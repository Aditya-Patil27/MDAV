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

    def analyze(self, image_path: str) -> dict:
        """Return a vision result dict (+ ``_mass`` BeliefMass) for ``image_path``."""
        if self.model is None:
            return self._mock_analysis(reason=self._load_failed_reason)

        try:
            prob_map, size = self._infer(image_path)
        except Exception as e:  # noqa: BLE001 - unreadable/odd input -> stay vacuous
            mass = vacuous(source="visual")
            return self._result(
                tamper_prob=0.5, confidence=0.0, mass=mass,
                explanation=f"Visual analysis could not run: {e}",
                heatmap_path=None, mock=False,
            )

        tamper_prob, confidence, area = self._aggregate(prob_map)
        heatmap_path = self._save_heatmap(prob_map, image_path)

        # Calibrated belief: p(authentic) = 1 - tamper_prob, committed in
        # proportion to the model's confidence; the rest stays uncertain.
        mass = from_probability(
            1.0 - tamper_prob,
            confidence=confidence,
            source="visual",
            details={"tampered_area_ratio": round(area, 4)},
        )
        return self._result(
            tamper_prob=tamper_prob, confidence=confidence, mass=mass,
            explanation=self._explain(tamper_prob, area),
            heatmap_path=heatmap_path, mock=False,
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
        """Collapse the pixel map to (tamper_probability, confidence, area_ratio).

        A localization model should flag a document when a *confident region*
        exists, so the document score is a high quantile of the map (robust to a
        few hot pixels) rather than the mean, which a small forgery would dilute.
        ``area_ratio`` is the fraction of pixels predicted tampered.
        """
        import numpy as np

        H, W = getattr(self, "_last_valid", prob_map.shape)
        m = prob_map[:H, :W]
        if m.size == 0:
            return 0.5, 0.0, 0.0
        peak = float(np.quantile(m, 0.995))
        area = float((m >= 0.5).mean())
        tamper_prob = max(peak, min(1.0, area * 4.0))  # large tampered area also drives it up
        tamper_prob = float(min(1.0, max(0.0, tamper_prob)))
        # Confidence: decisive maps (clearly hot or clearly cold) -> high.
        confidence = float(min(1.0, abs(tamper_prob - 0.5) * 2.0 * 0.6 + 0.4))
        return tamper_prob, confidence, area

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
        """Vacuous belief + flagged-mock scores when the model is unavailable."""
        mass = vacuous(source="visual")
        return self._result(
            tamper_prob=0.5, confidence=0.0, mass=mass,
            explanation=(
                "Visual model unavailable (" + (reason or "no weights") + "); "
                "branch contributes no evidence."
            ),
            heatmap_path=None, mock=True,
        )

    # ---- helpers -------------------------------------------------------------

    def _explain(self, tamper_prob: float, area: float) -> str:
        if tamper_prob < 0.3:
            return "No significant tampering detected by the visual localizer."
        if tamper_prob < 0.6:
            return f"Minor visual anomalies detected (~{area*100:.1f}% of pixels). Manual review advised."
        if tamper_prob < 0.8:
            return f"Significant tampering localized over ~{area*100:.1f}% of the document."
        return f"Strong tampering signal localized over ~{area*100:.1f}% of the document."

    def _result(self, *, tamper_prob, confidence, mass: BeliefMass, explanation,
                heatmap_path, mock) -> dict:
        return {
            "tamper_probability": round(float(tamper_prob), 4),
            "confidence": round(float(confidence), 4),
            "heatmap_path": heatmap_path,
            "explanation": explanation,
            "mock": mock,
            "belief": mass.to_dict(),
            "_mass": mass,
        }


vision_service = VisionService()
