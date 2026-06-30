"""
funsd_loader.py — FUNSD dataset parser.

Converts raw FUNSD JSON annotations into UnifiedDocument instances.

FUNSD annotation structure (discovered from file scan):
{
  "id": str,
  "words": [str, ...],            # flat list of all word strings
  "bboxes": [[x1,y1,x2,y2], ...], # one bbox per word
  "ner_tags": [int, ...]           # one NER tag per word
}

NER tag scheme:
  0 = O       (outside / non-entity)
  1 = B-HEADER
  2 = I-HEADER
  3 = B-QUESTION
  4 = I-QUESTION
  5 = B-ANSWER
  6 = I-ANSWER

Strategy:
  Group consecutive words with the same entity span (B- starts a new group,
  I- continues) into a single UnifiedField with merged text and merged bbox.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from PIL import Image

from src.schema import UnifiedDocument, UnifiedField
from src.utils import resolve_dataset_root

logger = logging.getLogger(__name__)

FUNSD_LANGUAGE = "en"
FUNSD_DOCUMENT_TYPE = "form"

# NER tag → label string
_TAG_LABELS: dict[int, str] = {
    0: "O",
    1: "B-HEADER",
    2: "I-HEADER",
    3: "B-QUESTION",
    4: "I-QUESTION",
    5: "B-ANSWER",
    6: "I-ANSWER",
}

# Tags that begin a new entity span
_BEGIN_TAGS: frozenset[int] = frozenset({1, 3, 5})
# Tags that continue a span (also used to identify tag type)
_CONTINUE_TAGS: frozenset[int] = frozenset({2, 4, 6})
# O tag — not part of any entity
_O_TAG: int = 0


def _merge_bbox(bboxes: list[list[int]]) -> list[int]:
    """Compute axis-aligned union of a list of [x1,y1,x2,y2] bboxes.

    Args:
        bboxes: List of bounding boxes.

    Returns:
        Merged [x1, y1, x2, y2].
    """
    x1 = min(b[0] for b in bboxes)
    y1 = min(b[1] for b in bboxes)
    x2 = max(b[2] for b in bboxes)
    y2 = max(b[3] for b in bboxes)
    return [x1, y1, x2, y2]


def _bbox_to_polygon(bbox: list[int]) -> list[list[int]]:
    """Convert [x1,y1,x2,y2] to four-corner polygon.

    Args:
        bbox: Axis-aligned bounding box.

    Returns:
        Four-point polygon [[x,y], ...].
    """
    x1, y1, x2, y2 = bbox
    return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]


def _get_image_size(image_path: Path) -> tuple[int, int]:
    """Return (width, height) without loading full pixel data.

    Args:
        image_path: Path to image file.

    Returns:
        (width, height).
    """
    with Image.open(image_path) as img:
        return img.size


def _parse_funsd_json(
    ann_path: Path,
    image_id: str,
    split: str,
    image_path: Path,
) -> UnifiedDocument | None:
    """Parse a single FUNSD annotation file into a UnifiedDocument.

    Consecutive words with the same entity type (B-/I-) are merged into
    a single UnifiedField.  'O'-tagged words are also grouped (label "O")
    so no token is discarded.

    Args:
        ann_path: Path to the JSON annotation file.
        image_id: Globally unique identifier.
        split: Dataset split name.
        image_path: Path to the corresponding image.

    Returns:
        UnifiedDocument or None on parse error.
    """
    try:
        with ann_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load FUNSD annotation %s: %s", ann_path, exc)
        return None

    words: list[str] = data.get("words", [])
    bboxes: list[list[int]] = data.get("bboxes", [])
    ner_tags: list[int] = data.get("ner_tags", [])

    n = len(words)
    if n == 0 or n != len(bboxes) or n != len(ner_tags):
        logger.warning("FUNSD %s: token count mismatch (words=%d, bboxes=%d, tags=%d)",
                       ann_path.name, n, len(bboxes), len(ner_tags))
        return None

    width, height = _get_image_size(image_path)

    fields: list[UnifiedField] = []

    # Group tokens into spans
    span_words: list[str] = []
    span_bboxes: list[list[int]] = []
    span_tag: int = _O_TAG
    span_start: int = 0

    def flush_span(span_idx: int) -> None:
        """Emit a UnifiedField for the current accumulated span."""
        if not span_words:
            return
        merged_text = " ".join(span_words)
        merged_bbox = _merge_bbox(span_bboxes)
        label = _TAG_LABELS.get(span_tag, "O")
        field = UnifiedField(
            field_id=f"{image_id}_span{span_idx}",
            label=label,
            text=merged_text,
            bbox=merged_bbox,
            polygon=_bbox_to_polygon(merged_bbox),
            confidence=1.0,
            extra={
                "ner_tag": span_tag,
                "token_count": len(span_words),
                "token_bboxes": list(span_bboxes),
            },
        )
        fields.append(field)

    field_idx = 0
    for i, (word, bbox, tag) in enumerate(zip(words, bboxes, ner_tags)):
        is_begin = tag in _BEGIN_TAGS
        is_o = tag == _O_TAG

        if is_begin or is_o:
            # Flush previous span
            if span_words:
                flush_span(field_idx)
                field_idx += 1
                span_words = []
                span_bboxes = []
            span_tag = tag
            span_start = i

        span_words.append(word)
        span_bboxes.append(bbox)

    # Flush final span
    if span_words:
        flush_span(field_idx)

    doc_id = data.get("id", ann_path.stem)

    return UnifiedDocument(
        image_id=image_id,
        dataset="FUNSD",
        split=split,
        language=FUNSD_LANGUAGE,
        document_type=FUNSD_DOCUMENT_TYPE,
        width=width,
        height=height,
        image_path=image_path,
        fields=fields,
        metadata={
            "source_annotation": str(ann_path),
            "funsd_doc_id": doc_id,
        },
    )


def load_funsd(splits: list[str] | None = None) -> list[UnifiedDocument]:
    """Load FUNSD dataset across the specified splits.

    Args:
        splits: List of split names. Defaults to ["train", "test"].

    Returns:
        List of UnifiedDocument instances.
    """
    if splits is None:
        splits = ["train", "test"]

    dataset_root = resolve_dataset_root() / "FUNSD"
    documents: list[UnifiedDocument] = []

    for split in splits:
        split_dir = dataset_root / split
        ann_dir = split_dir / "annotations"
        img_dir = split_dir / "images"

        if not ann_dir.exists():
            logger.warning("FUNSD split '%s' annotation dir not found: %s", split, ann_dir)
            continue

        ann_files = sorted(ann_dir.glob("funsd_*.json"))
        logger.info("FUNSD %s: found %d annotation files", split, len(ann_files))

        for ann_path in ann_files:
            stem = ann_path.stem  # e.g. "funsd_000042"
            image_id = f"{stem}_{split}"
            image_path = img_dir / f"{stem}.png"

            if not image_path.exists():
                logger.warning("FUNSD image missing: %s — skipping", image_path)
                continue

            doc = _parse_funsd_json(ann_path, image_id, split, image_path)
            if doc is not None:
                documents.append(doc)

    logger.info("FUNSD: loaded %d documents total", len(documents))
    return documents
