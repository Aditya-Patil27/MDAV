"""Dempster-Shafer evidence fusion across verification branches.

Replaces the original weighted-average placeholder. Each branch emits a
``BeliefMass`` over {AUTHENTIC, FORGED} (see ``belief.py``); this service
applies a per-source **reliability discount**, combines everything with
Dempster's rule, and maps the fused belief to a decision via the pignistic
probability.

Why discounting rather than weights: a weight just scales a vote, but Shafer
discounting moves an unreliable source's committed mass into *uncertainty* --
so a weak branch dilutes toward "don't know" instead of actively voting 0.5.
A single conclusive forensic signal (broken signature, QR/printed mismatch)
therefore still dominates a pile of soft heuristics, which is the project thesis.

The output keys (``visual_score``/``semantic_score``/``signature_score``/
``final_score``/``decision``/``reason_summary``) are kept identical to the old
contract so the DB models, schemas, and frontend need no changes. Each
per-branch ``*_score`` is now that branch's pignistic P(authentic).
"""

from __future__ import annotations

import json
import os

from app.services import belief
from app.services.belief import BeliefMass, vacuous

# Per-source reliability (0..1). Crypto signatures are trusted most; layout is
# the weakest structural hint. These are the *defaults* (the cold-start prior);
# the reliability calibrator can learn better values from reviewer-confirmed
# outcomes and write them to MDAV_FUSION_CONFIG, which overrides these on load.
_DEFAULT_RELIABILITY = {
    "signature": 0.95,
    "qr": 0.90,
    "visual": 0.85,
    "diffusion": 0.80,   # AIForge AI-generated-forgery branch (when available)
    "semantic": 0.70,
    "layout": 0.40,
}

_DEFAULT_THRESHOLDS = {"approved": 0.80, "flagged": 0.50}

# Champion config written by the calibrator (see reliability_calibrator.py).
FUSION_CONFIG_PATH = os.getenv(
    "MDAV_FUSION_CONFIG",
    os.path.join(os.path.dirname(__file__), "..", "..", "config", "fusion_reliability.json"),
)


def load_fusion_config(path: str | None = None):
    """Return (reliability, thresholds), overlaying any saved champion config.

    Falls back to the built-in defaults when no config file exists -- so a fresh
    install behaves exactly as before until a calibrated config is promoted.
    """
    reliability = dict(_DEFAULT_RELIABILITY)
    thresholds = dict(_DEFAULT_THRESHOLDS)
    try:
        with open(path or FUSION_CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        reliability.update(cfg.get("reliability", {}))
        thresholds.update(cfg.get("thresholds", {}))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return reliability, thresholds


RELIABILITY, THRESHOLDS = load_fusion_config()


class FusionService:
    def fuse(self, branches: dict[str, BeliefMass]) -> dict:
        """Fuse a mapping of ``source -> raw BeliefMass`` into a decision dict.

        Vacuous / missing branches contribute nothing. The raw (undiscounted)
        masses are used for the per-branch display scores; the discounted ones
        are what actually combine.
        """
        branches = {k: v for k, v in branches.items() if v is not None}

        discounted = [
            m.discount(RELIABILITY.get(src, 0.5))
            for src, m in branches.items()
        ]
        try:
            fused = belief.fuse(discounted) if discounted else vacuous("fusion")
            conflict = float(fused.details.get("conflict", 0.0))
        except ValueError:
            # Total contradiction between sources -> cannot trust either; flag.
            fused = vacuous("fusion")
            conflict = 1.0

        final_score = fused.pignistic()
        if conflict >= 1.0:
            decision = "REVIEW_REQUIRED"
        else:
            decision = belief.decide(
                fused,
                approve_threshold=THRESHOLDS["approved"],
                review_threshold=THRESHOLDS["flagged"],
            )

        scores = {src: m.pignistic() for src, m in branches.items()}
        reason = self._reason(branches, scores, decision, conflict)

        return {
            "visual_score": round(scores.get("visual", 0.5), 4),
            "semantic_score": round(scores.get("semantic", 0.5), 4),
            "signature_score": round(scores.get("signature", 0.5), 4),
            "layout_score": round(scores.get("layout", 0.5), 4),
            "qr_score": round(scores.get("qr", 0.5), 4),
            "diffusion_score": round(scores.get("diffusion", 0.5), 4),
            "final_score": round(final_score, 4),
            "decision": decision,
            "reason_summary": reason,
            "fused_belief": fused.to_dict(),
            "conflict": round(conflict, 4),
        }

    # ---- reasoning -----------------------------------------------------------

    def _reason(self, branches, scores, decision, conflict) -> str:
        parts: list[str] = []
        labels = {
            "visual": "Visual tamper analysis",
            "semantic": "Field/checksum validation",
            "signature": "Digital signature",
            "qr": "Secure QR cross-check",
            "layout": "Document layout",
        }
        for src, mass in branches.items():
            if mass.uncertain > 0.95:  # effectively vacuous -> nothing to say
                continue
            p = scores[src]
            verdict = (
                "supports authenticity" if p >= 0.65
                else "indicates tampering" if p <= 0.35
                else "is inconclusive"
            )
            parts.append(f"{labels.get(src, src)} {verdict} (P={p:.2f})")

        if not parts:
            parts.append("No branch produced decisive evidence")
        if conflict >= 0.3:
            parts.append(f"sources partly conflict (K={conflict:.2f})")

        return ". ".join(parts) + f". Overall assessment: {decision}."


fusion_service = FusionService()
