"""
main.py — Main CLI entrypoint for the AIForge Document Forgery Dataset Generator.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys

from src.utils import setup_logging, reset_rng, resolve_output_root
from src.dataset_loader import load_all_datasets
from src.builder import generate_forged_sample
from src.diffusers_generator import DiffusersGenerator
from src.statistics import StatsTracker
from src.visualization import generate_visualizations
from src.progress_tracker import ProgressTracker

logger = logging.getLogger("aiforge")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="AIForge: Benchmark Dataset Generator for AI-Generated Document Forgeries"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit the number of documents to process.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic/reproducible runs.",
    )
    parser.add_argument(
        "--datasets",
        type=str,
        nargs="+",
        default=["CORD", "FUNSD", "SROIE", "XFUND"],
        choices=["CORD", "FUNSD", "SROIE", "XFUND"],
        help="Datasets to process (default: CORD, FUNSD, SROIE, XFUND).",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum retries for generation or OCR verification failures.",
    )
    parser.add_argument(
        "--variants-per-doc",
        type=int,
        default=2,
        help="Number of independently edited variants generated per source document.",
    )
    parser.add_argument(
        "--shard-count",
        type=int,
        default=1,
        help="Total number of deterministic work shards.",
    )
    parser.add_argument(
        "--shard-index",
        type=int,
        default=0,
        help="Zero-based shard processed by this run.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output root. Required when --shard-count is greater than 1.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log output level.",
    )
    args = parser.parse_args()
    if args.variants_per_doc <= 0:
        parser.error("--variants-per-doc must be positive")
    if args.shard_count <= 0:
        parser.error("--shard-count must be positive")
    if args.shard_index < 0 or args.shard_index >= args.shard_count:
        parser.error("--shard-index must satisfy 0 <= index < shard-count")
    if args.shard_count > 1 and args.output_dir is None:
        parser.error("multi-shard runs require a separate explicit --output-dir per shard")
    return args


def write_readme(output_dir: Path) -> None:
    """Write the dataset README.md file in the output directory."""
    readme_path = output_dir / "README.md"
    content = """# AIForge: AI-Generated Document Forgery Benchmark Dataset

This dataset was generated using the **AIForge Pipeline** to facilitate training and benchmarking of AI-generated document forgery detection models.

## Dataset Structure

The final benchmark dataset has the following structure:
```
AIForge_Dataset/
    images/           - Edited document images (tampered)
    masks/            - Binary tamper masks (255 = tampered, 0 = authentic)
    annotations/      - Unified annotation JSON files matching original OCR coordinates
    metadata.csv      - Unified CSV table mapping every forged document
    statistics.json   - Aggregated dataset and generation statistics
    visualizations/   - Plotted distributions and side-by-side overlays
```

## Dataset Specifications

- **Generation Method**: Hugging Face Diffusers with FLUX.1-Fill-dev masked inpainting
- **Included Datasets**: CORD, FUNSD, SROIE, XFUND
- **Tampering Type**: Semantic-preserving text replacement of high-priority fields (Totals, Prices, Quantities, Dates, IDs).
- **Masking**: Binary 1-channel mask where only the modified text bounding box is white (255).
"""
    with readme_path.open("w", encoding="utf-8") as f:
        f.write(content)
    logger.info("Saved dataset README.md to %s", readme_path)


def run_pipeline(
    documents: list,
    output_dir: Path,
    seed: int,
    max_retries: int,
    image_generator,
    progress_tracker: ProgressTracker | None = None,
    variants_per_doc: int = 2,
    shard_count: int = 1,
    shard_index: int = 0,
) -> tuple[StatsTracker, list[tuple[Path, Path, Path]]]:
    """Run deterministic variant work items, continuing after individual failures."""
    if variants_per_doc <= 0:
        raise ValueError("variants_per_doc must be positive")
    if shard_count <= 0 or shard_index < 0 or shard_index >= shard_count:
        raise ValueError("Invalid shard configuration")
    if progress_tracker is None:
        progress_tracker = ProgressTracker.load_or_create(output_dir / "progress.json", output_dir / "metadata.csv")

    stats = StatsTracker()
    sample_paths: list[tuple[Path, Path, Path]] = []
    sorted_documents = sorted(documents, key=lambda doc: doc.image_id)
    master_items = [
        (global_index, doc, variant_index)
        for global_index, (doc, variant_index) in enumerate(
            (doc, variant_index)
            for doc in sorted_documents
            for variant_index in range(variants_per_doc)
        )
    ]
    shard_items = [
        item
        for item in master_items
        if item[0] % shard_count == shard_index
    ]
    logger.info(
        "Processing %d/%d work items for shard %d/%d",
        len(shard_items),
        len(master_items),
        shard_index,
        shard_count,
    )

    for global_index, doc, variant_index in shard_items:
        item_seed = seed + global_index
        forged_image_id = f"{doc.image_id}_v{variant_index}_forged"
        try:
            paths = generate_forged_sample(
                doc=doc,
                output_dir=output_dir,
                stats=stats,
                seed=item_seed,
                max_retries=max_retries,
                image_generator=image_generator,
                progress_tracker=progress_tracker,
                variant_index=variant_index,
                num_variants=variants_per_doc,
            )
            if paths is not None:
                sample_paths.append(paths)
        except Exception as exc:
            image_id = getattr(doc, "image_id", "<unknown>")
            dataset = getattr(doc, "dataset", "<unknown>")
            logger.error(
                "Document failed; continuing. document=%s dataset=%s stage=generation reason=%s",
                image_id,
                dataset,
                exc,
                exc_info=True,
            )
            stats.record_failure()
            progress_tracker.mark_failed(forged_image_id)

    metadata_path = output_dir / "metadata.csv"
    final_stats = StatsTracker.from_metadata(
        metadata_path,
        failed_generations=stats.failed_generations,
    )
    final_stats.retry_count = max(
        stats.retry_count,
        sum(progress_tracker.retry_counts.values()),
    )
    stats_path = output_dir / "statistics.json"
    final_stats.save(stats_path)
    progress_tracker.save()
    write_readme(output_dir)

    if sample_paths:
        logger.info("Generating dataset visualizations...")
        generate_visualizations(output_dir, final_stats, sample_paths)

    return final_stats, sample_paths


def main() -> None:
    """Main pipeline execution loop."""
    args = parse_args()
    setup_logging(args.log_level)

    logger.info("Starting AIForge Document Forgery Dataset Pipeline...")
    logger.info(
        "Config: seed=%d limit=%s datasets=%s variants=%d shard=%d/%d",
        args.seed,
        args.limit,
        args.datasets,
        args.variants_per_doc,
        args.shard_index,
        args.shard_count,
    )

    # Reset project-wide RNG with input seed
    reset_rng(args.seed)
    image_generator = DiffusersGenerator.from_env()

    output_dir = args.output_dir.expanduser() if args.output_dir else resolve_output_root()
    output_dir.mkdir(parents=True, exist_ok=True)
    progress_tracker = ProgressTracker.load_or_create(output_dir / "progress.json", output_dir / "metadata.csv")

    # 1. Load authentic documents from selected datasets
    documents = load_all_datasets(
        datasets=args.datasets,
        limit=args.limit,
    )

    if not documents:
        logger.warning("No documents loaded. Exiting.")
        sys.exit(0)

    run_pipeline(
        documents=documents,
        output_dir=output_dir,
        seed=args.seed,
        max_retries=args.max_retries,
        image_generator=image_generator,
        progress_tracker=progress_tracker,
        variants_per_doc=args.variants_per_doc,
        shard_count=args.shard_count,
        shard_index=args.shard_index,
    )
    logger.info("AIForge dataset pipeline completed successfully.")


if __name__ == "__main__":
    main()
