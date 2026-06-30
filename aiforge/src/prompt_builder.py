"""
Deterministic prompt generator for masked document inpainting.

Constructs explicit semantic replacement instructions for masked editing.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def build_inpainting_prompt(old_text: str, new_text: str, field_type: str) -> str:
    """Describe an exact text replacement inside the supplied inpainting mask.

    Kept short on purpose: FLUX's CLIP text encoder truncates at 77 *tokens*
    (quotes/punctuation/sub-words tokenize heavily, so the old verbose preserve
    list overflowed and CLIP dropped the tail). This concise form front-loads the
    exact value and the appearance constraints that matter, and stays well under
    the CLIP budget while T5 still receives the full string.
    """
    prompt = (
        f'In masked field type "{field_type}", replace original value "{old_text}" '
        f'with exact new value "{new_text}". Keep the same font, size, color, and '
        "background; change nothing else."
    )

    logger.debug("Generated prompt for old_text=%r -> new_text=%r", old_text, new_text)
    return prompt
