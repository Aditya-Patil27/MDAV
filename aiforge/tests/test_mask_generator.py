from __future__ import annotations

import unittest

from src.mask_generator import generate_tamper_mask


class MaskGeneratorTest(unittest.TestCase):
    def test_margin_expands_mask_to_match_feathered_paste(self) -> None:
        # Edited value bbox [40,20,60,30]; paste modifies bbox +/- margin(8),
        # so the mask must be white across the expanded [32,12,68,38] region.
        mask = generate_tamper_mask(100, 50, [40, 20, 60, 30], margin=8)
        self.assertEqual(mask.getpixel((50, 25)), 255)  # center
        self.assertEqual(mask.getpixel((33, 25)), 255)  # inside the margin ring
        self.assertEqual(mask.getpixel((67, 25)), 255)  # inside the margin ring
        self.assertEqual(mask.getpixel((31, 25)), 0)    # just outside expanded box
        self.assertEqual(mask.getpixel((68, 25)), 0)    # exclusive right edge

    def test_default_margin_keeps_tight_bbox(self) -> None:
        mask = generate_tamper_mask(100, 50, [40, 20, 60, 30])
        self.assertEqual(mask.getpixel((50, 25)), 255)
        self.assertEqual(mask.getpixel((33, 25)), 0)  # margin ring stays authentic

    def test_margin_is_clamped_to_image_bounds(self) -> None:
        # bbox near the corner; margin would push past (0,0) -> must clamp.
        mask = generate_tamper_mask(100, 50, [2, 2, 10, 10], margin=8)
        self.assertEqual(mask.getpixel((0, 0)), 255)
        self.assertEqual(mask.size, (100, 50))

    def test_empty_bbox_returns_black_mask(self) -> None:
        mask = generate_tamper_mask(20, 20, [10, 10, 10, 10], margin=8)
        self.assertEqual(mask.getextrema(), (0, 0))  # all black


if __name__ == "__main__":
    unittest.main()
