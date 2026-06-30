from __future__ import annotations

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from src.ocr_verifier import verify_edited_region_text


class OcrVerifierTest(unittest.TestCase):
    def test_numeric_value_accepts_exact_psm8_fallback(self) -> None:
        calls: list[str] = []

        def image_to_string(*args, **kwargs):
            config = kwargs["config"]
            calls.append(config)
            return "505,000" if config == "--psm 7" else "503,000"

        fake_tesseract = SimpleNamespace(image_to_string=image_to_string)
        with patch.dict(sys.modules, {"pytesseract": fake_tesseract}):
            result = verify_edited_region_text(
                Image.new("RGB", (120, 40), "white"),
                [0, 0, 120, 40],
                "503,000",
                "501,000",
            )

        self.assertTrue(result)
        self.assertEqual(
            calls,
            [
                "--psm 7",
                "--psm 8 -c tessedit_char_whitelist=0123456789,.-",
            ],
        )

    def test_value_inside_a_longer_number_is_not_accepted(self) -> None:
        # OCR reads '1503000'; expecting '503000' must NOT verify (the old
        # substring check wrongly accepted this).
        fake = SimpleNamespace(image_to_string=lambda *a, **k: "1503000")
        with patch.dict(sys.modules, {"pytesseract": fake}):
            result = verify_edited_region_text(
                Image.new("RGB", (120, 40), "white"),
                [0, 0, 120, 40],
                "503000",
                "501000",
            )
        self.assertFalse(result)

    def test_value_with_separator_noise_is_accepted(self) -> None:
        # Expected '503000', OCR renders it with a comma + surrounding text.
        fake = SimpleNamespace(image_to_string=lambda *a, **k: "Total: 503,000\n")
        with patch.dict(sys.modules, {"pytesseract": fake}):
            result = verify_edited_region_text(
                Image.new("RGB", (120, 40), "white"),
                [0, 0, 120, 40],
                "503000",
                "501000",
            )
        self.assertTrue(result)


    def test_changed_mode_accepts_a_different_value(self) -> None:
        # FLUX rendered a different plausible number (not the exact expected,
        # not the original). strict rejects; changed accepts.
        fake = SimpleNamespace(image_to_string=lambda *a, **k: "45,030")
        for mode, want in (("strict", False), ("changed", True)):
            os.environ["MDAV_OCR_VERIFY"] = mode
            try:
                with patch.dict(sys.modules, {"pytesseract": fake}):
                    result = verify_edited_region_text(
                        Image.new("RGB", (120, 40), "white"),
                        [0, 0, 120, 40],
                        "1,533,668",
                        "1,346,000",
                    )
            finally:
                del os.environ["MDAV_OCR_VERIFY"]
            self.assertEqual(result, want, mode)

    def test_changed_mode_still_rejects_unchanged_original(self) -> None:
        # If OCR still sees the ORIGINAL value, the edit didn't take -> reject.
        fake = SimpleNamespace(image_to_string=lambda *a, **k: "1,346,000")
        os.environ["MDAV_OCR_VERIFY"] = "changed"
        try:
            with patch.dict(sys.modules, {"pytesseract": fake}):
                result = verify_edited_region_text(
                    Image.new("RGB", (120, 40), "white"),
                    [0, 0, 120, 40],
                    "1,533,668",
                    "1,346,000",
                )
        finally:
            del os.environ["MDAV_OCR_VERIFY"]
        self.assertFalse(result)

    def test_off_mode_skips_ocr_and_accepts(self) -> None:
        os.environ["MDAV_OCR_VERIFY"] = "off"
        try:
            result = verify_edited_region_text(
                Image.new("RGB", (10, 10), "white"), [0, 0, 10, 10], "x", "y"
            )
        finally:
            del os.environ["MDAV_OCR_VERIFY"]
        self.assertIsNone(result)  # None => builder treats as accept


if __name__ == "__main__":
    unittest.main()
