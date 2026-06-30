"""
ocr_verifier.py - Optional OCR verification for edited document regions.

The verifier only OCRs the edited bounding box. If pytesseract or the local
Tesseract binary is unavailable, verification is skipped so generation can
still run in environments without OCR tooling.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Optional

from PIL import Image

from src.ocr_config import ocr_configs_for_text

logger = logging.getLogger(__name__)

_OCR_UNAVAILABLE_LOGGED = False


def verify_edited_region_text(
    image: Image.Image,
    bbox: list[int],
    expected_text: str,
    original_text: str,
) -> Optional[bool]:
    """Return True/False for OCR verification, or None when OCR is unavailable.

    Mode is set by env ``MDAV_OCR_VERIFY``:

    * ``strict`` (default) -- accept only if OCR reads the *exact* mutated value.
      Correct for "semantically perfect" forgeries, but diffusion models (FLUX)
      cannot reliably render an exact long number, so most samples fail.
    * ``changed`` -- accept as long as the region no longer shows the *original*
      value. For an AI-forgery **detector** the label is the tamper **mask**, not
      the exact text, so a region FLUX inpainted with a different plausible value
      is still a valid positive sample. This is what makes generation usable.
    * ``off`` -- skip OCR entirely; accept every inpaint (fastest, no Tesseract).
    """
    global _OCR_UNAVAILABLE_LOGGED
    mode = os.environ.get("MDAV_OCR_VERIFY", "strict").lower()

    if mode == "off":
        return None  # treated by the builder as "accept" (verification skipped)

    try:
        import pytesseract
    except ImportError:
        if not _OCR_UNAVAILABLE_LOGGED:
            logger.warning("OCR verification skipped: pytesseract is not installed")
            _OCR_UNAVAILABLE_LOGGED = True
        return None

    x1, y1, x2, y2 = bbox
    if x2 <= x1 or y2 <= y1:
        logger.warning("OCR verification failed: empty bbox=%s", bbox)
        return False

    if not _normalize_text(expected_text):
        return None

    region = image.crop((x1, y1, x2, y2))
    observations: list[str] = []
    for config in ocr_configs_for_text(expected_text):
        try:
            observations.append(pytesseract.image_to_string(region, config=config))
        except Exception as exc:
            if not _OCR_UNAVAILABLE_LOGGED:
                logger.warning("OCR verification pass failed for %s: %s", config, exc)
                _OCR_UNAVAILABLE_LOGGED = True

    if not observations:
        return None

    if any(_value_present(observed, expected_text) for observed in observations):
        return True

    if original_text and any(
        _value_present(observed, original_text) for observed in observations
    ):
        logger.warning(
            "OCR saw original text after edit. expected=%r observed=%r",
            expected_text,
            observations,
        )
        return False

    if mode == "changed":
        # Region was inpainted to *something other* than the original -> the
        # tamper happened; the mask (the real training label) is valid.
        logger.info(
            "Accepting inpainted region (lenient mode). expected=%r observed=%r",
            expected_text,
            observations,
        )
        return True

    logger.warning(
        "OCR did not see expected text. expected=%r observed=%r",
        expected_text,
        observations,
    )
    return False


def _normalize_text(text: str) -> str:
    return re.sub(r"[^0-9a-z]+", "", text.lower())


def _value_present(observed: str, expected: str) -> bool:
    """True if ``expected`` appears as a *standalone* value in ``observed``.

    Tolerant of OCR separator/space noise between characters (``503,000`` vs
    ``503 000``), but anchored on alphanumeric boundaries so a value is never
    matched *inside* a longer token -- the old ``expected_norm in observed``
    accepted ``503000`` inside ``1503000``, letting a wrong inpaint pass.
    """
    chars = [c for c in expected if c.isalnum()]
    if not chars:
        return False
    gap = r"[\s.,'\-]*"
    pattern = (
        r"(?<![0-9A-Za-z])"
        + gap.join(re.escape(c) for c in chars)
        + r"(?![0-9A-Za-z])"
    )
    return re.search(pattern, observed, re.IGNORECASE) is not None
