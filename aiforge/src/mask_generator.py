"""
mask_generator.py — Generate binary tamper masks for modified documents.

Mask values: 0 (authentic), 255 (tampered).
Mask size exactly matches original image dimensions.
"""

from __future__ import annotations

import logging
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)


def generate_tamper_mask(
    width: int,
    height: int,
    bbox: list[int],
    margin: int = 0,
) -> Image.Image:
    """Generate a binary tamper mask where only the modified region is white (255).

    Args:
        width: Original image width.
        height: Original image height.
        bbox: Bounding box of the edited field [x1, y1, x2, y2].
        margin: Pixels to expand the bbox on every side. **Pass the same margin
            that ``paste_crop_back`` uses** so the label covers the pixels the
            feathered paste actually modifies (the value bbox + margin), not just
            the tight bbox -- otherwise the ~margin-px ring around each edit is
            tampered but labelled authentic, which mis-trains the segmenter.

    Returns:
        PIL Image in 'L' (8-bit grayscale) mode.
    """
    x1, y1, x2, y2 = bbox

    # Create a black image
    mask = Image.new("L", (width, height), 0)

    if x2 <= x1 or y2 <= y1:
        logger.warning("Skipping empty tamper mask bbox: %s", bbox)
        return mask

    # Expand by the paste margin, clamped to image bounds. This matches the solid
    # region of the paste mask in crop_paste.paste_crop_back exactly.
    ex1 = max(0, x1 - margin)
    ey1 = max(0, y1 - margin)
    ex2 = min(width, x2 + margin)
    ey2 = min(height, y2 + margin)

    # PIL rectangles include the right/bottom edge; bboxes in this project use
    # crop semantics where x2/y2 are exclusive.
    draw = ImageDraw.Draw(mask)
    draw.rectangle([ex1, ey1, ex2 - 1, ey2 - 1], fill=255)

    logger.debug(
        "Generated tamper mask of size %dx%d with white rectangle at %s (margin=%d)",
        width,
        height,
        (ex1, ey1, ex2, ey2),
        margin,
    )
    return mask
