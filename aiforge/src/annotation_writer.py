"""
annotation_writer.py — Writes unified annotation JSON files for the forged dataset.

Serializes the UnifiedDocument dataclass with mutated fields and updated paths.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path

from src.schema import UnifiedDocument

logger = logging.getLogger(__name__)


def write_unified_annotation(
    doc: UnifiedDocument,
    forged_image_id: str,
    forged_image_path: Path,
    edited_field_id: str,
    forged_text: str,
    output_path: Path,
) -> None:
    """Duplicate the document annotation, update the mutated field, and save as JSON.

    Args:
        doc: The original UnifiedDocument.
        forged_image_id: The new unique ID for the forged document.
        forged_image_path: The absolute path to the saved forged image.
        edited_field_id: The ID of the field that was mutated.
        forged_text: The new mutated text.
        output_path: Destination path for the JSON annotation file.
    """
    # Create a deep copy of fields and modify the edited one
    updated_fields = []
    for field in doc.fields:
        # We construct a new field or copy it
        field_dict = asdict(field)
        if field.field_id == edited_field_id:
            field_dict["text"] = forged_text
        updated_fields.append(field_dict)

    # Prepare document dictionary matching UnifiedDocument schema
    doc_dict = {
        "image_id": forged_image_id,
        "dataset": doc.dataset,
        "split": doc.split,
        "language": doc.language,
        "document_type": doc.document_type,
        "width": doc.width,
        "height": doc.height,
        "image_path": str(forged_image_path),
        "fields": updated_fields,
        "metadata": {
            **doc.metadata,
            "original_image_id": doc.image_id,
            "original_image_path": str(doc.image_path),
            "edited_field_id": edited_field_id,
            "original_text": next((f.text for f in doc.fields if f.field_id == edited_field_id), ""),
            "forged_text": forged_text,
        }
    }

    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(doc_dict, f, ensure_ascii=False, indent=2)

    logger.debug("Saved unified annotation to %s", output_path)
