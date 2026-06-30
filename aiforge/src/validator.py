"""
validator.py — Output integrity and pipeline validation.

Performs validation checks on images, masks, annotations, and metadata entries.
Throws exceptions on failures to halt generation immediately.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from PIL import Image

from src.metadata_writer import MetadataIndex, get_metadata_index

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when generated sample validation fails."""
    pass


def validate_sample(
    image_id: str,
    forged_image_path: Path,
    mask_path: Path,
    annotation_path: Path,
    csv_path: Path,
    expected_text: str,
    expected_width: int,
    expected_height: int,
    metadata_index: MetadataIndex | None = None,
) -> None:
    """Validate all generated files and metadata for a single forgery sample.

    Halts execution by raising ValidationError if any check fails.

    Args:
        image_id: The ID of the forged document.
        forged_image_path: Path to the generated forgery image.
        mask_path: Path to the generated binary tamper mask.
        annotation_path: Path to the generated unified annotation JSON.
        csv_path: Path to the metadata CSV file.
        expected_text: The mutated value expected in the annotation.
        expected_width: Expected width of the output image.
        expected_height: Expected height of the output image.
    """
    # 1. Existence Checks
    if not forged_image_path.exists():
        raise ValidationError(f"Forged image file is missing: {forged_image_path}")
    if not mask_path.exists():
        raise ValidationError(f"Binary mask file is missing: {mask_path}")
    if not annotation_path.exists():
        raise ValidationError(f"Annotation file is missing: {annotation_path}")
    if not csv_path.exists():
        raise ValidationError(f"Metadata CSV is missing: {csv_path}")

    # 2. Dimension Verification
    try:
        with Image.open(forged_image_path) as img:
            w_img, h_img = img.size
        with Image.open(mask_path) as mask:
            w_mask, h_mask = mask.size
    except Exception as exc:
        raise ValidationError(f"Failed to open generated image or mask: {exc}")

    if w_img != expected_width or h_img != expected_height:
        raise ValidationError(
            f"Forged image dimensions {w_img}x{h_img} do not match expected {expected_width}x{expected_height}"
        )
    if w_mask != expected_width or h_mask != expected_height:
        raise ValidationError(
            f"Tamper mask dimensions {w_mask}x{h_mask} do not match expected {expected_width}x{expected_height}"
        )

    # 3. Non-empty Mask Verification
    try:
        with Image.open(mask_path) as mask:
            extrema = mask.convert("L").getextrema()
            # extrema returns (min, max) tuple
            max_val = extrema[1] if extrema else 0
    except Exception as exc:
        raise ValidationError(f"Failed to read mask pixels: {exc}")

    if max_val == 0:
        raise ValidationError("Tamper mask is completely black (no tampered pixels found)")

    # 4. Annotation Verification
    try:
        with annotation_path.open("r", encoding="utf-8") as f:
            ann_data = json.load(f)
    except Exception as exc:
        raise ValidationError(f"Failed to parse annotation JSON: {exc}")

    if ann_data.get("image_id") != image_id:
        raise ValidationError(
            f"Annotation image_id {ann_data.get('image_id')!r} does not match expected {image_id!r}"
        )

    # Find the modified text in fields
    found_text = False
    edited_field_id = ann_data.get("metadata", {}).get("edited_field_id")
    for field in ann_data.get("fields", []):
        if field.get("field_id") == edited_field_id:
            if field.get("text") == expected_text:
                found_text = True
                break
            else:
                raise ValidationError(
                    f"Mutated field text in annotation ({field.get('text')!r}) "
                    f"does not match mutated value ({expected_text!r})"
                )

    if not found_text:
        raise ValidationError(f"Edited field ID {edited_field_id!r} not found in annotation fields")

    # 5. Metadata Row & Duplicate Check
    index = metadata_index or get_metadata_index(csv_path)
    if index.duplicate_ids:
        duplicate_id = sorted(index.duplicate_ids)[0]
        raise ValidationError(f"Duplicate image_id found in metadata.csv: {duplicate_id}")

    row = index.rows_by_id.get(image_id)
    if row is None:
        raise ValidationError(f"Metadata entry for image_id {image_id} was not found in metadata.csv")
    for path_key in ["source_image", "forged_image", "mask_path"]:
        logged_path = Path(row.get(path_key, ""))
        if not logged_path.exists():
            raise ValidationError(
                f"Logged path {path_key} = {logged_path} does not exist on disk"
            )

    logger.debug("Successfully validated generated sample: %s", image_id)
