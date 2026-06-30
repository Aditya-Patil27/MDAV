"""
value_mutator.py — Semantic-preserving mutation for document text values.

Handles mutation of money, dates, invoice/receipt IDs, quantities,
and generic numbers. All mutations use the project-wide seeded RNG.
"""

from __future__ import annotations

import logging
import random
import re
from datetime import datetime, timedelta
from typing import Optional

from src.utils import get_rng

logger = logging.getLogger(__name__)

# Regular expressions for heuristics
RE_DATE_DMY = re.compile(r"\b(\d{1,2})(\s*[/\-.]\s*)(\d{1,2})(\s*[/\-.]\s*)(\d{2,4})\b")
RE_DATE_YMD = re.compile(r"\b(\d{4})(\s*[/\-.]\s*)(\d{1,2})(\s*[/\-.]\s*)(\d{1,2})\b")
RE_DATE_MONTH_NAME = re.compile(
    r"\b("
    r"January|February|March|April|May|June|July|August|September|October|November|December|"
    r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
    r")\s+(\d{1,2}),\s*(\d{2,4})\b",
    re.IGNORECASE,
)
RE_MONEY = re.compile(r"^\D*?(\d[\d,.]*)\s*\D*?$")

_MONTH_TO_NUM = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}
_MONTH_FULL = [
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
_MONTH_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def mutate_value(text: str, label: str, seed: Optional[int] = None) -> str:
    """Mutate a text value semantically based on its label and content.

    Args:
        text: The original text to mutate.
        label: The category/label of the field.
        seed: Seed for the random number generator.

    Returns:
        The mutated text.
    """
    rng = random.Random(seed) if seed is not None else get_rng()
    text_stripped = text.strip()

    if not text_stripped:
        return text

    # Check for date formats first (heuristic or date label)
    if (
        "date" in label.lower()
        or RE_DATE_DMY.search(text_stripped)
        or RE_DATE_YMD.search(text_stripped)
        or RE_DATE_MONTH_NAME.search(text_stripped)
    ):
        return _mutate_date(text, rng)

    # Check for money/prices
    if any(k in label.lower() for k in ["price", "total", "tax", "subtotal", "amount", "discount"]):
        return _mutate_money(text, rng)

    # Check for quantities
    if any(k in label.lower() for k in ["qty", "cnt", "quantity"]):
        return _mutate_quantity(text, rng)

    # Check for invoice / receipt IDs
    if any(k in label.lower() for k in ["invoice", "receipt", "doc_id", "document_id"]):
        return _mutate_id(text, rng)

    # Check if text contains digits (generic numbers)
    if any(c.isdigit() for c in text_stripped):
        # Let's see if it looks like money anyway
        if RE_MONEY.match(text_stripped):
            return _mutate_money(text, rng)
        return _mutate_generic_number(text, rng)

    # Alphabetic text/other: leave unchanged
    return text


def _mutate_money(text: str, rng) -> str:
    """Mutate money/prices preserving separators, decimals, and length if possible."""
    # Find the numeric part
    match = RE_MONEY.match(text)
    if not match:
        return _mutate_digit_fallback(text, rng)

    num_str = match.group(1)
    # Check separators: count commas and dots
    has_comma = "," in num_str
    has_dot = "." in num_str

    # Extract raw digits to find magnitude/value
    raw_digits = "".join(c for c in num_str if c.isdigit())
    if not raw_digits:
        return _mutate_digit_fallback(text, rng)

    val = int(raw_digits)
    if val == 0:
        val = 100  # avoid zero

    # Try up to 100 times to generate a mutated value with the exact same format
    # (i.e. same digit length/character count)
    target_len = len(raw_digits)
    for _ in range(100):
        # Perturb by ±10-50%
        factor = rng.uniform(0.5, 1.5)
        if factor == 1.0:
            factor = 1.2
        new_val = int(val * factor)
        if new_val == val:
            new_val += rng.choice([-1, 1])
        new_val = max(1, new_val)

        new_raw = str(new_val)
        if len(new_raw) == target_len:
            # Reconstruct format
            # We map characters from original num_str, replacing digits one by one
            reconstructed = []
            digit_idx = 0
            for char in num_str:
                if char.isdigit():
                    reconstructed.append(new_raw[digit_idx])
                    digit_idx += 1
                else:
                    reconstructed.append(char)
            new_num_str = "".join(reconstructed)
            return text.replace(num_str, new_num_str)

    # Fallback: simple digit replacement
    return _mutate_digit_fallback(text, rng)


def _mutate_date(text: str, rng) -> str:
    """Perturb day, month, and/or year in a date string while remaining valid."""
    match_month_name = RE_DATE_MONTH_NAME.search(text)
    if match_month_name:
        month_str, d_str, y_str = match_month_name.groups()
        month = _MONTH_TO_NUM.get(month_str.lower())
        if month is None:
            return _mutate_digit_fallback(text, rng)
        try:
            y_val = int(y_str)
            year = 2000 + y_val if len(y_str) == 2 else y_val
            dt = datetime(year, month, int(d_str))
        except ValueError:
            return _mutate_digit_fallback(text, rng)

        delta_days = rng.randint(1, 30) * rng.choice([-1, 1])
        new_dt = dt + timedelta(days=delta_days)
        if len(month_str) <= 4:
            new_month = _MONTH_ABBR[new_dt.month]
        else:
            new_month = _MONTH_FULL[new_dt.month]
        new_d = f"{new_dt.day:0{len(d_str)}d}"
        new_y = f"{new_dt.year % 100:02d}" if len(y_str) == 2 else f"{new_dt.year:04d}"
        new_date_str = f"{new_month} {new_d}, {new_y}"
        return text[:match_month_name.start()] + new_date_str + text[match_month_name.end():]

    # Find DD/MM/YYYY or YYYY/MM/DD
    match_dmy = RE_DATE_DMY.search(text)
    if match_dmy:
        d_str, sep1, m_str, sep2, y_str = match_dmy.groups()
        fmt = "dmy"
        orig_span = match_dmy.span()
    else:
        match_ymd = RE_DATE_YMD.search(text)
        if match_ymd:
            y_str, sep1, m_str, sep2, d_str = match_ymd.groups()
            fmt = "ymd"
            orig_span = match_ymd.span()
        else:
            return _mutate_digit_fallback(text, rng)

    try:
        # Determine year format (2-digit or 4-digit)
        y_val = int(y_str)
        if len(y_str) == 2:
            # assume 20xx
            year = 2000 + y_val
        else:
            year = y_val

        dt = datetime(year, int(m_str), int(d_str))
    except ValueError:
        # Invalid date parsed, fallback
        return _mutate_digit_fallback(text, rng)

    # Perturb date by a random delta (between 1 and 365 days, positive or negative)
    delta_days = rng.randint(1, 30) * rng.choice([-1, 1])
    new_dt = dt + timedelta(days=delta_days)

    # Format back to match original widths
    new_d = f"{new_dt.day:0{len(d_str)}d}"
    new_m = f"{new_dt.month:0{len(m_str)}d}"
    if len(y_str) == 2:
        new_y = f"{new_dt.year % 100:02d}"
    else:
        new_y = f"{new_dt.year:04d}"

    if fmt == "dmy":
        new_date_str = f"{new_d}{sep1}{new_m}{sep2}{new_y}"
    else:
        new_date_str = f"{new_y}{sep1}{new_m}{sep2}{new_d}"

    return text[:orig_span[0]] + new_date_str + text[orig_span[1]:]


def _mutate_id(text: str, rng) -> str:
    """Modify one or two digits in an invoice or receipt ID, preserving length."""
    # Find all digit indices
    digit_indices = [i for i, c in enumerate(text) if c.isdigit()]
    if not digit_indices:
        return text

    # Select 1 or 2 digits to change
    num_to_change = min(len(digit_indices), rng.choice([1, 2]))
    indices_to_change = rng.sample(digit_indices, num_to_change)

    char_list = list(text)
    for idx in indices_to_change:
        orig_digit = int(char_list[idx])
        # Choose a different digit
        new_digit = rng.choice([d for d in range(10) if d != orig_digit])
        char_list[idx] = str(new_digit)

    return "".join(char_list)


def _mutate_quantity(text: str, rng) -> str:
    """Multiply quantity by 2-5x while preserving formatting (like 'x' or 'PC')."""
    # Extract numeric part
    match = re.search(r"(\d+)", text)
    if not match:
        return text

    orig_qty_str = match.group(1)
    orig_qty = int(orig_qty_str)

    # Multiply by 2-5x
    multiplier = rng.randint(2, 5)
    new_qty = orig_qty * multiplier

    # Replace in string
    return text.replace(orig_qty_str, str(new_qty), 1)


def _mutate_generic_number(text: str, rng) -> str:
    """Mutate generic numbers by changing 1-2 digits, preserving formatting."""
    return _mutate_id(text, rng)


def _mutate_digit_fallback(text: str, rng) -> str:
    """Fallback: modify random digits preserving non-digit structure."""
    return _mutate_id(text, rng)
