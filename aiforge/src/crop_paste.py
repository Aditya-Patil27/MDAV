"""
crop_paste.py — Composite edited crop region back into the original document image.

Extracts only the target edited field region from the edited crop and pastes
it back into the original full-size image to ensure no other pixels change.
"""

from __future__ import annotations

import logging
import os

from PIL import Image, ImageDraw, ImageFilter

logger = logging.getLogger(__name__)


def paste_crop_back(
    original_img: Image.Image,
    edited_crop: Image.Image,
    bbox: list[int],
    crop_box: tuple[int, int, int, int],
    margin: int | None = None,
    blur_radius: float | None = None,
) -> Image.Image:
    """Feather the edited field region back into the full document."""
    if margin is None:
        margin = int(os.environ.get("FLUX_MASK_MARGIN", "8"))
    if blur_radius is None:
        blur_radius = float(os.environ.get("PASTE_FEATHER_RADIUS", "3"))
    if margin < 0 or blur_radius < 0:
        raise ValueError("margin and blur_radius must be non-negative")

    x1, y1, x2, y2 = bbox
    crop_x1, crop_y1, crop_x2, crop_y2 = crop_box
    expected_size = (crop_x2 - crop_x1, crop_y2 - crop_y1)
    if edited_crop.size != expected_size:
        raise ValueError(
            f"Edited crop size {edited_crop.size} does not match crop box size {expected_size}"
        )

    edited_layer = original_img.copy()
    edited_layer.paste(edited_crop.convert(original_img.mode), (crop_x1, crop_y1))

    mask_x1 = max(0, x1 - margin)
    mask_y1 = max(0, y1 - margin)
    mask_x2 = min(original_img.width, x2 + margin)
    mask_y2 = min(original_img.height, y2 + margin)
    if mask_x2 <= mask_x1 or mask_y2 <= mask_y1:
        raise ValueError(f"Expanded paste bbox has no area: {bbox!r}")

    paste_mask = Image.new("L", original_img.size, 0)
    ImageDraw.Draw(paste_mask).rectangle(
        (mask_x1, mask_y1, mask_x2 - 1, mask_y2 - 1),
        fill=255,
    )
    if blur_radius:
        paste_mask = paste_mask.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    result_img = Image.composite(edited_layer, original_img, paste_mask)

    logger.debug(
        "Feathered field region %s back into original image of size %s",
        (x1, y1, x2, y2),
        original_img.size,
    )
    return result_img
