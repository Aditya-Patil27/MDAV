"""Aadhaar layout-detection branch (the Kaggle-trained YOLOv8n ``best_layout_detector.pt``).

The detector (Ultralytics YOLOv8n, imgsz 640) localizes the five Aadhaar fields::

    0 aadhaar_number   1 dob   2 gender   3 name   4 address

This branch serves two purposes:

1. **Field crops** for the OCR branch (a tight crop OCRs far better than a whole
   noisy card) -- exposed in the result as ``detections`` with pixel boxes.
2. A *weak* structural authenticity signal: a genuine Aadhaar exposes a known
   set of labelled fields in a plausible arrangement. This is the weakest branch
   (layout is easy to mimic, and a legitimately cropped photo may miss fields),
   so it emits low-committed belief and is discounted hard at fusion time.
   Absence of fields is treated as *uncertainty*, never as forgery.

``ultralytics``/torch are imported lazily so the backend imports and runs in
mock mode on a host without the model or its dependencies.
"""

from __future__ import annotations

import os

from app.services.belief import BeliefMass, from_check, vacuous

MODEL_PATH = os.getenv(
    "MDAV_LAYOUT_WEIGHTS",
    "/app/models/best_layout_detector.pt",
)

# Class order is fixed by training (Untitled5.ipynb data.yaml). Do not reorder.
CLASS_NAMES = ["aadhaar_number", "dob", "gender", "name", "address"]
# Fields whose presence is the core structural signal of an Aadhaar card.
_KEY_FIELDS = {"aadhaar_number", "name", "dob"}
_CONF_THRESHOLD = float(os.getenv("MDAV_LAYOUT_CONF", "0.40"))


class LayoutService:
    """Detect Aadhaar layout fields and score structural plausibility."""

    def __init__(self, model_path: str | None = None):
        self.model_path = model_path if model_path is not None else MODEL_PATH
        self.model = None
        self._load_failed_reason = None
        self._try_load()

    def _try_load(self) -> None:
        if not self.model_path or not os.path.exists(self.model_path):
            self._load_failed_reason = f"weights not found at {self.model_path}"
            return
        try:
            from ultralytics import YOLO

            self.model = YOLO(self.model_path)
        except Exception as e:  # noqa: BLE001 - missing dep / bad file -> mock mode
            self.model = None
            self._load_failed_reason = f"{type(e).__name__}: {e}"

    @property
    def model_loaded(self) -> bool:
        return self.model is not None

    # ---- public API ----------------------------------------------------------

    def analyze(self, image_path: str) -> dict:
        """Detect fields and return a layout result dict (+ ``_mass``)."""
        if self.model is None:
            return self._result(
                detections=[], mass=vacuous(source="layout"),
                reason=f"Layout model unavailable ({self._load_failed_reason or 'no weights'})",
                mock=True, status="unavailable",
            )

        try:
            detections = self._detect(image_path)
        except Exception as e:  # noqa: BLE001
            return self._result(
                detections=[], mass=vacuous(source="layout"),
                reason=f"Layout detection could not run: {e}", mock=False, status="error",
            )

        mass = self._score(detections)
        return self._result(
            detections=detections, mass=mass,
            reason=self._reason(detections), mock=False, status="active",
        )

    def for_document_context(self, result: dict, document_type: str) -> dict:
        """Keep Aadhaar crops for OCR but suppress Aadhaar-only fusion on other IDs."""
        if document_type in {"unknown", "aadhaar"}:
            return result
        return self._result(
            detections=[],
            mass=vacuous(source="layout"),
            reason=(
                "The available layout detector is trained for Aadhaar fields and "
                f"does not contribute structural evidence for {document_type}."
            ),
            mock=bool(result.get("mock", False)),
            status="not_applicable",
        )

    # ---- detection -----------------------------------------------------------

    def _detect(self, image_path: str) -> list[dict]:
        results = self.model.predict(source=image_path, conf=_CONF_THRESHOLD, verbose=False)
        if not results:
            return []
        r = results[0]
        names = getattr(r, "names", None) or self.model.names
        out: list[dict] = []
        for box in r.boxes:
            cls_id = int(box.cls[0].item())
            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
            out.append({
                "label": names.get(cls_id, str(cls_id)) if isinstance(names, dict) else names[cls_id],
                "class_id": cls_id,
                "confidence": round(float(box.conf[0].item()), 4),
                "bbox": [x1, y1, x2, y2],
            })
        return out

    # ---- scoring -------------------------------------------------------------

    def _score(self, detections: list[dict]) -> BeliefMass:
        """Weak structural belief from which fields were confidently found.

        Only *presence* contributes authentic mass; absence stays uncertain
        (a cropped or partial scan is not forged). The pass weight is modest so
        layout never overrides a conclusive forensic branch.
        """
        found = {d["label"] for d in detections if d["confidence"] >= _CONF_THRESHOLD}
        key_hits = len(found & _KEY_FIELDS)
        if key_hits == 0:
            return vacuous(source="layout")
        # 0.20 -> 0.40 authentic mass as 1..3 key fields appear; rest uncertain.
        w_pass = min(0.40, 0.10 + 0.10 * key_hits)
        return from_check(
            True, w_pass=w_pass, source="layout",
            details={"fields_found": sorted(found), "key_field_hits": key_hits},
        )

    def _reason(self, detections: list[dict]) -> str:
        if not detections:
            return "No Aadhaar layout fields detected."
        labels = sorted({d["label"] for d in detections})
        return f"Detected layout fields: {', '.join(labels)}."

    def _result(self, *, detections, mass: BeliefMass, reason, mock, status) -> dict:
        return {
            "fields_detected": [d["label"] for d in detections],
            "detections": detections,
            "reason": reason,
            "mock": mock,
            "status": status,
            "belief": mass.to_dict(),
            "_mass": mass,
        }


layout_service = LayoutService()
