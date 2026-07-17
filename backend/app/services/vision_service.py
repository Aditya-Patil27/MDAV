"""Visual tamper-localization branch (the Kaggle-trained ``best.pth``).

The model is a DocTamper-style **segmentation** network, not a classifier:

    MDAVNet:
        dct = nn.Embedding(21, 8)                       # quantised-DCT stream
        net = smp.Unet("resnet18", in_channels=11, classes=2)
        forward(image, dct) -> logits (B, 2, H, W)

``softmax(1)[:, 1]`` is a per-pixel *tampered* probability map. This service
loads the checkpoint, reproduces the **exact** training preprocessing
(grayscale -> JPEG q75 -> RGB ImageNet-norm + jpegio quantised DCT clipped to
[0, 20]), runs a single fully-convolutional forward pass, aggregates the map to
a document-level ``tamper_probability``, and emits a Dempster-Shafer
``BeliefMass`` for fusion.

Every heavy dependency (torch, segmentation_models_pytorch, jpegio, cv2) is
imported lazily so the backend still imports and runs in *mock mode* on a host
without a GPU/torch stack (e.g. the dev machine). ``jpegio`` needs libjpeg and
is effectively Linux/Docker-only.
"""

from __future__ import annotations

import os
import tempfile

from app.services.belief import BeliefMass, from_probability, vacuous
from app.services.localization_evidence import summarize_positive_regions

# Checkpoint location. Defaults to the repo-root file the user provides; override
# with MDAV_VISION_WEIGHTS (the Docker image mounts it under /app/models).
MODEL_PATH = os.getenv(
    "MDAV_VISION_WEIGHTS",
    os.getenv("MODEL_PATH", "/app/models/best.pth"),
)

# Training contract (doctamper.ipynb) -- do not change without retraining.
_DCT_BINS = 21
_DCT_DIM = 8
_ENCODER = "resnet18"
_JPEG_QUALITY = 75          # val/minq recompression quality the model expects
_IMAGENET_MEAN = (0.485, 0.456, 0.406)
_IMAGENET_STD = (0.229, 0.224, 0.225)
# Safety cap: very large scans are downscaled before the forward pass so a CPU
# host does not OOM. Multiple of 8 keeps the DCT block grid aligned.
_MAX_SIDE = 1536
_STRIDE = 32                # smp Unet requires H, W divisible by 32 (>= 8 for DCT)
_IDENTITY_DOCUMENT_TYPES = {"aadhaar", "pan", "passport", "driving_licence"}


def _build_model():
    """Reconstruct ``MDAVNet`` exactly as trained. Imports torch/smp lazily."""
    import torch
    import torch.nn as nn
    import segmentation_models_pytorch as smp

    class DCTEmbed(nn.Module):
        def __init__(self, n_bins=_DCT_BINS, dim=_DCT_DIM):
            super().__init__()
            self.emb = nn.Embedding(n_bins, dim)

        def forward(self, dct):  # (B, H, W) int -> (B, dim, H, W)
            return self.emb(dct.long()).permute(0, 3, 1, 2).contiguous()

    class MDAVNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.dct = DCTEmbed()
            self.net = smp.Unet(
                encoder_name=_ENCODER,
                encoder_weights=None,          # weights come from the checkpoint
                in_channels=3 + _DCT_DIM,
                classes=2,
            )

        def forward(self, image, dct):
            return self.net(torch.cat([image, self.dct(dct)], dim=1))

    return MDAVNet()


class VisionService:
    """Tamper-localization over the document image."""

    def __init__(self, model_path: str | None = None):
        self.model_path = model_path if model_path is not None else MODEL_PATH
        self.model = None
        self.device = "cpu"
        self._load_failed_reason = None
        self._tmp = tempfile.mkdtemp(prefix="mdav_dct_")
        self._try_load()

    # ---- loading -------------------------------------------------------------

    def _try_load(self) -> None:
        if not self.model_path or not os.path.exists(self.model_path):
            self._load_failed_reason = f"weights not found at {self.model_path}"
            return
        try:
            import torch

            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            model = _build_model().to(self.device)
            ckpt = torch.load(self.model_path, map_location=self.device, weights_only=False)
            state = ckpt["model"] if isinstance(ckpt, dict) and "model" in ckpt else ckpt
            model.load_state_dict(state)
            model.eval()
            self.model = model
        except Exception as e:  # noqa: BLE001 - any failure -> graceful mock mode
            self.model = None
            self._load_failed_reason = f"{type(e).__name__}: {e}"

    @property
    def model_loaded(self) -> bool:
        return self.model is not None

    # ---- public API ----------------------------------------------------------

    def analyze(self, image_path: str, *, document_type: str = "unknown") -> dict:
        """Return a vision result dict (+ ``_mass`` BeliefMass) for ``image_path``."""
        if self.model is None:
            return self._mock_analysis(reason=self._load_failed_reason)

        try:
            prob_map, size = self._infer(image_path)
        except Exception as e:  # noqa: BLE001 - unreadable/odd input -> stay vacuous
            mass = vacuous(source="visual")
            return self._result(
                tamper_prob=None, confidence=0.0, mass=mass,
                explanation=f"Visual analysis could not run: {e}",
                heatmap_path=None, mock=False, status="error",
            )

        tamper_prob, confidence, area = self._aggregate(prob_map)
        heatmap_path = self._save_heatmap(prob_map, image_path)
        details = dict(self._last_prediction_details)
        if not details.get("positive_region_detected", True):
            mass = BeliefMass(
                authentic=0.0,
                forged=0.0,
                uncertain=1.0,
                source="visual",
                details=details,
            )
            return self._result(
                tamper_prob=None,
                confidence=0.0,
                mass=mass,
                explanation=(
                    "No coherent visual-tamper region reached the operating threshold; "
                    "the branch contributed no forged evidence."
                ),
                heatmap_path=heatmap_path,
                mock=False,
                status="inconclusive",
            )

        confidence, domain_limited = self._apply_domain_confidence_cap(
            confidence, document_type
        )
        if domain_limited:
            details["domain_limited"] = True
            details["model_limitation"] = (
                "The visual localizer requires identity-document calibration for "
                "photographs, holograms, and security-print artifacts."
            )

        # Calibrated belief: p(authentic) = 1 - tamper_prob, committed in
        # proportion to the model's confidence; the rest stays uncertain.
        mass = from_probability(
            1.0 - tamper_prob,
            confidence=confidence,
            source="visual",
            details=details,
        )
        return self._result(
            tamper_prob=tamper_prob, confidence=confidence, mass=mass,
            explanation=self._explain(
                tamper_prob, area, domain_limited=domain_limited
            ),
            heatmap_path=heatmap_path, mock=False, status="active",
        )

    # ---- inference -----------------------------------------------------------

    def _infer(self, image_path: str):
        """Run the model and return (tampered_prob_map HxW float, (H, W))."""
        import numpy as np
        import torch

        rgb, dct = self._preprocess(image_path)        # tensors on self.device
        with torch.no_grad():
            logits = self.model(rgb, dct)              # (1, 2, H, W)
            prob = torch.softmax(logits, dim=1)[0, 1]  # tampered channel
        return prob.detach().cpu().numpy().astype(np.float32), tuple(prob.shape)

    def _preprocess(self, image_path: str):
        """Reproduce the DocTamper training preprocessing exactly.

        grayscale -> JPEG quality 75 -> RGB ImageNet-normalised tensor, plus the
        jpegio quantised-DCT map (|coef| clipped to [0, 20]) as the embedding
        index stream. RGB and DCT are cropped to a common 8-aligned size and
        padded to a multiple of 32 for the Unet.
        """
        import numpy as np
        import torch
        import torchvision.transforms as T
        from PIL import Image

        im = Image.open(image_path).convert("L")
        # Safety downscale for very large scans (keep multiple-of-8 dims).
        if max(im.size) > _MAX_SIDE:
            scale = _MAX_SIDE / max(im.size)
            w = max(8, int(im.size[0] * scale) // 8 * 8)
            h = max(8, int(im.size[1] * scale) // 8 * 8)
            im = im.resize((w, h), Image.BILINEAR)

        # Final JPEG pass through a real path (jpegio needs a file).
        path = os.path.join(self._tmp, f"v_{os.getpid()}.jpg")
        im.save(path, "JPEG", quality=_JPEG_QUALITY)
        im = Image.open(path)
        im.load()
        rgb_img = im.convert("RGB")

        import jpegio
        jpg = jpegio.read(path)
        dct = np.clip(np.abs(jpg.coef_arrays[0]), 0, 20).astype(np.int64)
        try:
            os.remove(path)
        except OSError:
            pass

        # Common 8-aligned crop (top-left, matching the val path).
        H = min(dct.shape[0], rgb_img.size[1]) // 8 * 8
        W = min(dct.shape[1], rgb_img.size[0]) // 8 * 8
        rgb_img = rgb_img.crop((0, 0, W, H))
        dct = dct[:H, :W]

        norm = T.Compose([
            T.ToTensor(),
            T.Normalize(mean=_IMAGENET_MEAN, std=_IMAGENET_STD),
        ])
        rgb_t = norm(rgb_img)                          # (3, H, W)
        dct_t = torch.from_numpy(np.ascontiguousarray(dct))  # (H, W)

        # Pad right/bottom to a multiple of 32 (reflect for RGB, 0 for DCT idx).
        ph = (-(H) % _STRIDE)
        pw = (-(W) % _STRIDE)
        if ph or pw:
            rgb_t = torch.nn.functional.pad(rgb_t.unsqueeze(0), (0, pw, 0, ph), mode="reflect")[0]
            dct_t = torch.nn.functional.pad(dct_t.unsqueeze(0), (0, pw, 0, ph), mode="constant", value=0)[0]

        rgb_t = rgb_t.unsqueeze(0).to(self.device)
        dct_t = dct_t.unsqueeze(0).to(self.device)
        # Remember the unpadded region so the map can be cropped back.
        self._last_valid = (H, W)
        return rgb_t, dct_t

    def _aggregate(self, prob_map):
        """Collapse a pixel map only after a coherent positive region exists."""
        import numpy as np

        H, W = getattr(self, "_last_valid", prob_map.shape)
        m = prob_map[:H, :W]
        if m.size == 0:
            return 0.5, 0.0, 0.0
        threshold = float(os.getenv("MDAV_VISUAL_PIXEL_THRESHOLD", "0.80"))
        min_component_pixels = max(
            1, int(os.getenv("MDAV_VISUAL_MIN_COMPONENT_PIXELS", "16"))
        )
        region = summarize_positive_regions(
            m,
            threshold=threshold,
            min_component_pixels=min_component_pixels,
        )
        self._last_prediction_details = {
            "threshold": threshold,
            "max_prob": float(m.max()),
            "high_quantile": float(np.quantile(m, 0.995)),
            "model_type": "doctamper_segmentation",
            **region,
        }
        if not region["positive_region_detected"]:
            return 0.0, 0.0, float(region["threshold_area"])

        tamper_prob = float(region["largest_component_quantile"])
        margin = (tamper_prob - threshold) / (1.0 - threshold)
        area_scale = max(min_component_pixels * 8, m.size * 0.002)
        area_support = min(1.0, float(region["largest_component_pixels"]) / area_scale)
        confidence = float(min(1.0, max(0.0, 0.20 + 0.50 * margin + 0.30 * area_support)))
        return tamper_prob, confidence, float(region["largest_component_area"])

    def _save_heatmap(self, prob_map, image_path: str):
        try:
            import numpy as np
            import cv2

            H, W = getattr(self, "_last_valid", prob_map.shape)
            m = (np.clip(prob_map[:H, :W], 0, 1) * 255).astype("uint8")
            heat = cv2.applyColorMap(m, cv2.COLORMAP_JET)
            out_dir = os.getenv("HEATMAP_DIR", os.path.join(os.path.dirname(image_path) or ".", "heatmaps"))
            os.makedirs(out_dir, exist_ok=True)
            out = os.path.join(out_dir, os.path.splitext(os.path.basename(image_path))[0] + "_heatmap.png")
            cv2.imwrite(out, heat)
            return out
        except Exception:  # noqa: BLE001 - heatmap is best-effort, never fatal
            return None

    # ---- mock fallback -------------------------------------------------------

    def _mock_analysis(self, reason: str | None = None) -> dict:
        """Return explicit unavailability with vacuous evidence."""
        mass = vacuous(source="visual")
        return self._result(
            tamper_prob=None, confidence=0.0, mass=mass,
            explanation=(
                "Visual model unavailable (" + (reason or "no weights") + "); "
                "branch contributes no evidence."
            ),
            heatmap_path=None, mock=True, status="unavailable",
        )

    # ---- helpers -------------------------------------------------------------

    def _apply_domain_confidence_cap(
        self, confidence: float, document_type: str
    ) -> tuple[float, bool]:
        if document_type not in _IDENTITY_DOCUMENT_TYPES:
            return confidence, False
        cap = float(os.getenv("MDAV_IDENTITY_FORENSICS_CONFIDENCE_CAP", "0.25"))
        cap = min(1.0, max(0.0, cap))
        return min(confidence, cap), True

    def _explain(
        self, tamper_prob: float, area: float, *, domain_limited: bool = False
    ) -> str:
        if tamper_prob < 0.3:
            message = "No significant tampering detected by the visual localizer."
        elif tamper_prob < 0.6:
            message = (
                f"Minor visual anomalies detected (~{area*100:.1f}% of pixels). "
                "Manual review advised."
            )
        elif tamper_prob < 0.8:
            message = f"Significant tampering localized over ~{area*100:.1f}% of the document."
        else:
            message = f"Strong tampering signal localized over ~{area*100:.1f}% of the document."
        if domain_limited:
            return message + " Identity-document confidence is limited pending calibration."
        return message

    def _result(self, *, tamper_prob, confidence, mass: BeliefMass, explanation,
                heatmap_path, mock, status) -> dict:
        return {
            "tamper_probability": (
                round(float(tamper_prob), 4) if tamper_prob is not None else None
            ),
            "confidence": round(float(confidence), 4),
            "heatmap_path": heatmap_path,
            "explanation": explanation,
            "mock": mock,
            "status": status,
            "belief": mass.to_dict(),
            "_mass": mass,
        }


vision_service = VisionService()
