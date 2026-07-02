"""Diffusion / AI-generated forgery branch.

Detects **AI-generated / diffusion-synthesised documents** (a distinct fraud
vector from the localized splice/inpaint tampering the DocTamper ``visual``
branch catches). To make the branch functional without bespoke training, it is
backed by a **pretrained, publicly downloadable image classifier** on the HF Hub
-- any model that outputs real-vs-AI logits works, because the loader auto-detects
the "AI" class from the model's own ``id2label`` and maps softmax -> belief.

Pick the model with one env var (no code change):
    * MDAV_DIFFUSION_MODEL (default ``Ateeqq/ai-vs-human-image-detector``, Apache-2.0)
      alternatives: ``Organika/sdxl-detector`` (Swin, diffusion/SDXL-specific, CC-BY-NC),
      or a local path / your own AIForge-trained classifier.

Contract (unchanged, so fusion/DB/UI need no edits):
    * ``_predict(image_path) -> (ai_forgery_prob in [0,1], confidence in [0,1])``
    * belief = ``from_probability(1 - ai_forgery_prob, confidence=...)`` -- the raw
      (uncalibrated) softmax feeds the belief mass; the per-source reliability
      discount is applied later in ``fusion_service``.

``torch`` / ``transformers`` are imported lazily so the backend still imports and
runs in *mock mode* (vacuous belief -> contributes nothing) on a host without the
ML stack or without network access to fetch the model.
"""

from __future__ import annotations

import os

from app.services.belief import BeliefMass, from_probability, vacuous

# Which pretrained detector backs the branch. Any HF image-classification model
# with real-vs-AI labels works; default is permissively licensed (Apache-2.0).
MODEL_ID = os.getenv("MDAV_DIFFUSION_MODEL", "Ateeqq/ai-vs-human-image-detector")

# Substrings that mark a label as the "AI-generated / fake" class.
_AI_LABEL_HINTS = ("ai", "fake", "artificial", "generated", "synthetic", "gan", "diffusion")


class DiffusionService:
    """Detect AI-generated / diffusion-synthesised documents."""

    def __init__(self, model_id: str | None = None):
        self.model_id = model_id if model_id is not None else MODEL_ID
        self.model = None
        self.processor = None
        self.device = "cpu"
        self._ai_indices: list[int] = []
        self._load_failed_reason = None
        self._try_load()

    # ---- loading -------------------------------------------------------------

    def _try_load(self) -> None:
        try:
            import torch
            from transformers import AutoImageProcessor, AutoModelForImageClassification

            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.processor = AutoImageProcessor.from_pretrained(self.model_id)
            model = AutoModelForImageClassification.from_pretrained(self.model_id)
            model.to(self.device).eval()
            self.model = model

            # Locate the "AI-generated" output index/indices from the model's labels.
            id2label = dict(model.config.id2label)
            self._ai_indices = [
                int(i) for i, lbl in id2label.items()
                if any(h in str(lbl).lower() for h in _AI_LABEL_HINTS)
            ]
            if not self._ai_indices:
                # No label matched the hints -> can't tell which class is "AI".
                # Fail safe to mock rather than guess and emit misleading beliefs.
                self.model = None
                self._load_failed_reason = (
                    f"could not identify an AI-generated class in {id2label!r}; "
                    "set MDAV_DIFFUSION_MODEL to a real-vs-AI classifier"
                )
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
        """Return (ai_forgery_prob, confidence) from the classifier's softmax."""
        import torch
        from PIL import Image

        img = Image.open(image_path).convert("RGB")
        inputs = self.processor(images=img, return_tensors="pt").to(self.device)
        with torch.no_grad():
            logits = self.model(**inputs).logits          # (1, num_labels)
            probs = torch.softmax(logits, dim=1)[0]
        # Uncalibrated P(AI-generated) = summed prob of the AI-labeled class(es).
        ai_prob = float(probs[self._ai_indices].sum().item())
        ai_prob = min(1.0, max(0.0, ai_prob))
        # Decisive outputs (clearly AI or clearly real) -> higher confidence.
        confidence = float(min(1.0, abs(ai_prob - 0.5) * 2.0 * 0.6 + 0.4))
        return ai_prob, confidence

    # ---- helpers -------------------------------------------------------------

    def _explain(self, prob: float) -> str:
        if prob < 0.3:
            return "No AI-generation / diffusion artifacts detected."
        if prob < 0.6:
            return "Possible AI-generated content; review recommended."
        return "Strong evidence the document is AI-generated / diffusion-synthesised."

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
