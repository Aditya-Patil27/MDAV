from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from src.builder import _save_failure_artifacts


class FailureDebugTest(unittest.TestCase):
    def test_writes_region_placement_and_json(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            img = Image.new("RGB", (100, 60), "white")
            _save_failure_artifacts(
                out, "cord_000_v0_forged", 1, img, [20, 20, 40, 30], 8, "68.365", "12.000"
            )
            fd = out / "_failed"
            self.assertTrue((fd / "cord_000_v0_forged_attempt1_region.png").exists())
            self.assertTrue((fd / "cord_000_v0_forged_attempt1_placement.png").exists())
            info = json.loads((fd / "cord_000_v0_forged_attempt1.json").read_text())
            self.assertEqual(info["expected"], "68.365")
            self.assertEqual(info["bbox"], [20, 20, 40, 30])
            self.assertEqual(info["mask_margin"], 8)

    def test_env_flag_disables_saving(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            os.environ["MDAV_SAVE_FAILED"] = "0"
            try:
                _save_failure_artifacts(
                    out, "x", 1, Image.new("RGB", (10, 10), "white"), [1, 1, 5, 5], 2, "a", "b"
                )
            finally:
                del os.environ["MDAV_SAVE_FAILED"]
            self.assertFalse((out / "_failed").exists())

    def test_never_raises_on_bad_input(self) -> None:
        # A degenerate bbox must not crash generation; the helper swallows errors.
        with tempfile.TemporaryDirectory() as d:
            _save_failure_artifacts(
                Path(d), "x", 1, Image.new("RGB", (10, 10), "white"), [9, 9, 1, 1], 2, "a", "b"
            )


if __name__ == "__main__":
    unittest.main()
