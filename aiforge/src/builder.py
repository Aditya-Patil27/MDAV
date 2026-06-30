"""
builder.py — Coordinates the end-to-end dataset generation pipeline per sample.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from PIL import Image

from src.diffusers_generator import DiffusersGenerator
from src.generator_base import ImageGenerator
from src.schema import UnifiedDocument
from src.field_selector import select_fields_for_variants
from src.value_mutator import mutate_value
from src.crop_generator import calculate_crop_box
from src.prompt_builder import build_inpainting_prompt
from src.crop_paste import paste_crop_back
from src.mask_generator import generate_tamper_mask
from src.annotation_writer import write_unified_annotation
from src.metadata_writer import (
    append_metadata_row,
    get_metadata_index,
    metadata_has_image_id,
)
from src.ocr_verifier import verify_edited_region_text
from src.ocr_locator import locate_substring_bbox
from src.validator import validate_sample
from src.statistics import StatsTracker
from src.progress_tracker import ProgressTracker
from src.utils import pad_to_multiple, unpad_to_box

logger = logging.getLogger(__name__)


def _save_failure_artifacts(
    output_dir: Path,
    image_id: str,
    attempt: int,
    forged_img,
    bbox: list[int],
    mask_margin: int,
    expected: str,
    original: str,
) -> None:
    """Persist a rejected sample so OCR-verification failures can be diagnosed.

    Writes to ``<output_dir>/_failed/`` (disable with ``MDAV_SAVE_FAILED=0``):
      * ``*_region.png``    -- exactly the pixels OCR inspected. Garbled glyphs
        here => FLUX failed to render the value (rendering problem).
      * ``*_placement.png`` -- the full image with the edited region boxed. If the
        box is over the wrong text => value-bbox localization problem.
      * ``*.json``          -- expected/original value, bbox, attempt.
    """
    if os.environ.get("MDAV_SAVE_FAILED", "1") == "0":
        return
    try:
        from PIL import ImageDraw

        debug_dir = output_dir / "_failed"
        debug_dir.mkdir(parents=True, exist_ok=True)
        stem = f"{image_id}_attempt{attempt}"

        forged_img.crop(tuple(bbox)).save(debug_dir / f"{stem}_region.png", "PNG")

        annotated = forged_img.copy()
        ImageDraw.Draw(annotated).rectangle(
            [
                bbox[0] - mask_margin,
                bbox[1] - mask_margin,
                bbox[2] + mask_margin,
                bbox[3] + mask_margin,
            ],
            outline=(255, 0, 0),
            width=3,
        )
        annotated.save(debug_dir / f"{stem}_placement.png", "PNG")

        (debug_dir / f"{stem}.json").write_text(
            json.dumps(
                {
                    "image_id": image_id,
                    "attempt": attempt,
                    "bbox": list(bbox),
                    "mask_margin": mask_margin,
                    "expected": expected,
                    "original": original,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        logger.info("Saved failure-debug artifacts for %s to %s", image_id, debug_dir)
    except Exception as exc:  # debug aid must never break generation
        logger.warning("Could not save failure-debug artifacts for %s: %s", image_id, exc)


def generate_forged_sample(
    doc: UnifiedDocument,
    output_dir: Path,
    stats: StatsTracker,
    seed: int,
    max_retries: int = 3,
    image_generator: ImageGenerator | None = None,
    progress_tracker: ProgressTracker | None = None,
    variant_index: int = 0,
    num_variants: int = 1,
) -> tuple[Path, Path, Path] | None:
    """Run the forgery pipeline for a single UnifiedDocument.

    Args:
        doc: The authentic UnifiedDocument.
        output_dir: Directory where datasets (images, annotations, masks, metadata.csv) are stored.
        stats: StatsTracker instance for logging metrics.
        seed: Random seed.
        max_retries: Number of times to retry AI generation before raising.

    Returns:
        Tuple of (authentic_image_path, forged_image_path, mask_path) or None if skipped.
    """
    if image_generator is None:
        image_generator = DiffusersGenerator.from_env()
    if num_variants <= 0:
        raise ValueError("num_variants must be positive")
    if variant_index < 0 or variant_index >= num_variants:
        raise ValueError(
            f"variant_index {variant_index} is outside num_variants={num_variants}"
        )

    forged_image_id = f"{doc.image_id}_v{variant_index}_forged"
    logger.info("Starting forgery generation for image_id: %s", forged_image_id)

    # 1. Field Selection
    selected_fields = select_fields_for_variants(doc, num_variants)
    if not selected_fields:
        logger.info("Skipping document %s: no eligible fields found", doc.image_id)
        return None
    field = selected_fields[variant_index]

    # 2. Value Mutation
    original_value_only = field.extra.get("value_text", field.text)
    mutated_value_only = mutate_value(original_value_only, field.label, seed=seed)
    if mutated_value_only == original_value_only:
        logger.info("Skipping document %s: mutated text matches original", doc.image_id)
        return None
    mutated_text = field.text.replace(original_value_only, mutated_value_only, 1)

    logger.info(
        "Field selected: %s (%s). Text: %r -> Mutated: %r",
        field.field_id,
        field.label,
        field.text,
        mutated_text,
    )

    # 3. Crop Box Calculation (50% padding, min 150px, clamped)
    crop_box = calculate_crop_box(field.bbox, doc.width, doc.height)
    cx1, cy1, cx2, cy2 = crop_box
    crop_w, crop_h = cx2 - cx1, cy2 - cy1

    forged_image_path = output_dir / "images" / f"{forged_image_id}.png"
    mask_path = output_dir / "masks" / f"{forged_image_id}.png"
    annotation_path = output_dir / "annotations" / f"{forged_image_id}.json"
    csv_path = output_dir / "metadata.csv"
    metadata_index = get_metadata_index(csv_path)

    if metadata_has_image_id(csv_path, forged_image_id, metadata_index):
        try:
            validate_sample(
                image_id=forged_image_id,
                forged_image_path=forged_image_path,
                mask_path=mask_path,
                annotation_path=annotation_path,
                csv_path=csv_path,
                expected_text=mutated_text,
                expected_width=doc.width,
                expected_height=doc.height,
                metadata_index=metadata_index,
            )
            stats.record_success(
                dataset=doc.dataset,
                language=doc.language,
                doc_type=doc.document_type,
                field_type=field.label,
                generator=image_generator.name,
                crop_w=crop_w,
                crop_h=crop_h,
                doc_w=doc.width,
                doc_h=doc.height,
            )
            if progress_tracker is not None:
                progress_tracker.mark_completed(forged_image_id)
            logger.info("Resuming: existing forged sample is valid for %s", forged_image_id)
            return doc.image_path, forged_image_path, mask_path
        except Exception as exc:
            logger.warning(
                "Existing metadata for %s is not a complete valid sample; regenerating. reason=%s",
                forged_image_id,
                exc,
            )

    # Load original image
    try:
        original_img = Image.open(doc.image_path).convert("RGB")
    except Exception as exc:
        logger.error("Failed to load original image %s: %s", doc.image_path, exc)
        stats.record_failure()
        if progress_tracker is not None:
            progress_tracker.mark_failed(forged_image_id)
        return None

    # Crop target region
    crop_img = original_img.crop((cx1, cy1, cx2, cy2))

    field_bbox_in_crop = [
        field.bbox[0] - cx1,
        field.bbox[1] - cy1,
        field.bbox[2] - cx1,
        field.bbox[3] - cy1,
    ]
    editing_bbox = locate_substring_bbox(
        crop_img,
        field_bbox_in_crop,
        original_value_only,
    )
    if editing_bbox is None:
        has_trusted_cord_value_bbox = (
            doc.dataset == "CORD"
            and field.extra.get("value_bbox_source") == "cord_is_key"
            and "label_text" in field.extra
            and bool(str(field.extra.get("value_text", "")).strip())
        )
        if has_trusted_cord_value_bbox:
            editing_bbox = field_bbox_in_crop
            logger.warning(
                "Using trusted CORD is_key value bbox after OCR localization failure. "
                "field=%s reason=%s",
                field.field_id,
                "no confidence-qualified exact OCR match",
            )
        else:
            logger.error(
                "OCR locator could not confidently find original value. "
                "document=%s dataset=%s stage=ocr_locator value=%r",
                doc.image_id,
                doc.dataset,
                original_value_only,
            )
            stats.record_failure()
            if progress_tracker is not None:
                progress_tracker.mark_failed(forged_image_id)
            return None

    editing_bbox_document = [
        editing_bbox[0] + cx1,
        editing_bbox[1] + cy1,
        editing_bbox[2] + cx1,
        editing_bbox[3] + cy1,
    ]

    # 4. Extend with real source pixels to dimensions accepted by FLUX.
    padded_crop, original_box_in_padded = pad_to_multiple(
        crop_img,
        multiple=64,
        source_image=original_img,
        source_box=crop_box,
    )
    padded_x1, padded_y1, _, _ = original_box_in_padded
    padded_bbox = [
        padded_x1 + editing_bbox[0],
        padded_y1 + editing_bbox[1],
        padded_x1 + editing_bbox[2],
        padded_y1 + editing_bbox[3],
    ]

    # 5. Prompt Construction
    prompt = build_inpainting_prompt(
        original_value_only,
        mutated_value_only,
        field.label,
    )

    # 6. AI Editing with Retries
    forged_img = None
    sample_accepted = False
    attempts_used = 0
    # Resolve the paste/mask margin once so steps 8 and 10 stay aligned.
    mask_margin = getattr(image_generator, "mask_margin", None)
    if mask_margin is None:
        mask_margin = int(os.environ.get("FLUX_MASK_MARGIN", "8"))
    for attempt in range(max_retries):
        attempts_used = attempt + 1
        attempt_failed = False
        try:
            logger.info(
                "Calling %s image generator (Attempt %d/%d)",
                image_generator.name,
                attempt + 1,
                max_retries,
            )
            edited_padded_crop = image_generator.generate(
                padded_crop,
                prompt,
                padded_bbox,
                seed=seed + attempt,
            )
            if edited_padded_crop is None:
                logger.warning("Generator returned no image on attempt %d", attempt + 1)
                attempt_failed = True
            elif edited_padded_crop.size != padded_crop.size:
                logger.warning(
                    "Generator returned invalid size %s; expected %s",
                    edited_padded_crop.size,
                    padded_crop.size,
                )
                attempt_failed = True
        except Exception as exc:
            logger.warning("Image generator call failed on attempt %d: %s", attempt + 1, exc)
            attempt_failed = True
        if attempt_failed:
            if attempt < max_retries - 1:
                stats.record_retry()
                if progress_tracker is not None:
                    progress_tracker.record_retry(forged_image_id)
                time.sleep(min(2**attempt, 30))
            continue

        # 7. Remove source-context padding without resizing.
        edited_crop = unpad_to_box(edited_padded_crop, original_box_in_padded)

        # 8. Feather the mutated area back into the original full-resolution image.
        forged_img = paste_crop_back(
            original_img,
            edited_crop,
            editing_bbox_document,
            crop_box,
            margin=mask_margin,
        )

        # 9. OCR verify edited region only. None means OCR tooling unavailable.
        ocr_result = verify_edited_region_text(
            forged_img,
            editing_bbox_document,
            mutated_value_only,
            original_value_only,
        )
        if ocr_result is False:
            _save_failure_artifacts(
                output_dir,
                forged_image_id,
                attempt + 1,
                forged_img,
                editing_bbox_document,
                mask_margin,
                mutated_value_only,
                original_value_only,
            )
            logger.warning(
                "OCR verification failed on attempt %d for %s; retrying",
                attempt + 1,
                forged_image_id,
            )
            if attempt < max_retries - 1:
                stats.record_retry()
                if progress_tracker is not None:
                    progress_tracker.record_retry(forged_image_id)
                time.sleep(min(2**attempt, 30))
            continue

        sample_accepted = True
        break

    if not sample_accepted or forged_img is None:
        logger.error("AI generation failed after %d attempts for %s", max_retries, forged_image_id)
        stats.record_failure()
        if progress_tracker is not None:
            progress_tracker.mark_failed(forged_image_id)
        return None

    # 10. Generate Binary Tamper Mask over the same region the paste modified.
    mask_img = generate_tamper_mask(
        doc.width, doc.height, editing_bbox_document, margin=mask_margin
    )

    # Save output files
    forged_image_path.parent.mkdir(parents=True, exist_ok=True)
    mask_path.parent.mkdir(parents=True, exist_ok=True)
    annotation_path.parent.mkdir(parents=True, exist_ok=True)

    forged_img.save(forged_image_path, "PNG")
    mask_img.save(mask_path, "PNG")

    # 11. Write Unified Annotation JSON
    write_unified_annotation(
        doc=doc,
        forged_image_id=forged_image_id,
        forged_image_path=forged_image_path,
        edited_field_id=field.field_id,
        forged_text=mutated_text,
        output_path=annotation_path,
    )

    # 12. Write Metadata Entry (CSV row)
    append_metadata_row(
        csv_path=csv_path,
        image_id=forged_image_id,
        dataset=doc.dataset,
        split=doc.split,
        language=doc.language,
        document_type=doc.document_type,
        source_image=doc.image_path,
        forged_image=forged_image_path,
        mask_path=mask_path,
        edited_field=field.field_id,
        original_text=field.text,
        forged_text=mutated_text,
        edited_field_type=field.label,
        generator=image_generator.name,
        crop_width=crop_w,
        crop_height=crop_h,
        doc_width=doc.width,
        doc_height=doc.height,
        attempts=attempts_used,
        metadata_index=metadata_index,
    )

    # 13. Validate generated sample output (Stops pipeline if validation fails)
    try:
        validate_sample(
            image_id=forged_image_id,
            forged_image_path=forged_image_path,
            mask_path=mask_path,
            annotation_path=annotation_path,
            csv_path=csv_path,
            expected_text=mutated_text,
            expected_width=doc.width,
            expected_height=doc.height,
            metadata_index=metadata_index,
        )
    except Exception as exc:
        logger.error(
            "Validation failed. document=%s dataset=%s stage=validation reason=%s",
            doc.image_id,
            doc.dataset,
            exc,
        )
        stats.record_failure()
        if progress_tracker is not None:
            progress_tracker.mark_failed(forged_image_id)
        return None

    # 14. Record stats
    stats.record_success(
        dataset=doc.dataset,
        language=doc.language,
        doc_type=doc.document_type,
        field_type=field.label,
        generator=image_generator.name,
        crop_w=crop_w,
        crop_h=crop_h,
        doc_w=doc.width,
        doc_h=doc.height,
    )
    if progress_tracker is not None:
        progress_tracker.mark_completed(forged_image_id)

    logger.info("Successfully completed forgery pipeline for: %s", forged_image_id)
    return doc.image_path, forged_image_path, mask_path
