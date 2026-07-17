"""Evidence helpers shared by pixel-level forgery localizers.

Segmentation logits describe pixels, not a calibrated document verdict.  This
module therefore requires a coherent above-threshold component before a branch
commits forged evidence.  It intentionally has no torch dependency.
"""

from __future__ import annotations

from typing import Any


def summarize_positive_regions(
    probability_map: Any,
    *,
    threshold: float,
    min_component_pixels: int,
) -> dict[str, float | int | bool]:
    """Summarize above-threshold connected regions in a probability map.

    ``cv2`` is available in the production image.  If it is unavailable, a
    conservative fallback treats all positive pixels as one candidate instead
    of failing the verification flow.
    """
    import numpy as np

    values = np.asarray(probability_map, dtype=np.float32)
    if values.ndim != 2 or values.size == 0:
        raise ValueError("probability map must be a non-empty two-dimensional array")
    if not 0.0 < threshold < 1.0:
        raise ValueError("pixel threshold must be between zero and one")
    if min_component_pixels < 1:
        raise ValueError("minimum component size must be positive")

    mask = values >= threshold
    threshold_area = float(mask.mean())
    positive_pixels = int(mask.sum())
    candidates: list[tuple[int, Any]] = []
    components_available = True

    if positive_pixels:
        try:
            import cv2

            component_count, labels, stats, _ = cv2.connectedComponentsWithStats(
                mask.astype("uint8"), connectivity=8
            )
            for component_id in range(1, component_count):
                pixels = int(stats[component_id, cv2.CC_STAT_AREA])
                if pixels >= min_component_pixels:
                    candidates.append((pixels, labels == component_id))
            raw_component_count = component_count - 1
        except ImportError:
            # Keep the branch fail-soft outside the Docker image. This fallback
            # is deliberately less permissive than silently accepting a peak.
            components_available = False
            raw_component_count = 1
            if positive_pixels >= min_component_pixels:
                candidates.append((positive_pixels, mask))
    else:
        raw_component_count = 0

    details: dict[str, float | int | bool] = {
        "threshold_area": threshold_area,
        "positive_pixels": positive_pixels,
        "component_count": int(raw_component_count),
        "valid_component_count": len(candidates),
        "min_component_pixels": int(min_component_pixels),
        "components_available": components_available,
        "positive_region_detected": bool(candidates),
    }
    if not candidates:
        return details

    # Prefer confidence first, then area when two regions have equal strength.
    selected_size, selected_mask = max(
        candidates,
        key=lambda item: (float(np.quantile(values[item[1]], 0.95)), item[0]),
    )
    selected_values = values[selected_mask]
    details.update(
        {
            "largest_component_pixels": int(selected_size),
            "largest_component_area": float(selected_size / values.size),
            "largest_component_mean": float(selected_values.mean()),
            "largest_component_quantile": float(np.quantile(selected_values, 0.95)),
            "largest_component_max": float(selected_values.max()),
        }
    )
    return details
