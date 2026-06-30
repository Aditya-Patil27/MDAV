"""
visualization.py — Automatic visualization generation.

Generates sample grids, mask overlays, close-up crops, and distribution plots.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
from PIL import Image

from src.statistics import StatsTracker

logger = logging.getLogger(__name__)


def generate_visualizations(
    output_dir: Path,
    stats: StatsTracker,
    sample_paths: List[tuple[Path, Path, Path]],  # List of (authentic_path, forged_path, mask_path)
) -> None:
    """Create visualization files in the target folder.

    Args:
        output_dir: Directory where visualizations should be saved.
        stats: StatsTracker instance containing accumulated stats.
        sample_paths: List of tuples representing generated files.
    """
    vis_dir = output_dir / "visualizations"
    vis_dir.mkdir(parents=True, exist_ok=True)

    # 1. Generate Distribution Plots
    try:
        _plot_distributions(stats, vis_dir)
    except Exception as exc:
        logger.error("Failed to generate distribution plots: %s", exc, exc_info=True)

    # 2. Generate Mask Overlays (up to 3 samples)
    for idx, (auth, forged, mask) in enumerate(sample_paths[:3]):
        try:
            _create_mask_overlay(auth, forged, mask, vis_dir / f"overlay_{idx}.png")
            _create_closeup_comparison(auth, forged, mask, vis_dir / f"closeup_{idx}.png")
        except Exception as exc:
            logger.error("Failed to generate sample overlay for %s: %s", auth.name, exc, exc_info=True)

    # 3. Generate Sample Grid (up to 9 samples)
    if sample_paths:
        try:
            _create_sample_grid([f for _, f, _ in sample_paths[:9]], vis_dir / "sample_grid.png")
        except Exception as exc:
            logger.error("Failed to generate sample grid: %s", exc, exc_info=True)

    logger.info("Saved visualizations to %s", vis_dir)


def _plot_distributions(stats: StatsTracker, vis_dir: Path) -> None:
    """Plot field-type and language distributions as bar charts."""
    computed = stats.compute_stats()

    # Field Type Distribution
    field_dist = computed.get("edited_field_distribution", {})
    if field_dist:
        plt.figure(figsize=(10, 5))
        plt.bar(field_dist.keys(), field_dist.values(), color="skyblue")
        plt.title("Edited Field Type Distribution")
        plt.xlabel("Field Type")
        plt.ylabel("Count")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        plt.savefig(vis_dir / "field_type_distribution.png", dpi=150)
        plt.close()

    # Language Distribution
    lang_dist = computed.get("language_counts", {})
    if lang_dist:
        plt.figure(figsize=(8, 5))
        plt.bar(lang_dist.keys(), lang_dist.values(), color="salmon")
        plt.title("Language Distribution")
        plt.xlabel("Language")
        plt.ylabel("Count")
        plt.tight_layout()
        plt.savefig(vis_dir / "language_distribution.png", dpi=150)
        plt.close()


def _create_mask_overlay(
    auth_path: Path,
    forged_path: Path,
    mask_path: Path,
    save_path: Path,
) -> None:
    """Create a side-by-side image: [Authentic, Mask, Forged]."""
    auth = Image.open(auth_path).convert("RGB")
    forged = Image.open(forged_path).convert("RGB")
    mask = Image.open(mask_path).convert("RGB")

    # Resize all to a uniform height (e.g. 800px) keeping aspect ratio
    h_target = 800
    resized_images = []
    for img in [auth, mask, forged]:
        aspect = img.width / img.height
        w_target = int(h_target * aspect)
        resized_images.append(img.resize((w_target, h_target), Image.Resampling.LANCZOS))

    total_w = sum(img.width for img in resized_images) + 40  # 20px padding between images
    canvas = Image.new("RGB", (total_w, h_target + 40), (240, 240, 240))

    x_offset = 10
    for img in resized_images:
        canvas.paste(img, (x_offset, 20))
        x_offset += img.width + 20

    canvas.save(save_path)
    logger.debug("Saved mask overlay to %s", save_path)


def _create_closeup_comparison(
    auth_path: Path,
    forged_path: Path,
    mask_path: Path,
    save_path: Path,
) -> None:
    """Create a close-up comparison around the edited bounding box."""
    # Find bounding box from the mask
    mask = Image.open(mask_path).convert("L")
    bbox = mask.getbbox()  # returns (x1, y1, x2, y2) of non-zero region
    if not bbox:
        return

    # Pad the bounding box slightly for context
    x1, y1, x2, y2 = bbox
    w, h = x2 - x1, y2 - y1
    pad_w = int(w * 0.3) + 20
    pad_h = int(h * 0.3) + 20

    x1_crop = max(0, x1 - pad_w)
    y1_crop = max(0, y1 - pad_h)
    x2_crop = min(mask.width, x2 + pad_w)
    y2_crop = min(mask.height, y2 + pad_h)

    auth = Image.open(auth_path).convert("RGB").crop((x1_crop, y1_crop, x2_crop, y2_crop))
    forged = Image.open(forged_path).convert("RGB").crop((x1_crop, y1_crop, x2_crop, y2_crop))

    # Save side-by-side closeup
    total_w = auth.width + forged.width + 10
    h_max = max(auth.height, forged.height)
    canvas = Image.new("RGB", (total_w, h_max), (255, 255, 255))
    canvas.paste(auth, (0, 0))
    canvas.paste(forged, (auth.width + 10, 0))

    canvas.save(save_path)
    logger.debug("Saved closeup comparison to %s", save_path)


def _create_sample_grid(forged_paths: List[Path], save_path: Path) -> None:
    """Create a grid layout of generated forged documents."""
    images = [Image.open(p).convert("RGB") for p in forged_paths]
    if not images:
        return

    # Resize all to 400px width
    w_target = 400
    resized = []
    for img in images:
        aspect = img.height / img.width
        h_target = int(w_target * aspect)
        resized.append(img.resize((w_target, h_target), Image.Resampling.LANCZOS))

    cols = 3
    rows = (len(resized) + cols - 1) // cols

    col_width = w_target + 10
    row_height = max(img.height for img in resized) + 10

    canvas = Image.new("RGB", (col_width * cols + 10, row_height * rows + 10), (240, 240, 240))

    for idx, img in enumerate(resized):
        r = idx // cols
        c = idx % cols
        canvas.paste(img, (c * col_width + 10, r * row_height + 10))

    canvas.save(save_path)
    logger.debug("Saved sample grid to %s", save_path)
