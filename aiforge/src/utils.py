"""
utils.py — Shared utility functions for the AIForge pipeline.

Responsibilities:
- Logging configuration
- Seeded random number generation
- Image I/O helpers (PIL-based)
- Path helpers
"""

from __future__ import annotations

import logging
import os
import random
import sys
from pathlib import Path
from typing import Optional

from PIL import Image


# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────

def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure root logger with a clean formatter.

    Args:
        level: Logging level string ("DEBUG", "INFO", "WARNING", "ERROR").

    Returns:
        Configured root logger.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(numeric_level)
    # Avoid duplicate handlers on repeated calls
    if not root.handlers:
        root.addHandler(handler)
    return root


def get_logger(name: str) -> logging.Logger:
    """Return a named child logger.

    Args:
        name: Logger name (typically ``__name__``).

    Returns:
        Named logger.
    """
    return logging.getLogger(name)


# ──────────────────────────────────────────────
# Seeded RNG
# ──────────────────────────────────────────────

_rng: Optional[random.Random] = None


def get_rng(seed: Optional[int] = None) -> random.Random:
    """Return the module-level seeded RNG, initialising it on first call.

    Args:
        seed: Integer seed. Ignored after first call; pass ``None`` to
              reuse the existing instance.

    Returns:
        Seeded :class:`random.Random` instance.
    """
    global _rng
    if _rng is None:
        _rng = random.Random(seed)
    return _rng


def reset_rng(seed: int) -> random.Random:
    """Force-reset the RNG to a new seed.

    Args:
        seed: New seed value.

    Returns:
        Fresh seeded :class:`random.Random` instance.
    """
    global _rng
    _rng = random.Random(seed)
    return _rng


# ──────────────────────────────────────────────
# Image I/O
# ──────────────────────────────────────────────

def load_image(path: Path) -> Image.Image:
    """Load an image from disk in RGB mode.

    Args:
        path: Absolute path to the image file.

    Returns:
        PIL Image in RGB mode.

    Raises:
        FileNotFoundError: If the image does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")
    img = Image.open(path)
    return img.convert("RGB")


def save_image(img: Image.Image, path: Path, quality: int = 95) -> None:
    """Save an image to disk, creating parent directories as needed.

    Args:
        img: PIL Image to save.
        path: Destination path. Format inferred from extension.
        quality: JPEG quality (ignored for PNG).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    ext = path.suffix.lower()
    if ext in (".jpg", ".jpeg"):
        img.save(path, format="JPEG", quality=quality)
    else:
        img.save(path, format="PNG")


def image_size(path: Path) -> tuple[int, int]:
    """Return (width, height) of an image without loading pixel data.

    Args:
        path: Absolute path to the image file.

    Returns:
        Tuple of (width, height) in pixels.
    """
    with Image.open(path) as img:
        return img.size  # (width, height)


def upsample(img: Image.Image, scale: float = 2.0) -> Image.Image:
    """Upsample an image using Lanczos resampling.

    Args:
        img: Source image.
        scale: Upscale factor (default 2×).

    Returns:
        Upsampled image.
    """
    new_w = round(img.width * scale)
    new_h = round(img.height * scale)
    return img.resize((new_w, new_h), Image.LANCZOS)


def downsample(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Downsample an image to exact pixel dimensions using Lanczos resampling.

    Args:
        img: Source image.
        target_w: Target width in pixels.
        target_h: Target height in pixels.

    Returns:
        Downsampled image.
    """
    return img.resize((target_w, target_h), Image.LANCZOS)


def _edge_replicate_pad(
    image: Image.Image,
    left: int,
    top: int,
    right: int,
    bottom: int,
) -> Image.Image:
    """Pad an image by repeating its outermost pixels without interpolation."""
    if min(left, top, right, bottom) < 0:
        raise ValueError("Padding values must be non-negative")
    if image.width <= 0 or image.height <= 0:
        raise ValueError("Cannot pad an empty image")

    output = Image.new(
        image.mode,
        (image.width + left + right, image.height + top + bottom),
        image.getpixel((0, 0)),
    )
    output.paste(image, (left, top))

    left_edge = image.crop((0, 0, 1, image.height))
    right_edge = image.crop((image.width - 1, 0, image.width, image.height))
    for x in range(left):
        output.paste(left_edge, (x, top))
    for x in range(right):
        output.paste(right_edge, (left + image.width + x, top))

    top_edge = output.crop((0, top, output.width, top + 1))
    bottom_y = top + image.height - 1
    bottom_edge = output.crop((0, bottom_y, output.width, bottom_y + 1))
    for y in range(top):
        output.paste(top_edge, (0, y))
    for y in range(bottom):
        output.paste(bottom_edge, (0, top + image.height + y))
    return output


def pad_to_multiple(
    image: Image.Image,
    multiple: int = 64,
    source_image: Image.Image | None = None,
    source_box: tuple[int, int, int, int] | None = None,
) -> tuple[Image.Image, tuple[int, int, int, int]]:
    """Extend an image to the next size multiple and return its box in the result."""
    if multiple <= 0:
        raise ValueError("multiple must be positive")

    target_width = ((image.width + multiple - 1) // multiple) * multiple
    target_height = ((image.height + multiple - 1) // multiple) * multiple
    extra_width = target_width - image.width
    extra_height = target_height - image.height
    left = extra_width // 2
    top = extra_height // 2
    right = extra_width - left
    bottom = extra_height - top

    if source_image is None or source_box is None:
        padded = _edge_replicate_pad(image, left, top, right, bottom)
        return padded, (left, top, left + image.width, top + image.height)

    x1, y1, x2, y2 = source_box
    if (x2 - x1, y2 - y1) != image.size:
        raise ValueError(
            f"source_box size {(x2 - x1, y2 - y1)} does not match image size {image.size}"
        )

    desired_left = x1 - left
    desired_top = y1 - top
    desired_right = x2 + right
    desired_bottom = y2 + bottom
    real_left = max(0, desired_left)
    real_top = max(0, desired_top)
    real_right = min(source_image.width, desired_right)
    real_bottom = min(source_image.height, desired_bottom)

    real_pixels = source_image.crop((real_left, real_top, real_right, real_bottom))
    pad_left = real_left - desired_left
    pad_top = real_top - desired_top
    pad_right = desired_right - real_right
    pad_bottom = desired_bottom - real_bottom
    padded = _edge_replicate_pad(
        real_pixels,
        pad_left,
        pad_top,
        pad_right,
        pad_bottom,
    )
    original_left = pad_left + (x1 - real_left)
    original_top = pad_top + (y1 - real_top)
    original_box = (
        original_left,
        original_top,
        original_left + image.width,
        original_top + image.height,
    )
    return padded, original_box


def unpad_to_box(
    padded_image: Image.Image,
    original_box_within_padded: tuple[int, int, int, int],
) -> Image.Image:
    """Crop a padded result back to the exact original image box."""
    x1, y1, x2, y2 = original_box_within_padded
    if x1 < 0 or y1 < 0 or x2 > padded_image.width or y2 > padded_image.height:
        raise ValueError(
            f"Unpad box {original_box_within_padded} is outside image size {padded_image.size}"
        )
    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"Unpad box has no area: {original_box_within_padded}")
    return padded_image.crop(original_box_within_padded)


# ──────────────────────────────────────────────
# Path helpers
# ──────────────────────────────────────────────

def ensure_dir(path: Path) -> Path:
    """Create a directory and all parents if they do not exist.

    Args:
        path: Directory path.

    Returns:
        The same path (for chaining).
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_dataset_root() -> Path:
    """Return the absolute path to the datasets/ directory.

    Assumes this file lives at <project_root>/src/utils.py.

    Returns:
        Path to the datasets root.
    """
    base_dir = Path(os.environ.get("BASE_DIR", Path(__file__).parent.parent)).expanduser()
    return base_dir / "datasets"


def resolve_output_root() -> Path:
    """Return the absolute path to the AIForge_Dataset/ output directory.

    Returns:
        Path to the output root.
    """
    base_dir = Path(os.environ.get("BASE_DIR", Path(__file__).parent.parent)).expanduser()
    default_output = base_dir / "AIForge_Dataset"
    return Path(os.environ.get("OUTPUT_DIR", default_output)).expanduser()
