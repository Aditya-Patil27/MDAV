"""AIForge AI/diffusion-forgery segmentation branch.

The preferred backend is the local ``best_diffusion.pth`` checkpoint produced by
``notebooks/train_aiforge_diffusion.ipynb``. It is a two-class DCT+RGB semantic
segmentation model. An explicitly configured Hugging Face image classifier is
supported only as a fallback; this module never downloads a model by default.

All ML imports are lazy. Missing weights, dependencies, unreadable images, and
invalid checkpoints therefore yield vacuous Dempster-Shafer evidence instead of
preventing the backend from importing or the wider verification flow from
continuing.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from app.services.belief import BeliefMass, from_probability, vacuous
from app.services.localization_evidence import summarize_positive_regions


_DOCKER_MODEL_PATH = Path("/app/models/best_diffusion.pth")
_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_ARCHITECTURE = {
    "name": "MDAVNet",
    "encoder": "resnet18",
    "encoder_weights": None,
    "rgb_channels": 3,
    "dct_bins": 21,
    "dct_dim": 16,
    "classes": 2,
    "jpeg_quality": 95,
    "stride": 32,
    "mean": (0.485, 0.456, 0.406),
    "std": (0.229, 0.224, 0.225),
}
_AI_LABEL_HINTS = (
    "ai",
    "fake",
    "artificial",
    "generated",
    "synthetic",
    "gan",
    "diffusion",
)
_IDENTITY_DOCUMENT_TYPES = {"aadhaar", "pan", "passport", "driving_licence"}


def _requested_weights_path(model_path: str | None) -> Path | None:
    """Resolve an explicit path, or discover Docker/local default checkpoints."""
    if model_path is not None:
        return Path(model_path).expanduser()

    configured = os.getenv("MDAV_DIFFUSION_WEIGHTS")
    if configured:
        return Path(configured).expanduser()

    candidates = [
        _DOCKER_MODEL_PATH,
        Path.cwd() / "models" / "best_diffusion.pth",
        Path.cwd().parent / "models" / "best_diffusion.pth",
        _REPO_ROOT / "models" / "best_diffusion.pth",
        _BACKEND_ROOT.parent / "models" / "best_diffusion.pth",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return _DOCKER_MODEL_PATH


def _coerce_architecture(checkpoint: Any, state: dict[str, Any]) -> dict[str, Any]:
    """Return a validated model contract, preferring checkpoint metadata."""
    architecture = dict(_DEFAULT_ARCHITECTURE)
    if isinstance(checkpoint, dict) and isinstance(checkpoint.get("architecture"), dict):
        architecture.update(checkpoint["architecture"])

    embedding = state.get("dct.emb.weight")
    if embedding is not None and getattr(embedding, "shape", None) is not None:
        architecture["dct_bins"] = int(embedding.shape[0])
        architecture["dct_dim"] = int(embedding.shape[1])

    head = state.get("net.segmentation_head.0.weight")
    if head is not None and getattr(head, "shape", None) is not None:
        architecture["classes"] = int(head.shape[0])

    architecture["mean"] = tuple(float(v) for v in architecture["mean"])
    architecture["std"] = tuple(float(v) for v in architecture["std"])
    for key in ("rgb_channels", "dct_bins", "dct_dim", "classes", "jpeg_quality", "stride"):
        architecture[key] = int(architecture[key])

    if architecture["name"] != "MDAVNet":
        raise ValueError(f"unsupported AIForge architecture: {architecture['name']!r}")
    if architecture["rgb_channels"] != 3 or architecture["classes"] != 2:
        raise ValueError(
            "AIForge checkpoint must use three RGB channels and two segmentation classes"
        )
    if architecture["dct_bins"] <= 0 or architecture["dct_dim"] <= 0:
        raise ValueError("AIForge DCT dimensions must be positive")
    if architecture["stride"] <= 0 or architecture["jpeg_quality"] not in range(1, 101):
        raise ValueError("invalid AIForge preprocessing metadata")
    if len(architecture["mean"]) != 3 or len(architecture["std"]) != 3:
        raise ValueError("AIForge mean/std must contain three values")
    return architecture


def _checkpoint_threshold(checkpoint: Any) -> float:
    env_value = os.getenv("MDAV_DIFFUSION_THRESHOLD")
    if env_value is not None:
        threshold = float(env_value)
    elif isinstance(checkpoint, dict) and checkpoint.get("best_threshold") is not None:
        threshold = float(checkpoint["best_threshold"])
    else:
        threshold = 0.95
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("MDAV_DIFFUSION_THRESHOLD must be between 0 and 1")
    return threshold


def _build_model(architecture: dict[str, Any]):
    """Reconstruct MDAVNet from checkpoint metadata using lazy ML imports."""
    import torch
    import torch.nn as nn
    import segmentation_models_pytorch as smp

    dct_bins = architecture["dct_bins"]
    dct_dim = architecture["dct_dim"]

    class DCTEmbed(nn.Module):
        def __init__(self):
            super().__init__()
            self.emb = nn.Embedding(dct_bins, dct_dim)

        def forward(self, dct):
            return self.emb(dct.long()).permute(0, 3, 1, 2).contiguous()

    class MDAVNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.dct = DCTEmbed()
            self.net = smp.Unet(
                encoder_name=architecture["encoder"],
                encoder_weights=architecture.get("encoder_weights"),
                in_channels=architecture["rgb_channels"] + dct_dim,
                classes=architecture["classes"],
            )

        def forward(self, image, dct):
            return self.net(torch.cat([image, self.dct(dct)], dim=1))

    return MDAVNet()


class DiffusionService:
    """Detect localized AI-generated or diffusion-inpainted document regions."""

    def __init__(self, model_path: str | None = None, model_id: str | None = None):
        requested = _requested_weights_path(model_path)
        self.model_path = str(requested) if requested is not None else None
        self.model_id = model_id if model_id is not None else os.getenv("MDAV_DIFFUSION_MODEL")
        self.model = None
        self.processor = None
        self.device = "cpu"
        self.backend: str | None = None
        self.architecture = dict(_DEFAULT_ARCHITECTURE)
        self.threshold = 0.95
        self._ai_indices: list[int] = []
        self._load_failed_reason: str | None = None
        self._last_valid: tuple[int, int] | None = None
        self._last_prediction_details: dict[str, Any] = {}
        self._tmp = tempfile.TemporaryDirectory(prefix="mdav_diff_")
        self._try_load()

    def _try_load(self) -> None:
        failures: list[str] = []
        if self.model_path and Path(self.model_path).is_file():
            try:
                self._load_segmentation_model()
                return
            except Exception as exc:  # noqa: BLE001 - fail-soft model boundary
                self.model = None
                self.backend = None
                failures.append(f"segmentation {type(exc).__name__}: {exc}")
        else:
            failures.append(f"AIForge weights not found at {self.model_path}")

        if self.model_id:
            try:
                self._load_classifier_model()
                return
            except Exception as exc:  # noqa: BLE001 - optional explicit fallback
                self.model = None
                self.processor = None
                self.backend = None
                failures.append(f"classifier {type(exc).__name__}: {exc}")

        self._load_failed_reason = "; ".join(failures)

    def _load_segmentation_model(self) -> None:
        import torch

        checkpoint = torch.load(self.model_path, map_location="cpu", weights_only=False)
        state = checkpoint.get("model", checkpoint) if isinstance(checkpoint, dict) else checkpoint
        if not isinstance(state, dict):
            raise ValueError("checkpoint does not contain a model state dictionary")

        architecture = _coerce_architecture(checkpoint, state)
        threshold = _checkpoint_threshold(checkpoint)
        model = _build_model(architecture)
        model.load_state_dict(state, strict=True)

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        model.to(self.device).eval()
        self.model = model
        self.architecture = architecture
        self.threshold = threshold
        self.backend = "segmentation"
        self._load_failed_reason = None

    def _load_classifier_model(self) -> None:
        import torch
        from transformers import AutoImageProcessor, AutoModelForImageClassification

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        processor = AutoImageProcessor.from_pretrained(self.model_id)
        model = AutoModelForImageClassification.from_pretrained(self.model_id)
        model.to(self.device).eval()
        id2label = dict(model.config.id2label)
        ai_indices = [
            int(index)
            for index, label in id2label.items()
            if any(hint in str(label).lower() for hint in _AI_LABEL_HINTS)
        ]
        if not ai_indices:
            raise ValueError(f"could not identify an AI-generated class in {id2label!r}")

        self.processor = processor
        self.model = model
        self._ai_indices = ai_indices
        self.backend = "classifier"
        self._load_failed_reason = None

    @property
    def model_loaded(self) -> bool:
        return self.model is not None

    def analyze(self, image_path: str, *, document_type: str = "unknown") -> dict:
        if self.model is None:
            return self._result(
                ai_forgery_prob=None,
                confidence=0.0,
                mass=vacuous(source="diffusion"),
                reason=f"AI-forgery branch pending ({self._load_failed_reason}).",
                status="pending",
            )

        try:
            probability, confidence = self._predict(image_path)
        except Exception as exc:  # noqa: BLE001 - image/model errors stay branch-local
            return self._result(
                ai_forgery_prob=None,
                confidence=0.0,
                mass=vacuous(source="diffusion"),
                reason=f"AI-forgery analysis could not run: {exc}",
                status="error",
            )

        details = {"ai_forgery_prob": round(probability, 4)}
        details.update(self._last_prediction_details)
        if (
            self.backend == "segmentation"
            and not details.get("positive_region_detected", True)
        ):
            details["evidence_status"] = "inconclusive"
            mass = BeliefMass(
                authentic=0.0,
                forged=0.0,
                uncertain=1.0,
                source="diffusion",
                details=details,
            )
            return self._result(
                ai_forgery_prob=None,
                confidence=0.0,
                mass=mass,
                reason=(
                    "No coherent AIForge region reached the validated pixel threshold; "
                    "the branch contributed no forged evidence."
                ),
                status="inconclusive",
            )

        confidence, domain_limited = self._apply_domain_confidence_cap(
            confidence, document_type
        )
        if domain_limited:
            details["domain_limited"] = True
            details["model_limitation"] = (
                "AIForge was validated primarily on receipt/form edits; "
                "identity-document evidence is confidence-limited pending calibration."
            )
        mass = from_probability(
            1.0 - probability,
            confidence=confidence,
            source="diffusion",
            details=details,
        )
        return self._result(
            ai_forgery_prob=probability,
            confidence=confidence,
            mass=mass,
            reason=self._explain(probability, domain_limited=domain_limited),
            status="active",
        )

    def _predict(self, image_path: str) -> tuple[float, float]:
        if self.backend == "classifier":
            return self._predict_classifier(image_path)
        probability_map = self._infer_segmentation(image_path)
        return self._aggregate(probability_map)

    def _predict_classifier(self, image_path: str) -> tuple[float, float]:
        import torch
        from PIL import Image

        image = Image.open(image_path).convert("RGB")
        inputs = self.processor(images=image, return_tensors="pt").to(self.device)
        with torch.no_grad():
            logits = self.model(**inputs).logits
            probabilities = torch.softmax(logits, dim=1)[0]
        probability = float(probabilities[self._ai_indices].sum().item())
        probability = min(1.0, max(0.0, probability))
        confidence = min(1.0, abs(probability - 0.5) * 1.2 + 0.4)
        self._last_prediction_details = {
            "model_type": "hf_image_classifier",
            "model_id": str(self.model_id),
        }
        return probability, float(confidence)

    def _infer_segmentation(self, image_path: str):
        import numpy as np
        import torch

        rgb, dct = self._preprocess(image_path)
        with torch.no_grad():
            logits = self.model(rgb, dct)
            probability = torch.softmax(logits, dim=1)[0, 1]
        return probability.detach().cpu().numpy().astype(np.float32)

    def _preprocess(self, image_path: str):
        """Reproduce the checkpoint's grayscale-JPEG RGB+DCT preprocessing."""
        import numpy as np
        import torch
        import torchvision.transforms.functional as tf
        from PIL import Image

        image = Image.open(image_path).convert("L")
        max_side = int(os.getenv("MDAV_DIFFUSION_MAX_SIDE", "1536"))
        if max_side > 0 and max(image.size) > max_side:
            scale = max_side / max(image.size)
            width = max(8, int(image.size[0] * scale) // 8 * 8)
            height = max(8, int(image.size[1] * scale) // 8 * 8)
            image = image.resize((width, height), Image.Resampling.BILINEAR)

        handle = tempfile.NamedTemporaryFile(
            suffix=".jpg", dir=self._tmp.name, delete=False
        )
        temporary_path = Path(handle.name)
        handle.close()
        try:
            image.save(
                temporary_path,
                "JPEG",
                quality=self.architecture["jpeg_quality"],
            )
            import jpegio

            jpeg = jpegio.read(str(temporary_path))
            dct = np.clip(
                np.abs(jpeg.coef_arrays[0]),
                0,
                self.architecture["dct_bins"] - 1,
            ).astype(np.int64)
            jpeg_rgb = Image.open(temporary_path).convert("RGB")
            jpeg_rgb.load()
        finally:
            temporary_path.unlink(missing_ok=True)

        height = min(dct.shape[0], jpeg_rgb.size[1]) // 8 * 8
        width = min(dct.shape[1], jpeg_rgb.size[0]) // 8 * 8
        if height < 8 or width < 8:
            raise ValueError("image is too small for 8x8 JPEG DCT preprocessing")
        jpeg_rgb = jpeg_rgb.crop((0, 0, width, height))
        dct = dct[:height, :width]

        rgb_tensor = tf.normalize(
            tf.to_tensor(jpeg_rgb),
            mean=self.architecture["mean"],
            std=self.architecture["std"],
        )
        dct_tensor = torch.from_numpy(np.ascontiguousarray(dct)).long()

        stride = self.architecture["stride"]
        pad_height = -height % stride
        pad_width = -width % stride
        if pad_height or pad_width:
            rgb_tensor = torch.nn.functional.pad(
                rgb_tensor.unsqueeze(0),
                (0, pad_width, 0, pad_height),
                mode="reflect",
            )[0]
            dct_tensor = torch.nn.functional.pad(
                dct_tensor.unsqueeze(0),
                (0, pad_width, 0, pad_height),
                mode="constant",
                value=0,
            )[0]

        self._last_valid = (height, width)
        return (
            rgb_tensor.unsqueeze(0).to(self.device),
            dct_tensor.unsqueeze(0).to(self.device),
        )

    def _aggregate(self, probability_map) -> tuple[float, float]:
        import numpy as np

        height, width = self._last_valid or probability_map.shape
        valid = probability_map[:height, :width]
        if valid.size == 0:
            raise ValueError("segmentation model returned an empty probability map")

        min_component_pixels = max(
            1, int(os.getenv("MDAV_DIFFUSION_MIN_COMPONENT_PIXELS", "16"))
        )
        region = summarize_positive_regions(
            valid,
            threshold=self.threshold,
            min_component_pixels=min_component_pixels,
        )
        max_probability = float(valid.max())
        high_quantile = float(np.quantile(valid, 0.995))
        self._last_prediction_details = {
            "threshold": float(self.threshold),
            "max_prob": max_probability,
            "high_quantile": high_quantile,
            "model_type": "aiforge_segmentation",
            **region,
        }
        if not region["positive_region_detected"]:
            return 0.0, 0.0

        probability = float(region["largest_component_quantile"])
        threshold_margin = (probability - self.threshold) / (1.0 - self.threshold)
        area_scale = max(min_component_pixels * 8, valid.size * 0.002)
        area_support = min(1.0, float(region["largest_component_pixels"]) / area_scale)
        confidence = 0.20 + 0.50 * threshold_margin + 0.30 * area_support
        confidence = float(min(1.0, max(0.0, confidence)))
        return probability, confidence

    def _apply_domain_confidence_cap(
        self, confidence: float, document_type: str
    ) -> tuple[float, bool]:
        """Avoid over-committing an out-of-domain receipt/form model on IDs."""
        if document_type not in _IDENTITY_DOCUMENT_TYPES:
            return confidence, False
        cap = float(os.getenv("MDAV_IDENTITY_FORENSICS_CONFIDENCE_CAP", "0.25"))
        cap = min(1.0, max(0.0, cap))
        return min(confidence, cap), True

    def _explain(self, probability: float, *, domain_limited: bool = False) -> str:
        if probability < 0.30:
            message = "No localized AI/diffusion forgery evidence detected."
        elif probability < 0.60:
            message = "Possible localized AI/diffusion forgery evidence; review recommended."
        else:
            message = "Strong localized AI/diffusion forgery evidence detected."
        if domain_limited:
            return message + " Identity-document confidence is limited pending calibration."
        return message

    def _result(
        self,
        *,
        ai_forgery_prob,
        confidence,
        mass: BeliefMass,
        reason,
        status,
    ) -> dict:
        return {
            "ai_forgery_prob": (
                round(float(ai_forgery_prob), 4)
                if ai_forgery_prob is not None
                else None
            ),
            "confidence": round(float(confidence), 4),
            "reason": reason,
            "status": status,
            "details": dict(mass.details),
            "belief": mass.to_dict(),
            "_mass": mass,
        }


diffusion_service = DiffusionService()
