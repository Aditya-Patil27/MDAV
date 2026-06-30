"""
metadata_writer.py — Appends sample metadata to metadata.csv.

Maintains a unified tabular log of all generated document forgeries.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# CSV Columns in specified order
CSV_HEADERS = [
    "image_id",
    "dataset",
    "split",
    "language",
    "document_type",
    "source_image",
    "forged_image",
    "mask_path",
    "edited_field",
    "edited_field_type",
    "original_text",
    "forged_text",
    "generator",
    "generator_model",
    "generation_method",
    "crop_width",
    "crop_height",
    "doc_width",
    "doc_height",
    "attempts",
    "timestamp",
]


@dataclass
class MetadataIndex:
    """Process-local O(1) lookup index for one metadata CSV."""

    image_ids: set[str] = field(default_factory=set)
    rows_by_id: dict[str, dict[str, str]] = field(default_factory=dict)
    duplicate_ids: set[str] = field(default_factory=set)

    @classmethod
    def load(cls, csv_path: Path) -> "MetadataIndex":
        index = cls()
        if not csv_path.exists():
            return index
        try:
            with csv_path.open("r", encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    image_id = row.get("image_id")
                    if not image_id:
                        continue
                    if image_id in index.image_ids:
                        index.duplicate_ids.add(image_id)
                    index.image_ids.add(image_id)
                    index.rows_by_id.setdefault(image_id, dict(row))
        except OSError as exc:
            logger.warning("Could not build metadata index from %s: %s", csv_path, exc)
        return index

    def add_row(self, row: dict[str, object]) -> None:
        image_id = str(row["image_id"])
        if image_id in self.image_ids:
            self.duplicate_ids.add(image_id)
            return
        self.image_ids.add(image_id)
        self.rows_by_id[image_id] = {key: str(value) for key, value in row.items()}


_METADATA_INDEXES: dict[Path, MetadataIndex] = {}


def get_metadata_index(csv_path: Path) -> MetadataIndex:
    """Build an index once per CSV path and reuse it for the current process."""
    key = csv_path.expanduser().resolve()
    cached = _METADATA_INDEXES.get(key)
    if cached is not None:
        if not csv_path.exists() and cached.image_ids:
            cached = MetadataIndex()
            _METADATA_INDEXES[key] = cached
        return cached
    index = MetadataIndex.load(csv_path)
    _METADATA_INDEXES[key] = index
    return index


def metadata_has_image_id(
    csv_path: Path,
    image_id: str,
    metadata_index: MetadataIndex | None = None,
) -> bool:
    """Return True if the cached metadata index contains image_id."""
    index = metadata_index or get_metadata_index(csv_path)
    return image_id in index.image_ids


def append_metadata_row(
    csv_path: Path,
    image_id: str,
    dataset: str,
    split: str,
    language: str,
    document_type: str,
    source_image: Path,
    forged_image: Path,
    mask_path: Path,
    edited_field: str,
    original_text: str,
    forged_text: str,
    edited_field_type: str | None = None,
    generator: str = "diffusers",
    generator_model: str = "flux-fill",
    generation_method: str = "ai_inpainting",
    crop_width: int | None = None,
    crop_height: int | None = None,
    doc_width: int | None = None,
    doc_height: int | None = None,
    attempts: int | None = None,
    metadata_index: MetadataIndex | None = None,
) -> None:
    """Append a metadata entry for one generated sample to the CSV file.

    Creates the CSV and writes headers if it doesn't already exist.

    Args:
        csv_path: Path to the metadata.csv file.
        image_id: Unique forgery image ID.
        dataset: Original dataset name (e.g. CORD).
        split: Split name.
        language: Language code.
        document_type: Document type.
        source_image: Path to the authentic source image.
        forged_image: Path to the mutated forgery image.
        mask_path: Path to the binary tamper mask image.
        edited_field: The ID of the edited field.
        original_text: Original text string.
        forged_text: Mutated text string.
        generator: Tool name used ("diffusers").
        generator_model: Underlying model used ("flux-fill").
        generation_method: Editing method ("ai_inpainting").
    """
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    index = metadata_index or get_metadata_index(csv_path)
    if metadata_has_image_id(csv_path, image_id, index):
        logger.info("Metadata already contains image_id %s; skipping duplicate row", image_id)
        return

    write_header = not csv_path.exists()

    row = {
        "image_id": image_id,
        "dataset": dataset,
        "split": split,
        "language": language,
        "document_type": document_type,
        "source_image": str(source_image),
        "forged_image": str(forged_image),
        "mask_path": str(mask_path),
        "edited_field": edited_field,
        "edited_field_type": "" if edited_field_type is None else edited_field_type,
        "original_text": original_text,
        "forged_text": forged_text,
        "generator": generator,
        "generator_model": generator_model,
        "generation_method": generation_method,
        "crop_width": "" if crop_width is None else crop_width,
        "crop_height": "" if crop_height is None else crop_height,
        "doc_width": "" if doc_width is None else doc_width,
        "doc_height": "" if doc_height is None else doc_height,
        "attempts": "" if attempts is None else attempts,
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }

    try:
        with csv_path.open("a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            if write_header:
                writer.writeheader()
            writer.writerow(row)
        index.add_row(row)
        logger.debug("Appended metadata row for image_id %s to %s", image_id, csv_path)
    except OSError as exc:
        logger.error("Failed to write metadata row to %s: %s", csv_path, exc)
        raise
