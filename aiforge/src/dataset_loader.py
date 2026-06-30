"""
dataset_loader.py — Orchestrator that loads all four datasets.

Calls each dataset-specific loader and returns a flat list of
UnifiedDocument instances. This is the only module that imports
the individual loaders; all downstream modules receive the list.
"""

from __future__ import annotations

import logging
from typing import Optional

from src.schema import UnifiedDocument
from src.cord_loader import load_cord
from src.funsd_loader import load_funsd
from src.sroie_loader import load_sroie
from src.xfund_loader import load_xfund

logger = logging.getLogger(__name__)


def load_all_datasets(
    datasets: Optional[list[str]] = None,
    cord_splits: Optional[list[str]] = None,
    funsd_splits: Optional[list[str]] = None,
    sroie_splits: Optional[list[str]] = None,
    xfund_languages: Optional[list[str]] = None,
    xfund_splits: Optional[list[str]] = None,
    limit: Optional[int] = None,
) -> list[UnifiedDocument]:
    """Load all requested datasets and return a combined flat list.

    Args:
        datasets: Which datasets to include. Defaults to all four:
                  ["CORD", "FUNSD", "SROIE", "XFUND"].
        cord_splits: CORD splits to load (default: train + validation + test).
        funsd_splits: FUNSD splits to load (default: train + test).
        sroie_splits: SROIE splits to load (default: train + eval + test).
        xfund_languages: XFUND languages to load (default: all 8).
        xfund_splits: XFUND splits to load (default: train + val).
        limit: If set, cap the total number of documents returned.

    Returns:
        Flat list of UnifiedDocument instances.
    """
    if datasets is None:
        datasets = ["CORD", "FUNSD", "SROIE", "XFUND"]

    all_docs: list[UnifiedDocument] = []

    if "CORD" in datasets:
        try:
            cord_docs = load_cord(splits=cord_splits)
            all_docs.extend(cord_docs)
            logger.info("Loaded %d CORD documents", len(cord_docs))
        except Exception as exc:
            logger.error("CORD loading failed: %s", exc, exc_info=True)

    if "FUNSD" in datasets:
        try:
            funsd_docs = load_funsd(splits=funsd_splits)
            all_docs.extend(funsd_docs)
            logger.info("Loaded %d FUNSD documents", len(funsd_docs))
        except Exception as exc:
            logger.error("FUNSD loading failed: %s", exc, exc_info=True)

    if "SROIE" in datasets:
        try:
            sroie_docs = load_sroie(splits=sroie_splits)
            all_docs.extend(sroie_docs)
            logger.info("Loaded %d SROIE documents", len(sroie_docs))
        except Exception as exc:
            logger.error("SROIE loading failed: %s", exc, exc_info=True)

    if "XFUND" in datasets:
        try:
            xfund_docs = load_xfund(
                languages=xfund_languages,
                splits=xfund_splits,
            )
            all_docs.extend(xfund_docs)
            logger.info("Loaded %d XFUND documents", len(xfund_docs))
        except Exception as exc:
            logger.error("XFUND loading failed: %s", exc, exc_info=True)

    logger.info("Total documents loaded: %d", len(all_docs))

    # Sanity-check for duplicate image_ids
    seen_ids: set[str] = set()
    duplicates: list[str] = []
    for doc in all_docs:
        if doc.image_id in seen_ids:
            duplicates.append(doc.image_id)
        seen_ids.add(doc.image_id)

    if duplicates:
        logger.warning(
            "Found %d duplicate image_ids: %s …",
            len(duplicates),
            duplicates[:5],
        )

    if limit is not None:
        all_docs = all_docs[:limit]
        logger.info("Applied limit=%d -> %d documents", limit, len(all_docs))

    return all_docs
