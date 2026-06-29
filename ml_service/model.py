"""DocTamper tamper-localization model + inference (matches best.pth).

Mirrors ``backend/app/services/vision_service.py`` so the standalone ML
microservice and the in-process backend branch agree on architecture and
preprocessing. See ``doctamper.ipynb`` for the training contract.

    MDAVNet: nn.Embedding(21, 8) DCT stream + smp.Unet("resnet18",
             in_channels=11, classes=2) -> per-pixel tampered logits.
"""

import os
import tempfile

import numpy as np
import torch
import torch.nn as nn
import torchvision.transforms as T
from PIL import Image
import segmentation_models_pytorch as smp

_DCT_BINS, _DCT_DIM = 21, 8
_JPEG_QUALITY = 75
_MEAN, _STD = (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)
_STRIDE = 32


class DCTEmbed(nn.Module):
    def __init__(self, n_bins=_DCT_BINS, dim=_DCT_DIM):
        super().__init__()
        self.emb = nn.Embedding(n_bins, dim)

    def forward(self, dct):  # (B, H, W) -> (B, dim, H, W)
        return self.emb(dct.long()).permute(0, 3, 1, 2).contiguous()


class MDAVNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.dct = DCTEmbed()
        self.net = smp.Unet(
            encoder_name="resnet18", encoder_weights=None,
            in_channels=3 + _DCT_DIM, classes=2,
        )

    def forward(self, image, dct):
        return self.net(torch.cat([image, self.dct(dct)], dim=1))


class VisualTamperDetector:
    def __init__(self, model_path: str | None = None):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self._tmp = tempfile.mkdtemp(prefix="mdav_dct_")
        self.norm = T.Compose([T.ToTensor(), T.Normalize(mean=_MEAN, std=_STD)])
        if model_path and os.path.exists(model_path):
            self.load_model(model_path)

    def load_model(self, model_path: str):
        model = MDAVNet().to(self.device)
        ckpt = torch.load(model_path, map_location=self.device, weights_only=False)
        state = ckpt["model"] if isinstance(ckpt, dict) and "model" in ckpt else ckpt
        model.load_state_dict(state)
        model.eval()
        self.model = model

    def _preprocess(self, image_path: str):
        im = Image.open(image_path).convert("L")
        path = os.path.join(self._tmp, f"v_{os.getpid()}.jpg")
        im.save(path, "JPEG", quality=_JPEG_QUALITY)
        im = Image.open(path); im.load()
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

        rgb_t = self.norm(rgb_img)
        dct_t = torch.from_numpy(np.ascontiguousarray(dct))
        ph, pw = (-H) % _STRIDE, (-W) % _STRIDE
        if ph or pw:
            rgb_t = nn.functional.pad(rgb_t.unsqueeze(0), (0, pw, 0, ph), mode="reflect")[0]
            dct_t = nn.functional.pad(dct_t.unsqueeze(0), (0, pw, 0, ph), value=0)[0]
        return rgb_t.unsqueeze(0).to(self.device), dct_t.unsqueeze(0).to(self.device), (H, W)

    def predict(self, image_path: str) -> dict:
        if self.model is None:
            return {"error": "Model not loaded"}

        rgb, dct, (H, W) = self._preprocess(image_path)
        with torch.no_grad():
            prob = torch.softmax(self.model(rgb, dct), dim=1)[0, 1]
        m = prob[:H, :W].detach().cpu().numpy().astype(np.float32)

        peak = float(np.quantile(m, 0.995)) if m.size else 0.5
        area = float((m >= 0.5).mean()) if m.size else 0.0
        tamper = float(min(1.0, max(0.0, max(peak, min(1.0, area * 4.0)))))
        return {
            "class_label": "tampered" if tamper >= 0.5 else "clean",
            "tamper_probability": round(tamper, 4),
            "tampered_area_ratio": round(area, 4),
            "confidence": round(min(1.0, abs(tamper - 0.5) * 2 * 0.6 + 0.4), 4),
        }
