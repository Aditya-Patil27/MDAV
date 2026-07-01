"""Diffusion / AI-generated forgery branch (the AIForge model).

Detects diffusion-/GAN-inpainted document regions -- a different forensic signal
from the copy-move/splice tampering the DocTamper ``visual`` branch catches. The
model is the **same** ``MDAVNet`` architecture as the visual branch (DCT + Unet),
but trained standalone on AIForge-Doc-v1, so it reuses the identical preprocessing
and is loaded from a *separate* checkpoint (``best_diffusion.pth``).

Contract (mask-based -- the model is a per-pixel localizer, aggregated to a
document-level score):
    * weights at ``MDAV_DIFFUSION_WEIGHTS`` (default ``/app/models/best_diffusion.pth``)
    * ``_predict(image_path) -> (ai_forgery_prob in [0,1], confidence in [0,1])``
    * belief = ``from_probability(1 - ai_forgery_prob, confidence=...)``

Everything heavy (torch, smp, jpegio, cv2) is imported lazily so the backend
still imports and runs in *mock mode* on a host without the ML stack. The branch
emits a **vacuous** belief (contributes nothing) until weights are present.
"""

from __future__ import annotations

import os
import tempfile

from app.services.belief import BeliefMass, from_probability, vacuous

MODEL_PATH = os.getenv("MDAV_DIFFUSION_WEIGHTS", "/app/models/best_diffusion.pth")

# Training contract -- must match train_aiforge_diffusion.ipynb (and the visual
# branch, since the architecture/preprocessing are shared). Do not change without
# retraining best_diffusion.pth.
_DCT_BINS = 21
_DCT_DIM = 8
_ENCODER = "resnet18"
_JPEG_QUALITY = 75
_IMAGENET_MEAN = (0.485, 0.456, 0.406)
_IMAGENET_STD = (0.229, 0.224, 0.225)
_MAX_SIDE = 1536            # downscale very large scans so a CPU host does not OOM
_STRIDE = 32               # smp Unet needs H, W divisible by 32


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


class DiffusionService:
    """Detect AI-generated / diffusion-inpainted forgery (AIForge)."""

    def __init__(self, model_path: str | None = None):
        self.model_path = model_path if model_path is not None else MODEL_PATH
        self.model = None
        self.device = "cpu"
        self._load_failed_reason = None
        self._tmp = tempfile.mkdtemp(prefix="mdav_diff_")
        self._last_valid = None
        self._try_load()

    # ---- loading -------------------------------------------------------------

    def _try_load(self) -> None:
        if not self.model_path or not os.path.exists(self.model_path):
            self._load_failed_reason = f"AIForge weights not found at {self.model_path}"
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
        if self.model is None:
            return self._result(
                ai_forgery_prob=None, confidence=0.0,
                mass=vacuous(source="diffusion"),
                reason=f"AI-forgery branch pending ({self._load_failed_reason}).",
                status="pending",
            )

        try:
            prob, confidence = self._predict(image_path)
        except Exception as e:  # noqa: BLE001
            return self._result(
                ai_forgery_prob=None, confidence=0.0,
                mass=vacuous(source="diffusion"),
                reason=f"AI-forgery analysis could not run: {e}", status="error",
            )

        mass = from_probability(
            1.0 - prob, confidence=confidence, source="diffusion",
            details={"ai_forgery_prob": round(prob, 4)},
        )
        return self._result(
            ai_forgery_prob=prob, confidence=confidence, mass=mass,
            reason=self._explain(prob), status="active",
        )

    # ---- inference -----------------------------------------------------------

    def _predict(self, image_path: str):
        """Run the model and aggregate its mask to (ai_forgery_prob, confidence)."""
        prob_map = self._infer(image_path)
        return self._aggregate(prob_map)

    def _infer(self, image_path: str):
        import numpy as np
        import torch

        rgb, dct = self._preprocess(image_path)
        with torch.no_grad():
            logits = self.model(rgb, dct)              # (1, 2, H, W)
            prob = torch.softmax(logits, dim=1)[0, 1]  # AI-forged channel
        return prob.detach().cpu().numpy().astype(np.float32)

    def _preprocess(self, image_path: str):
        """Reproduce the AIForge training preprocessing exactly (== visual branch).

        grayscale -> JPEG q75 -> RGB ImageNet-normalised tensor, plus the jpegio
        quantised-DCT map (|coef| clipped to [0, 20]). RGB and DCT are cropped to
        a common 8-aligned size and padded to a multiple of 32 for the Unet.
        """
        import numpy as np
        import torch
        import torchvision.transforms as T
        from PIL import Image

        im = Image.open(image_path).convert("L")
        if max(im.size) > _MAX_SIDE:
            scale = _MAX_SIDE / max(im.size)
            w = max(8, int(im.size[0] * scale) // 8 * 8)
            h = max(8, int(im.size[1] * scale) // 8 * 8)
            im = im.resize((w, h), Image.BILINEAR)

        path = os.path.join(self._tmp, f"d_{os.getpid()}.jpg")
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

        H = min(dct.shape[0], rgb_img.size[1]) // 8 * 8
        W = min(dct.shape[1], rgb_img.size[0]) // 8 * 8
        rgb_img = rgb_img.crop((0, 0, W, H))
        dct = dct[:H, :W]

        norm = T.Compose([
            T.ToTensor(),
            T.Normalize(mean=_IMAGENET_MEAN, std=_IMAGENET_STD),
        ])
        rgb_t = norm(rgb_img)                              # (3, H, W)
        dct_t = torch.from_numpy(np.ascontiguousarray(dct))  # (H, W)

        ph = (-(H) % _STRIDE)
        pw = (-(W) % _STRIDE)
        if ph or pw:
            rgb_t = torch.nn.functional.pad(rgb_t.unsqueeze(0), (0, pw, 0, ph), mode="reflect")[0]
            dct_t = torch.nn.functional.pad(dct_t.unsqueeze(0), (0, pw, 0, ph), mode="constant", value=0)[0]

        rgb_t = rgb_t.unsqueeze(0).to(self.device)
        dct_t = dct_t.unsqueeze(0).to(self.device)
        self._last_valid = (H, W)
        return rgb_t, dct_t

    def _aggregate(self, prob_map):
        """Collapse the pixel map to (ai_forgery_prob, confidence).

        Same policy as the visual branch: a high quantile (robust to a few hot
        pixels) is the document score, and a large flagged area also drives it up.
        """
        import numpy as np

        H, W = self._last_valid or prob_map.shape
        m = prob_map[:H, :W]
        if m.size == 0:
            return 0.5, 0.0
        peak = float(np.quantile(m, 0.995))
        area = float((m >= 0.5).mean())
        prob = max(peak, min(1.0, area * 4.0))
        prob = float(min(1.0, max(0.0, prob)))
        confidence = float(min(1.0, abs(prob - 0.5) * 2.0 * 0.6 + 0.4))
        return prob, confidence

    # ---- helpers -------------------------------------------------------------

    def _explain(self, prob: float) -> str:
        if prob < 0.3:
            return "No diffusion/AI-generation artifacts detected."
        if prob < 0.6:
            return "Possible AI-generated regions; review recommended."
        return "Strong evidence of AI-generated / diffusion-inpainted content."

    def _result(self, *, ai_forgery_prob, confidence, mass: BeliefMass, reason, status) -> dict:
        return {
            "ai_forgery_prob": round(float(ai_forgery_prob), 4) if ai_forgery_prob is not None else None,
            "confidence": round(float(confidence), 4),
            "reason": reason,
            "status": status,
            "belief": mass.to_dict(),
            "_mass": mass,
        }


diffusion_service = DiffusionService()
