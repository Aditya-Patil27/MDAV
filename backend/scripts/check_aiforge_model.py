"""Load the AIForge branch and inspect one image without starting the API."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.diffusion_service import DiffusionService


def public_result(result: dict) -> dict:
    """Return the JSON-safe public branch payload without the BeliefMass object."""
    return {key: value for key, value in result.items() if key != "_mass"}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Load the local AIForge model and analyze one document image."
    )
    parser.add_argument("image", type=Path, help="path to a PNG or JPEG document")
    parser.add_argument(
        "--weights",
        type=Path,
        default=None,
        help="override MDAV_DIFFUSION_WEIGHTS for this check",
    )
    args = parser.parse_args()

    service = DiffusionService(
        model_path=str(args.weights) if args.weights is not None else None
    )
    print(f"model_loaded: {service.model_loaded}")
    print(f"backend: {service.backend}")
    print(f"weights_path: {service.model_path}")
    print(f"threshold: {service.threshold}")
    if service._load_failed_reason:
        print(f"load_status: {service._load_failed_reason}")

    result = public_result(service.analyze(str(args.image)))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
