"""Shared OCR pass selection for value localization and verification."""

from __future__ import annotations

import re

PSM7_CONFIG = "--psm 7"
NUMERIC_PSM8_CONFIG = "--psm 8 -c tessedit_char_whitelist=0123456789,.-"


def ocr_configs_for_text(text: str) -> tuple[str, ...]:
    """Return strict OCR passes appropriate for the expected value text."""
    compact = "".join(text.split())
    if compact and re.fullmatch(r"[0-9,.-]+", compact):
        return PSM7_CONFIG, NUMERIC_PSM8_CONFIG
    return (PSM7_CONFIG,)
