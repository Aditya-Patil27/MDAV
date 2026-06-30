"""
crop_generator.py — Expanded crop generator with safety clamping.

Calculates bounding boxes for document crops around target fields
using 50% relative padding (minimum 150px) clamped to image dimensions.
"""

from __future__ import annotations

import logging
from typing import Tuple

logger = logging.getLogger(__name__)


def calculate_crop_box(
    bbox: list[int],
    img_width: int,
    img_height: int,
) -> Tuple[int, int, int, int]:
    """Calculate the expanded crop box coordinates around a target bounding box.

    Args:
        bbox: Target bounding box [x1, y1, x2, y2].
        img_width: Original image width.
        img_height: Original image height.

    Returns:
        Expanded crop box coordinates (crop_x1, crop_y1, crop_x2, crop_y2).
    """
    x1, y1, x2, y2 = bbox
    w = x2 - x1
    h = y2 - y1

    # 50% padding, minimum 150 pixels
    pad_w = max(int(w * 0.5), 150)
    pad_h = max(int(h * 0.5), 150)

    crop_x1 = max(0, x1 - pad_w)
    crop_y1 = max(0, y1 - pad_h)
    crop_x2 = min(img_width, x2 + pad_w)
    crop_y2 = min(img_height, y2 + pad_h)

    # Ensure box is valid (e.g. if original bbox was somehow malformed)
    if crop_x2 <= crop_x1:
        crop_x2 = min(img_width, crop_x1 + 1)
    if crop_y2 <= crop_y1:
        crop_y2 = min(img_height, crop_y1 + 1)

    logger.debug(
        "Crop box calculated: target %s -> crop %s (padded by w=%d, h=%d)",
        (x1, y1, x2, y2),
        (crop_x1, crop_y1, crop_x2, crop_y2),
        pad_w,
        pad_h,
    )

    return crop_x1, crop_y1, crop_x2, crop_y2
