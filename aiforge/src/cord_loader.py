"""
cord_loader.py — CORD dataset parser.

Converts raw CORD JSON annotations into UnifiedDocument instances.

CORD annotation structure (discovered from file scan):
{
  "gt_parse": {
      "menu": [{"nm": str, "cnt": str, "price": str}],
      "sub_total": {"subtotal_price": str, "service_price": str, "tax_price": str, "etc": str},
      "total": {"total_price": str}
  },
  "meta": {
      "version": str,
      "split": str,
      "image_id": int,
      "image_size": {"width": int, "height": int}
  },
  "valid_line": [{
      "words": [{
          "quad": {"x1":int,"y1":int,"x2":int,"y2":int,"x3":int,"y3":int,"x4":int,"y4":int},
          "text": str,
          "is_key": int,
          "row_id": int
      }],
      # is_key separates label words from the value span used for editing.
      "category": str,     e.g. "menu.price", "total.total_price"
      "group_id": int,
      "sub_group_id": int
  }],
  "roi": {},
  "repeating_symbol": [],
  "dontcare": []
}
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.schema import UnifiedDocument, UnifiedField
from src.utils import resolve_dataset_root

logger = logging.getLogger(__name__)

CORD_LANGUAGE = "ko"
CORD_DOCUMENT_TYPE = "receipt"


def _quad_to_bbox(quad: dict) -> list[int]:
    """Convert CORD quad dict to axis-aligned [x1, y1, x2, y2] bbox.

    Args:
        quad: Dict with keys x1, y1, x2, y2, x3, y3, x4, y4.

    Returns:
        Axis-aligned bounding box [min_x, min_y, max_x, max_y].
    """
    xs = [quad["x1"], quad["x2"], quad["x3"], quad["x4"]]
    ys = [quad["y1"], quad["y2"], quad["y3"], quad["y4"]]
    return [min(xs), min(ys), max(xs), max(ys)]


def _quad_to_polygon(quad: dict) -> list[list[int]]:
    """Convert CORD quad dict to polygon [[x,y], ...].

    Args:
        quad: Dict with keys x1, y1, x2, y2, x3, y3, x4, y4.

    Returns:
        Four-point polygon.
    """
    return [
        [quad["x1"], quad["y1"]],
        [quad["x2"], quad["y2"]],
        [quad["x3"], quad["y3"]],
        [quad["x4"], quad["y4"]],
    ]


def _merge_words(words: list[dict]) -> tuple[str, list[int], list[list[int]]]:
    """Merge all words in a valid_line into a single text, bbox, and polygon.

    Args:
        words: List of word dicts with 'quad' and 'text' keys.

    Returns:
        Tuple of (merged_text, merged_bbox, merged_polygon).
    """
    texts: list[str] = []
    all_xs: list[int] = []
    all_ys: list[int] = []
    polygon: list[list[int]] = []

    for w in words:
        texts.append(w["text"])
        q = w["quad"]
        all_xs.extend([q["x1"], q["x2"], q["x3"], q["x4"]])
        all_ys.extend([q["y1"], q["y2"], q["y3"], q["y4"]])
        polygon.extend(_quad_to_polygon(q))

    merged_text = " ".join(texts)
    bbox = [min(all_xs), min(all_ys), max(all_xs), max(all_ys)]
    return merged_text, bbox, polygon


def _parse_cord_json(
    ann_path: Path,
    image_id: str,
    split: str,
    image_path: Path,
) -> UnifiedDocument | None:
    """Parse a single CORD annotation file into a UnifiedDocument.

    Args:
        ann_path: Path to the JSON annotation file.
        image_id: Globally unique image identifier.
        split: Dataset split name.
        image_path: Path to the corresponding image.

    Returns:
        UnifiedDocument or None if the file cannot be parsed.
    """
    try:
        with ann_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load CORD annotation %s: %s", ann_path, exc)
        return None

    meta = data.get("meta", {})
    image_size = meta.get("image_size", {})
    width = image_size.get("width", 0)
    height = image_size.get("height", 0)

    fields: list[UnifiedField] = []

    for line_idx, line in enumerate(data.get("valid_line", [])):
        words = line.get("words", [])
        if not words:
            continue

        category = line.get("category", "unknown")
        group_id = line.get("group_id", 0)
        sub_group_id = line.get("sub_group_id", 0)

        merged_text, bbox, polygon = _merge_words(words)

        if not merged_text.strip():
            continue

        key_words = [word for word in words if word.get("is_key", 0)]
        value_words = [word for word in words if not word.get("is_key", 0)]
        label_text = _merge_words(key_words)[0] if key_words else ""
        value_text = merged_text
        if value_words:
            value_text, bbox, polygon = _merge_words(value_words)

        field = UnifiedField(
            field_id=f"{image_id}_line{line_idx}",
            label=category,
            text=merged_text,
            bbox=bbox,
            polygon=polygon,
            confidence=1.0,
            extra={
                "group_id": group_id,
                "sub_group_id": sub_group_id,
                "word_count": len(words),
                "is_key": any(w.get("is_key", 0) for w in words),
                "value_text": value_text,
                "label_text": label_text,
                "value_bbox_source": (
                    "cord_is_key" if value_words and value_text.strip() else ""
                ),
            },
        )
        fields.append(field)

    return UnifiedDocument(
        image_id=image_id,
        dataset="CORD",
        split=split,
        language=CORD_LANGUAGE,
        document_type=CORD_DOCUMENT_TYPE,
        width=width,
        height=height,
        image_path=image_path,
        fields=fields,
        metadata={
            "source_annotation": str(ann_path),
            "gt_parse": data.get("gt_parse", {}),
            "cord_meta": meta,
        },
    )


def load_cord(splits: list[str] | None = None) -> list[UnifiedDocument]:
    """Load CORD dataset across the specified splits.

    Args:
        splits: List of split names to load. Defaults to ["train", "validation", "test"].

    Returns:
        List of UnifiedDocument instances.
    """
    if splits is None:
        splits = ["train", "validation", "test"]

    dataset_root = resolve_dataset_root() / "CORD"
    documents: list[UnifiedDocument] = []

    for split in splits:
        split_dir = dataset_root / split
        ann_dir = split_dir / "annotations"
        img_dir = split_dir / "images"

        if not ann_dir.exists():
            logger.warning("CORD split '%s' annotation dir not found: %s", split, ann_dir)
            continue

        ann_files = sorted(ann_dir.glob("cord_*.json"))
        logger.info("CORD %s: found %d annotation files", split, len(ann_files))

        for ann_path in ann_files:
            stem = ann_path.stem  # e.g. "cord_000042"
            image_id = f"{stem}_{split}"
            image_path = img_dir / f"{stem}.png"

            if not image_path.exists():
                logger.warning("CORD image missing: %s — skipping", image_path)
                continue

            doc = _parse_cord_json(ann_path, image_id, split, image_path)
            if doc is not None:
                documents.append(doc)

    logger.info("CORD: loaded %d documents total", len(documents))
    return documents
