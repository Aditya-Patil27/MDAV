from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.metadata_writer import append_metadata_row
from src.statistics import StatsTracker


class StatisticsTest(unittest.TestCase):
    def test_rebuilds_success_statistics_from_final_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "source.png"
            forged = tmp_path / "forged.png"
            mask = tmp_path / "mask.png"
            for path in (source, forged, mask):
                path.write_bytes(b"x")

            csv_path = tmp_path / "metadata.csv"
            append_metadata_row(
                csv_path=csv_path,
                image_id="cord_1_v0_forged",
                dataset="CORD",
                split="train",
                language="ko",
                document_type="receipt",
                source_image=source,
                forged_image=forged,
                mask_path=mask,
                edited_field="field_total",
                original_text="10.00",
                forged_text="12.00",
                crop_width=100,
                crop_height=50,
                doc_width=800,
                doc_height=1200,
                attempts=1,
            )
            append_metadata_row(
                csv_path=csv_path,
                image_id="sroie_1_v1_forged",
                dataset="SROIE",
                split="train",
                language="en",
                document_type="receipt",
                source_image=source,
                forged_image=forged,
                mask_path=mask,
                edited_field="field_date",
                original_text="01/01/2020",
                forged_text="02/01/2020",
                crop_width=200,
                crop_height=70,
                doc_width=400,
                doc_height=900,
                attempts=3,
            )

            stats = StatsTracker.from_metadata(csv_path, failed_generations=2)
            computed = stats.compute_stats()

            self.assertEqual(computed["successful_generations"], 2)
            self.assertEqual(computed["failed_generations"], 2)
            self.assertEqual(computed["dataset_counts"], {"CORD": 1, "SROIE": 1})
            self.assertEqual(computed["generator_distribution"], {"diffusers": 2})
            self.assertEqual(computed["average_crop_size"], {"width": 150.0, "height": 60.0})
            self.assertEqual(computed["retry_count"], 2)


if __name__ == "__main__":
    unittest.main()
