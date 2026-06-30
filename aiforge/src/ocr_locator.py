"""Locate an exact value substring inside an annotated field region."""

from __future__ import annotations

import logging
from statistics import mean

from PIL import Image

from src.ocr_config import ocr_configs_for_text

logger = logging.getLogger(__name__)


def locate_substring_bbox(
    crop_image: Image.Image,
    field_bbox_in_crop: list[int],
    original_value_text: str,
    min_confidence: float = 60,
) -> list[int] | None:
    """Return the crop-local bbox of an exact OCR token run, or ``None``."""
    x1, y1, x2, y2 = field_bbox_in_crop
    if x2 <= x1 or y2 <= y1:
        return None

    target = _normalize_whitespace(original_value_text)
    if not target:
        return None

    try:
        import pytesseract
    except ImportError:
        logger.warning("OCR substring localization skipped: pytesseract is not installed")
        return None

    region = crop_image.crop((x1, y1, x2, y2))
    for config in ocr_configs_for_text(target):
        try:
            data = pytesseract.image_to_data(
                region,
                output_type=pytesseract.Output.DICT,
                config=config,
            )
            match = _find_match(_tokens_from_data(data), target, min_confidence)
        except Exception as exc:
            logger.warning("OCR substring localization failed for %s: %s", config, exc)
            continue
        if match is not None:
            left = min(token["left"] for token in match)
            top = min(token["top"] for token in match)
            right = max(token["left"] + token["width"] for token in match)
            bottom = max(token["top"] + token["height"] for token in match)
            return [x1 + left, y1 + top, x1 + right, y1 + bottom]
    return None


def _find_match(
    tokens: list[dict],
    target: str,
    min_confidence: float,
) -> list[dict] | None:
    try:
        match = _find_exact_run(tokens, target)
        if match is None:
            match = next(
                (
                    [token]
                    for token in tokens
                    if _normalize_whitespace(token["text"]) == target
                ),
                None,
            )
        if match is not None:
            # Tesseract emits conf == -1 for boxes it has no score for; including
            # those in the mean can sink an otherwise-confident multi-token run.
            scored = [token["conf"] for token in match if token["conf"] >= 0]
            if scored and mean(scored) >= min_confidence:
                return match
    except Exception as exc:
        logger.warning("OCR substring localization returned invalid data: %s", exc)
    return None


def _normalize_whitespace(text: str) -> str:
    return " ".join(str(text).split())


def _tokens_from_data(data: dict) -> list[dict]:
    tokens: list[dict] = []
    for index, text in enumerate(data.get("text", [])):
        normalized = _normalize_whitespace(text)
        if not normalized:
            continue
        tokens.append(
            {
                "text": normalized,
                "conf": float(data["conf"][index]),
                "left": int(data["left"][index]),
                "top": int(data["top"][index]),
                "width": int(data["width"][index]),
                "height": int(data["height"][index]),
            }
        )
    return tokens


def _find_exact_run(tokens: list[dict], target: str) -> list[dict] | None:
    for start in range(len(tokens)):
        for end in range(start + 1, len(tokens) + 1):
            candidate = " ".join(token["text"] for token in tokens[start:end])
            if candidate == target:
                return tokens[start:end]
            if len(candidate) > len(target):
                break
    return None
