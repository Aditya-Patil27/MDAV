from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.progress_tracker import ProgressTracker


class ProgressTrackerTest(unittest.TestCase):
    def test_persists_completed_failed_and_retry_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            progress_path = Path(tmp) / "progress.json"
            tracker = ProgressTracker(progress_path)
            tracker.record_retry("doc_1_v0_forged")
            tracker.mark_completed("doc_1_v0_forged")
            tracker.mark_failed("doc_2_v1_forged")

            loaded = ProgressTracker.load(progress_path)
            self.assertTrue(loaded.should_skip("doc_1_v0_forged"))
            self.assertIn("doc_2_v1_forged", loaded.failed_ids)
            self.assertEqual(loaded.retry_counts["doc_1_v0_forged"], 1)


if __name__ == "__main__":
    unittest.main()
