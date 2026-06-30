"""
schema.py — Unified dataclasses for the AIForge dataset pipeline.

Every dataset loader converts raw annotations into these types.
All downstream modules consume ONLY these types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class UnifiedField:
    """Represents one annotated text field in a document."""

    field_id: str
    label: str                          # original category/label string
    text: str                           # OCR text
    bbox: list[int]                     # [x1, y1, x2, y2] absolute pixels
    polygon: list[list[int]]            # [[x,y], ...] quad or contour (may be empty)
    confidence: float = 1.0            # OCR confidence (1.0 if not provided)
    extra: dict[str, Any] = field(default_factory=dict)  # dataset-specific metadata


@dataclass
class UnifiedDocument:
    """One document from any of the four supported datasets."""

    image_id: str                       # globally unique, e.g. "cord_000042_train"
    dataset: str                        # "CORD" | "FUNSD" | "SROIE" | "XFUND"
    split: str                          # "train" | "validation" | "test" | "eval"
    language: str                       # ISO 639-1 code, e.g. "ko", "en", "de"
    document_type: str                  # "receipt" | "form"
    width: int
    height: int
    image_path: Path                    # absolute path to the source image
    fields: list[UnifiedField]          # all annotated fields
    metadata: dict[str, Any] = field(default_factory=dict)  # raw source metadata


# ──────────────────────────────────────────────
# Label priority mapping for field selection
# ──────────────────────────────────────────────

#: Priority table: lower number = higher priority (selected first).
#: Keys are lower-cased substrings matched against UnifiedField.label.
FIELD_PRIORITY: dict[str, int] = {
    "total_price":      1,
    "total":            1,
    "grand_total":      1,
    "subtotal":         2,
    "sub_total":        2,
    "price":            2,
    "menu.price":       2,
    "tax":              3,
    "tax_price":        3,
    "discount":         3,
    "qty":              4,
    "cnt":              4,
    "quantity":         4,
    "menu.cnt":         4,
    "date":             5,
    "invoice":          6,
    "invoice_no":       6,
    "invoice_id":       6,
    "receipt_id":       7,
    "doc_id":           8,
    "document_id":      8,
    "answer":           9,    # FUNSD answers (numeric preferred)
    "numeric":          9,
    "amount":           2,
}

DEFAULT_PRIORITY: int = 10
