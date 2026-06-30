"""
statistics.py — Accumulate and dump pipeline statistics to statistics.json.
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class StatsTracker:
    """Accumulates dataset statistics during the pipeline run."""

    def __init__(self) -> None:
        self.dataset_counts: Dict[str, int] = {}
        self.language_counts: Dict[str, int] = {}
        self.document_types: Dict[str, int] = {}
        self.edited_field_distribution: Dict[str, int] = {}
        self.generator_distribution: Dict[str, int] = {}
        self.crop_sizes: List[tuple[int, int]] = []
        self.doc_sizes: List[tuple[int, int]] = []
        self.successful_generations: int = 0
        self.failed_generations: int = 0
        self.retry_count: int = 0

    @classmethod
    def from_metadata(cls, csv_path: Path, failed_generations: int = 0) -> "StatsTracker":
        """Rebuild successful-generation statistics from the final metadata CSV."""
        stats = cls()
        stats.failed_generations = failed_generations

        if not csv_path.exists():
            logger.info("Metadata CSV not found while computing final statistics: %s", csv_path)
            return stats

        with csv_path.open("r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                image_id = row.get("image_id")
                if not image_id:
                    continue

                stats.successful_generations += 1
                dataset = row.get("dataset", "")
                language = row.get("language", "")
                doc_type = row.get("document_type", "")
                field_type = row.get("edited_field_type") or row.get("edited_field", "")
                generator = row.get("generator", "")

                stats.dataset_counts[dataset] = stats.dataset_counts.get(dataset, 0) + 1
                stats.language_counts[language] = stats.language_counts.get(language, 0) + 1
                stats.document_types[doc_type] = stats.document_types.get(doc_type, 0) + 1
                stats.edited_field_distribution[field_type] = (
                    stats.edited_field_distribution.get(field_type, 0) + 1
                )
                stats.generator_distribution[generator] = stats.generator_distribution.get(generator, 0) + 1

                crop_w = _parse_int(row.get("crop_width"))
                crop_h = _parse_int(row.get("crop_height"))
                if crop_w is not None and crop_h is not None:
                    stats.crop_sizes.append((crop_w, crop_h))

                doc_w = _parse_int(row.get("doc_width"))
                doc_h = _parse_int(row.get("doc_height"))
                if doc_w is not None and doc_h is not None:
                    stats.doc_sizes.append((doc_w, doc_h))

                attempts = _parse_int(row.get("attempts")) or 1
                stats.retry_count += max(0, attempts - 1)

        return stats

    def record_success(
        self,
        dataset: str,
        language: str,
        doc_type: str,
        field_type: str,
        generator: str,
        crop_w: int,
        crop_h: int,
        doc_w: int,
        doc_h: int,
    ) -> None:
        """Record a successfully generated sample."""
        self.successful_generations += 1
        self.dataset_counts[dataset] = self.dataset_counts.get(dataset, 0) + 1
        self.language_counts[language] = self.language_counts.get(language, 0) + 1
        self.document_types[doc_type] = self.document_types.get(doc_type, 0) + 1
        self.edited_field_distribution[field_type] = self.edited_field_distribution.get(field_type, 0) + 1
        self.generator_distribution[generator] = self.generator_distribution.get(generator, 0) + 1
        self.crop_sizes.append((crop_w, crop_h))
        self.doc_sizes.append((doc_w, doc_h))

    def record_failure(self) -> None:
        """Record a failed generation attempt."""
        self.failed_generations += 1

    def record_retry(self) -> None:
        """Record a retry event during generation."""
        self.retry_count += 1

    def compute_stats(self) -> Dict[str, Any]:
        """Compute averages and aggregate statistics."""
        avg_crop_w = 0.0
        avg_crop_h = 0.0
        if self.crop_sizes:
            avg_crop_w = sum(w for w, h in self.crop_sizes) / len(self.crop_sizes)
            avg_crop_h = sum(h for w, h in self.crop_sizes) / len(self.crop_sizes)

        avg_doc_w = 0.0
        avg_doc_h = 0.0
        if self.doc_sizes:
            avg_doc_w = sum(w for w, h in self.doc_sizes) / len(self.doc_sizes)
            avg_doc_h = sum(h for w, h in self.doc_sizes) / len(self.doc_sizes)

        return {
            "dataset_counts": self.dataset_counts,
            "language_counts": self.language_counts,
            "document_types": self.document_types,
            "edited_field_distribution": self.edited_field_distribution,
            "generator_distribution": self.generator_distribution,
            "average_crop_size": {
                "width": round(avg_crop_w, 2),
                "height": round(avg_crop_h, 2),
            },
            "average_document_size": {
                "width": round(avg_doc_w, 2),
                "height": round(avg_doc_h, 2),
            },
            "successful_generations": self.successful_generations,
            "failed_generations": self.failed_generations,
            "retry_count": self.retry_count,
        }

    def save(self, output_path: Path) -> None:
        """Save computed statistics as JSON to output_path."""
        stats = self.compute_stats()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        logger.info("Saved generation statistics to %s", output_path)


def _parse_int(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
