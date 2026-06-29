"""Offline reliability-calibration job (champion/challenger).

Reads reviewer-confirmed outcomes from the DB, fits challenger source
reliabilities, and reports whether the challenger should be promoted. By default
it is **read-only** -- pass ``--promote`` to actually write the new champion
config that the fusion layer loads.

Usage (from the backend/ directory):
    python -m scripts.calibrate_reliability            # dry run, print proposal
    python -m scripts.calibrate_reliability --promote  # write champion if gated
    python -m scripts.calibrate_reliability --json      # machine-readable report
"""

import argparse
import json
import sys

from app.database import SessionLocal
from app.services.fusion_service import load_fusion_config
from app.services import reliability_calibrator as rc


def main() -> int:
    ap = argparse.ArgumentParser(description="Calibrate DS source reliabilities from feedback")
    ap.add_argument("--promote", action="store_true", help="write champion config if gated to promote")
    ap.add_argument("--json", action="store_true", help="emit the full report as JSON")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--min-eval", type=int, default=30)
    ap.add_argument("--margin", type=float, default=0.02)
    args = ap.parse_args()

    reliability, thresholds = load_fusion_config()

    db = SessionLocal()
    try:
        samples = rc.load_samples_from_db(db)
    finally:
        db.close()

    report = rc.propose(
        samples,
        champion_reliability=reliability,
        thresholds=thresholds,
        seed=args.seed,
        min_eval=args.min_eval,
        margin=args.margin,
    )

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"samples: {report['n_total']} (train {report['n_train']}, eval {report['n_eval']})")
        print(f"decision: {report['reason']}")
        if "challenger_reliability" in report:
            print("champion :", report["champion_reliability"])
            print("challenger:", report["challenger_reliability"])
            print("champion eval :", report.get("champion_eval"))
            print("challenger eval:", report.get("challenger_eval"))

    if args.promote and report.get("promote"):
        path = rc.write_champion(report, thresholds=thresholds)
        print(f"PROMOTED -> wrote champion config to {path}")
    elif args.promote:
        print("not promoted (gate not satisfied); champion unchanged")

    return 0


if __name__ == "__main__":
    sys.exit(main())
