"""Diffusion / AI-generated forgery branch (the AIForge model -- WIP).

This is the slot for the teammate's **AIForge** model, which detects
diffusion-/GAN-inpainted or fully AI-generated document regions (a different
forensic signal from the copy-move/splice tampering the visual DocTamper branch
catches). The dataset/model is still being built, so this branch ships as a
documented placeholder that emits a **vacuous** belief (contributes nothing) and
flips on automatically once weights are provided.

Expected contract (probability-based -- adjust if AIForge outputs a mask):
    * weights at ``MDAV_DIFFUSION_WEIGHTS``
    * ``_predict(image_path) -> (ai_forgery_prob: float in [0,1], confidence)``
    * belief = ``from_probability(1 - ai_forgery_prob, confidence=...)``

Everything heavy is imported lazily so the backend runs without the model.
"""

from __future__ import annotations

import os

from app.services.belief import BeliefMass, from_probability, vacuous

MODEL_PATH = os.getenv("MDAV_DIFFUSION_WEIGHTS", "/app/models/best_diffusion.pth")


class DiffusionService:
    """Detect AI-generated / diffusion-inpainted forgery (AIForge)."""

    def __init__(self, model_path: str | None = None):
        self.model_path = model_path if model_path is not None else MODEL_PATH
        self.model = None
        self._load_failed_reason = None
        self._try_load()

    def _try_load(self) -> None:
        if not self.model_path or not os.path.exists(self.model_path):
            self._load_failed_reason = "AIForge model not yet available"
            return
        try:
            # TODO(AIForge): build MDAVNet-equivalent / classifier here once the
            # teammate finalises the dataset + architecture, then set self.model.
            self._load_failed_reason = "AIForge loader not implemented yet"
        except Exception as e:  # noqa: BLE001
            self.model = None
            self._load_failed_reason = f"{type(e).__name__}: {e}"

    @property
    def model_loaded(self) -> bool:
        return self.model is not None

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

    # ---- to be implemented when AIForge weights land -------------------------

    def _predict(self, image_path: str):  # pragma: no cover - placeholder
        raise NotImplementedError("AIForge model not wired yet")

    def _explain(self, prob: float) -> str:
        if prob < 0.3:
            return "No diffusion/AI-generation artifacts detected."
        if prob < 0.6:
            return "Possible AI-generated regions; review recommended."
        return "Strong evidence of AI-generated / diffusion-inpainted content."

    def _result(self, *, ai_forgery_prob, confidence, mass: BeliefMass, reason, status) -> dict:
        return {
            "ai_forgery_prob": ai_forgery_prob,
            "confidence": round(float(confidence), 4),
            "reason": reason,
            "status": status,
            "belief": mass.to_dict(),
            "_mass": mass,
        }


diffusion_service = DiffusionService()
