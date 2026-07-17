"""Conservative document-type and side inference from existing evidence.

Layout is preferred when available. OCR fields and keywords provide a fallback
so an offline layout model does not reduce a recognizable Aadhaar or PAN to the
generic ``other`` label. Low-confidence signals are preserved as a possible
type and never force document-specific validation rules.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class DocumentContext:
    document_type: str = "unknown"
    side: str = "unknown"
    confidence: float = 0.0
    source: str = "unknown"
    possible_type: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


_TYPE_ALIASES = {
    "aadhar": "aadhaar",
    "aadhaar": "aadhaar",
    "pan": "pan",
    "passport": "passport",
    "license": "driving_licence",
    "licence": "driving_licence",
    "driving": "driving_licence",
}


def infer_document_context(
    *,
    filename: str,
    raw_text: str,
    extracted_fields: dict,
    layout_result: dict | None = None,
) -> DocumentContext:
    """Infer type, side, confidence, and provenance without forcing a guess."""
    layout_result = layout_result or {}
    text = (raw_text or "").lower()
    filename_text = Path(filename or "").name.lower()
    fields = extracted_fields or {}
    layout_fields = set(layout_result.get("fields_detected") or [])

    candidates: dict[str, tuple[float, str]] = {}

    def offer(kind: str, score: float, source: str) -> None:
        current = candidates.get(kind)
        if current is None or score > current[0]:
            candidates[kind] = (score, source)

    # The layout checkpoint is Aadhaar-specific, but one spurious box must not
    # override a deterministic PAN identifier from OCR. Multiple key fields are
    # strong Aadhaar evidence; a lone field is only a weak type hint.
    layout_key_hits = len(layout_fields & {"aadhaar_number", "name", "dob", "address"})
    if layout_key_hits >= 2:
        offer("aadhaar", 0.95, "layout")
    elif layout_key_hits == 1:
        offer("aadhaar", 0.76, "layout")

    if "aadhaar" in fields:
        score = 0.78
        if any(token in text for token in ("aadhaar", "aadhar", "government of india", "uidai")):
            score = 0.90
        offer("aadhaar", score, "ocr")
    elif any(token in text for token in ("aadhaar", "aadhar", "unique identification authority")):
        offer("aadhaar", 0.72, "ocr")

    if "pan" in fields:
        offer("pan", 0.90, "ocr")
    elif "income tax department" in text and "permanent account number" in text:
        offer("pan", 0.80, "ocr")

    if "passport" in text and any(token in text for token in ("republic of india", "passport no")):
        offer("passport", 0.78, "ocr")
    if any(token in text for token in ("driving licence", "driving license")):
        offer("driving_licence", 0.78, "ocr")

    for token, kind in _TYPE_ALIASES.items():
        if token in filename_text:
            offer(kind, 0.60, "filename")

    if not candidates:
        return DocumentContext()

    best_type, (confidence, source) = max(
        candidates.items(), key=lambda item: item[1][0]
    )
    if confidence < 0.65:
        return DocumentContext(
            confidence=round(confidence, 4),
            source=source,
            possible_type=best_type,
        )

    side = _infer_side(best_type, text, layout_fields)
    return DocumentContext(
        document_type=best_type,
        side=side,
        confidence=round(confidence, 4),
        source=source,
        possible_type=best_type,
    )


def _infer_side(document_type: str, text: str, layout_fields: set[str]) -> str:
    if document_type != "aadhaar":
        return "unknown"

    front_layout = bool(layout_fields & {"name", "dob", "gender"})
    back_layout = "address" in layout_fields
    if front_layout and back_layout:
        return "combined"
    if front_layout:
        return "front"
    if back_layout:
        return "back"

    front_text = any(
        token in text
        for token in ("date of birth", "dob", "year of birth", "male", "female")
    )
    back_text = any(
        token in text
        for token in ("address", "mera aadhaar", "help@uidai.gov.in")
    )
    if front_text and back_text:
        return "combined"
    if front_text:
        return "front"
    if back_text:
        return "back"
    return "unknown"
