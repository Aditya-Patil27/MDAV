from __future__ import annotations

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image, ImageDraw


class OcrLocatorTest(unittest.TestCase):
    def test_locates_only_value_tokens_inside_label_and_value_field(self) -> None:
        from src.ocr_locator import locate_substring_bbox

        image = Image.new("RGB", (180, 50), "white")
        draw = ImageDraw.Draw(image)
        draw.text((12, 15), "Sub-Total", fill="black")
        draw.text((100, 15), "1,346,000", fill="black")
        data = {
            "text": ["Sub-Total", "1,346,000"],
            "conf": ["94", "91"],
            "left": [2, 90],
            "top": [5, 5],
            "width": [70, 65],
            "height": [18, 18],
        }
        fake_tesseract = SimpleNamespace(
            Output=SimpleNamespace(DICT="dict"),
            image_to_data=lambda *args, **kwargs: data,
        )

        with patch.dict(sys.modules, {"pytesseract": fake_tesseract}):
            bbox = locate_substring_bbox(image, [10, 10, 170, 40], "1,346,000")

        self.assertEqual(bbox, [100, 15, 165, 33])

    def test_returns_none_when_value_is_absent(self) -> None:
        from src.ocr_locator import locate_substring_bbox

        data = {
            "text": ["Sub-Total", "9.99"],
            "conf": ["95", "95"],
            "left": [0, 80],
            "top": [0, 0],
            "width": [70, 30],
            "height": [15, 15],
        }
        fake_tesseract = SimpleNamespace(
            Output=SimpleNamespace(DICT="dict"),
            image_to_data=lambda *args, **kwargs: data,
        )
        with patch.dict(sys.modules, {"pytesseract": fake_tesseract}):
            result = locate_substring_bbox(
                Image.new("RGB", (120, 30), "white"),
                [0, 0, 120, 30],
                "1,346,000",
            )
        self.assertIsNone(result)

    def test_returns_none_when_pytesseract_is_unavailable(self) -> None:
        from src.ocr_locator import locate_substring_bbox

        with patch.dict(sys.modules, {"pytesseract": None}):
            result = locate_substring_bbox(
                Image.new("RGB", (20, 20), "white"),
                [0, 0, 20, 20],
                "10.00",
            )
        self.assertIsNone(result)

    def test_returns_none_when_exact_match_has_low_confidence(self) -> None:
        from src.ocr_locator import locate_substring_bbox

        data = {
            "text": ["1,346,000"],
            "conf": ["59"],
            "left": [10],
            "top": [4],
            "width": [60],
            "height": [16],
        }
        fake_tesseract = SimpleNamespace(
            Output=SimpleNamespace(DICT="dict"),
            image_to_data=lambda *args, **kwargs: data,
        )
        with patch.dict(sys.modules, {"pytesseract": fake_tesseract}):
            result = locate_substring_bbox(
                Image.new("RGB", (100, 30), "white"),
                [0, 0, 100, 30],
                "1,346,000",
            )
        self.assertIsNone(result)

    def test_minus_one_confidence_tokens_do_not_sink_a_valid_run(self) -> None:
        from src.ocr_locator import locate_substring_bbox

        # Two-token exact run; Tesseract gave one token conf -1. Mean over all
        # tokens (-1, 90) = 44.5 would wrongly reject; mean over scored tokens
        # (90) must accept.
        data = {
            "text": ["1", "346"],
            "conf": ["-1", "90"],
            "left": [10, 30],
            "top": [4, 4],
            "width": [15, 40],
            "height": [16, 16],
        }
        fake_tesseract = SimpleNamespace(
            Output=SimpleNamespace(DICT="dict"),
            image_to_data=lambda *args, **kwargs: data,
        )
        with patch.dict(sys.modules, {"pytesseract": fake_tesseract}):
            bbox = locate_substring_bbox(
                Image.new("RGB", (120, 30), "white"),
                [0, 0, 120, 30],
                "1 346",
            )
        self.assertEqual(bbox, [10, 4, 70, 20])

    def test_numeric_value_retries_with_psm8_whitelist(self) -> None:
        from src.ocr_locator import locate_substring_bbox

        calls: list[str] = []

        def image_to_data(*args, **kwargs):
            config = kwargs["config"]
            calls.append(config)
            text = "505,000" if config == "--psm 7" else "503,000"
            return {
                "text": [text],
                "conf": ["92"],
                "left": [6],
                "top": [7],
                "width": [80],
                "height": [20],
            }

        fake_tesseract = SimpleNamespace(
            Output=SimpleNamespace(DICT="dict"),
            image_to_data=image_to_data,
        )
        with patch.dict(sys.modules, {"pytesseract": fake_tesseract}):
            result = locate_substring_bbox(
                Image.new("RGB", (120, 40), "white"),
                [10, 5, 110, 35],
                "503,000",
            )

        self.assertEqual(result, [16, 12, 96, 32])
        self.assertEqual(
            calls,
            [
                "--psm 7",
                "--psm 8 -c tessedit_char_whitelist=0123456789,.-",
            ],
        )


if __name__ == "__main__":
    unittest.main()
