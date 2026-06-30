"""
field_selector.py — Priority-based field selection for editing.

For every UnifiedDocument, select exactly ONE UnifiedField to be
AI-inpainted. Selection follows a strict priority order:

  Priority 1 — Monetary totals        (total, grand_total, total_price)
  Priority 2 — Prices / amounts       (price, subtotal, amount, discount)
  Priority 3 — Taxes                  (tax, tax_price)
  Priority 4 — Quantities             (qty, cnt, quantity)
  Priority 5 — Dates                  (date)
  Priority 6 — Invoice numbers        (invoice)
  Priority 7 — Receipt IDs            (receipt_id)
  Priority 8 — Document IDs           (doc_id, document_id)
  Priority 9 — Numeric / answer text  (any answer with digit content)
  Priority 10 — Remaining OCR fields

Within the same priority tier, fields with longer non-empty numeric
content are preferred (more informative edits).

Additional hard constraints:
- The field bbox must have positive area (non-zero width and height).
- The field text must be non-empty after stripping whitespace.
- Alphabetic-only text is deprioritised (mutation is a no-op for pure alpha).
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from src.schema import FIELD_PRIORITY, DEFAULT_PRIORITY, UnifiedDocument, UnifiedField

logger = logging.getLogger(__name__)

# Regex that matches at least one digit anywhere in the text
_HAS_DIGIT = re.compile(r"\d")


def _label_priority(label: str) -> int:
    """Map a field label string to its integer priority.

    Lower value = higher priority.

    Args:
        label: The field's label string (case-insensitive match).

    Returns:
        Integer priority.
    """
    label_lower = label.lower()
    # Exact match first
    if label_lower in FIELD_PRIORITY:
        return FIELD_PRIORITY[label_lower]
    # Substring match
    for key, prio in FIELD_PRIORITY.items():
        if key in label_lower:
            return prio
    return DEFAULT_PRIORITY


def _has_valid_bbox(field: UnifiedField) -> bool:
    """Return True if the field has a positive-area bounding box.

    Args:
        field: UnifiedField to check.

    Returns:
        True if bbox is non-degenerate.
    """
    if len(field.bbox) != 4:
        return False
    x1, y1, x2, y2 = field.bbox
    return (x2 > x1) and (y2 > y1)


def _score(field: UnifiedField) -> tuple[int, int]:
    """Compute a (priority, tiebreak) sort key for a field.

    Lower tuple = better candidate.

    Args:
        field: UnifiedField to score.

    Returns:
        (priority, negative_digit_count) — negative so more digits = lower value = earlier.
    """
    prio = _label_priority(field.label)
    # Tiebreak: prefer fields that contain more digit characters
    digit_count = sum(1 for c in field.text if c.isdigit())
    return (prio, -digit_count)


def select_field(doc: UnifiedDocument) -> Optional[UnifiedField]:
    """Select the best single field from a document for AI editing.

    Args:
        doc: UnifiedDocument to select from.

    Returns:
        The selected UnifiedField, or None if no eligible field exists.
    """
    candidates = [
        f for f in doc.fields
        if f.text.strip()             # non-empty text
        and _has_valid_bbox(f)        # non-degenerate bbox
    ]

    if not candidates:
        logger.debug(
            "Document %s: no eligible fields (total fields=%d)",
            doc.image_id,
            len(doc.fields),
        )
        return None

    # Sort by (priority, tiebreak) ascending
    candidates.sort(key=_score)

    best = candidates[0]
    logger.debug(
        "Document %s: selected field '%s' (label=%s, priority=%d, text=%r)",
        doc.image_id,
        best.field_id,
        best.label,
        _label_priority(best.label),
        best.text[:40],
    )
    return best


def select_fields_for_variants(
    doc: UnifiedDocument,
    num_variants: int,
) -> list[UnifiedField]:
    """Rank fields for variants, preferring a different exact label per variant."""
    if num_variants <= 0:
        return []

    candidates = [
        field
        for field in doc.fields
        if field.text.strip() and _has_valid_bbox(field)
    ]
    candidates.sort(key=_score)
    if not candidates:
        return []

    selected: list[UnifiedField] = []
    assigned_labels: set[str] = set()
    for field in candidates:
        if field.label in assigned_labels:
            continue
        selected.append(field)
        assigned_labels.add(field.label)
        if len(selected) == num_variants:
            return selected

    fallback_index = 0
    while len(selected) < num_variants:
        selected.append(candidates[fallback_index % len(candidates)])
        fallback_index += 1
    return selected


def select_fields_batch(
    documents: list[UnifiedDocument],
) -> dict[str, Optional[UnifiedField]]:
    """Select one field per document for a batch of documents.

    Args:
        documents: List of UnifiedDocument instances.

    Returns:
        Dict mapping image_id → selected UnifiedField (or None).
    """
    result: dict[str, Optional[UnifiedField]] = {}
    for doc in documents:
        result[doc.image_id] = select_field(doc)
    skipped = sum(1 for v in result.values() if v is None)
    if skipped:
        logger.info(
            "Field selection: %d/%d documents had no eligible field",
            skipped,
            len(documents),
        )
    return result
