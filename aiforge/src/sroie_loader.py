"""
sroie_loader.py — SROIE dataset parser.

Converts raw SROIE annotations into UnifiedDocument instances.

SROIE annotation structure (discovered from file scan):

  box/{ID}.txt — OCR boxes, one word per line:
      x1,y1,x2,y2,x3,y3,x4,y4,text
      (8 coordinates = quadrilateral, last token = text; commas in text possible)

  entities/{ID}.txt — Structured entities, JSON format:
      {"company": str, "date": str, "address": str, "total": str}

  img/{ID}.jpg — Receipt image

Splits: train/ (has box/, entities/, img/), eval/, test/
Language: English/Malay (we use "en" as primary)
Document type: receipt
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from PIL import Image

from src.schema import UnifiedDocument, UnifiedField
from src.utils import resolve_dataset_root

logger = logging.getLogger(__name__)

SROIE_LANGUAGE = "en"
SROIE_DOCUMENT_TYPE = "receipt"


def _parse_box_line(line: str) -> tuple[list[int], list[list[int]], str] | None:
    """Parse one line of a SROIE box file.

    Format: x1,y1,x2,y2,x3,y3,x4,y4,text
    Note: text may contain commas, so we split on the first 8 commas only.

    Args:
        line: Raw line string from the box file.

    Returns:
        Tuple of (axis_bbox, polygon, text) or None if unparseable.
    """
    line = line.strip()
    if not line:
        return None

    parts = line.split(",", 8)  # at most 8 splits → 9 parts
    if len(parts) < 9:
        # Malformed — try 8 coords + text
        return None

    try:
        coords = [int(p) for p in parts[:8]]
    except ValueError:
        return None

    text = parts[8].strip()
    xs = coords[0::2]  # x1,x3,x5,x7 — wait, format is x1,y1,x2,y2,...
    # Actual order: x1,y1,x2,y2,x3,y3,x4,y4
    xs = [coords[0], coords[2], coords[4], coords[6]]
    ys = [coords[1], coords[3], coords[5], coords[7]]

    polygon = [[coords[i * 2], coords[i * 2 + 1]] for i in range(4)]
    bbox = [min(xs), min(ys), max(xs), max(ys)]
    return bbox, polygon, text


def _parse_entities(entities_path: Path) -> dict[str, str]:
    """Parse SROIE entities file.

    Args:
        entities_path: Path to the entities JSON file.

    Returns:
        Dict with keys company, date, address, total.
    """
    try:
        with entities_path.open("r", encoding="utf-8", errors="replace") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to parse SROIE entities %s: %s", entities_path, exc)
        return {}


def _get_image_size(image_path: Path) -> tuple[int, int]:
    """Return (width, height) without loading pixel data.

    Args:
        image_path: Path to image file.

    Returns:
        (width, height).
    """
    with Image.open(image_path) as img:
        return img.size


def _entity_label(text: str, entities: dict[str, str]) -> str:
    """Match a text string against SROIE entity values to get a semantic label.

    Args:
        text: OCR text of the field.
        entities: Parsed entity dict.

    Returns:
        Label string (e.g. "total", "date", "company", "address", "other").
    """
    for key, val in entities.items():
        if val and text.strip() in val:
            return key
    return "other"


def _parse_sroie_sample(
    doc_id: str,
    box_path: Path,
    entities_path: Path | None,
    image_path: Path,
    split: str,
) -> UnifiedDocument | None:
    """Parse a single SROIE sample into a UnifiedDocument.

    Args:
        doc_id: Globally unique document identifier.
        box_path: Path to the .txt box annotation file.
        entities_path: Path to the entities .txt file (may be None).
        image_path: Path to the image file.
        split: Dataset split name.

    Returns:
        UnifiedDocument or None on error.
    """
    # Load boxes
    try:
        box_lines = box_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        logger.warning("Failed to read SROIE box file %s: %s", box_path, exc)
        return None

    # Load entities (optional)
    entities: dict[str, str] = {}
    if entities_path and entities_path.exists():
        entities = _parse_entities(entities_path)

    width, height = _get_image_size(image_path)

    fields: list[UnifiedField] = []
    for line_idx, line in enumerate(box_lines):
        parsed = _parse_box_line(line)
        if parsed is None:
            continue
        bbox, polygon, text = parsed
        if not text:
            continue

        label = _entity_label(text, entities)

        field = UnifiedField(
            field_id=f"{doc_id}_word{line_idx}",
            label=label,
            text=text,
            bbox=bbox,
            polygon=polygon,
            confidence=1.0,
            extra={
                "line_index": line_idx,
                "entities": entities,
            },
        )
        fields.append(field)

    # Also add entity-level fields so the selector can find totals/dates directly
    for entity_key, entity_val in entities.items():
        if not entity_val:
            continue
        # Find first word field that matches
        matched = next(
            (f for f in fields if entity_val.strip().startswith(f.text.strip())),
            None,
        )
        if matched:
            # Elevate label
            matched.label = entity_key
        else:
            # Create a synthetic field at bbox (0,0,0,0) — placeholder
            fields.append(
                UnifiedField(
                    field_id=f"{doc_id}_entity_{entity_key}",
                    label=entity_key,
                    text=entity_val,
                    bbox=[0, 0, 0, 0],
                    polygon=[],
                    confidence=1.0,
                    extra={"synthetic": True, "entities": entities},
                )
            )

    # Filter out synthetic fields with zero bbox from primary selection
    # (they are kept but field_selector must handle them)

    return UnifiedDocument(
        image_id=doc_id,
        dataset="SROIE",
        split=split,
        language=SROIE_LANGUAGE,
        document_type=SROIE_DOCUMENT_TYPE,
        width=width,
        height=height,
        image_path=image_path,
        fields=fields,
        metadata={
            "source_box": str(box_path),
            "source_entities": str(entities_path) if entities_path else None,
            "entities": entities,
        },
    )


def load_sroie(splits: list[str] | None = None) -> list[UnifiedDocument]:
    """Load SROIE dataset across the specified splits.

    Args:
        splits: List of split names. Defaults to ["train", "eval", "test"].

    Returns:
        List of UnifiedDocument instances.
    """
    if splits is None:
        splits = ["train", "eval", "test"]

    dataset_root = resolve_dataset_root() / "SROIE"
    documents: list[UnifiedDocument] = []

    for split in splits:
        split_dir = dataset_root / split
        box_dir = split_dir / "box"
        entities_dir = split_dir / "entities"
        img_dir = split_dir / "img"

        if not box_dir.exists():
            logger.warning("SROIE split '%s' box dir not found: %s", split, box_dir)
            continue

        box_files = sorted(box_dir.glob("*.txt"))
        logger.info("SROIE %s: found %d box files", split, len(box_files))

        for box_path in box_files:
            stem = box_path.stem  # e.g. "X00016469612"
            doc_id = f"sroie_{stem}_{split}"

            entities_path = entities_dir / f"{stem}.txt"
            image_path = img_dir / f"{stem}.jpg"

            if not image_path.exists():
                logger.warning("SROIE image missing: %s — skipping", image_path)
                continue

            doc = _parse_sroie_sample(
                doc_id=doc_id,
                box_path=box_path,
                entities_path=entities_path if entities_dir.exists() else None,
                image_path=image_path,
                split=split,
            )
            if doc is not None:
                documents.append(doc)

    logger.info("SROIE: loaded %d documents total", len(documents))
    return documents
