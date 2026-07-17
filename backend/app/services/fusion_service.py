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

The legacy output keys (``visual_score``/``semantic_score``/
``signature_score``/``final_score``/``decision``/``reason_summary``) remain for
API compatibility. Rich fields make their meaning explicit: raw branch mass,
source reliability, discounted branch mass, final fused mass, and the exact
decision-score formula.
"""

from __future__ import annotations

import json
import os
from decimal import Decimal, ROUND_HALF_UP

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

_DEFAULT_THRESHOLDS = {
    "approved": 0.80,
    "flagged": 0.50,
    "max_uncertainty": 0.35,
    "max_conflict": 0.30,
}

SCORE_FORMULA = "pignistic_authenticity_v1"


def _format_percentage(value: float) -> str:
    """Format stored four-decimal masses like the frontend's one-decimal display."""
    percent = Decimal(str(round(float(value), 4))) * Decimal("100")
    return f"{percent.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)}%"

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
    def fuse(
        self,
        branches: dict[str, BeliefMass],
        branch_metadata: dict[str, dict] | None = None,
    ) -> dict:
        """Fuse a mapping of ``source -> raw BeliefMass`` into a decision dict.

        Vacuous / missing branches contribute nothing. The raw (undiscounted)
        masses are used for the per-branch display scores; the discounted ones
        are what actually combine.
        """
        branches = {k: v for k, v in branches.items() if v is not None}

        branch_metadata = branch_metadata or {}
        discounted_by_source = {
            src: mass.discount(RELIABILITY.get(src, 0.5))
            for src, mass in branches.items()
        }
        fusion_inputs = dict(discounted_by_source)
        correlation_adjusted = False
        visual_mass = discounted_by_source.get("visual")
        diffusion_mass = discounted_by_source.get("diffusion")
        if (
            visual_mass is not None
            and diffusion_mass is not None
            and visual_mass.uncertain < 0.999
            and diffusion_mass.uncertain < 0.999
        ):
            # Both localizers consume related RGB/DCT image evidence. Averaging
            # their discounted masses prevents one scan artifact from being
            # counted twice by Dempster's independence assumption.
            fusion_inputs.pop("visual")
            fusion_inputs.pop("diffusion")
            fusion_inputs["image_forensics"] = self._average_dependent_evidence(
                visual_mass, diffusion_mass
            )
            correlation_adjusted = True
        discounted = list(fusion_inputs.values())
        try:
            fused = belief.fuse(discounted) if discounted else vacuous("fusion")
            conflict = float(fused.details.get("conflict", 0.0))
        except ValueError:
            # Total contradiction between sources -> cannot trust either; flag.
            fused = vacuous("fusion")
            conflict = 1.0

        final_score = fused.pignistic()
        decision = belief.decide(
            fused,
            approve_threshold=THRESHOLDS["approved"],
            review_threshold=THRESHOLDS["flagged"],
            max_uncertainty=THRESHOLDS["max_uncertainty"],
            max_conflict=THRESHOLDS["max_conflict"],
            conflict=conflict,
        )

        raw_scores = {src: mass.pignistic() for src, mass in branches.items()}
        discounted_scores = {
            src: mass.pignistic() for src, mass in discounted_by_source.items()
        }
        branch_evidence = {
            src: {
                "raw_mass": branches[src].to_dict(),
                "reliability": round(RELIABILITY.get(src, 0.5), 4),
                "discounted_mass": discounted_by_source[src].to_dict(),
                "raw_pignistic_authenticity": round(raw_scores[src], 4),
                "discounted_pignistic_authenticity": round(
                    discounted_scores[src], 4
                ),
                "correlation_group": (
                    "image_forensics"
                    if correlation_adjusted and src in {"visual", "diffusion"}
                    else None
                ),
                "fusion_input": (
                    "image_forensics"
                    if correlation_adjusted and src in {"visual", "diffusion"}
                    else src
                ),
            }
            for src in branches
        }
        reason = self._reason(
            discounted_by_source,
            decision,
            conflict,
            fused,
            branch_metadata,
            correlation_adjusted=correlation_adjusted,
        )

        def display_score(source: str):
            value = discounted_scores.get(source)
            return round(value, 4) if value is not None else None

        return {
            "visual_score": display_score("visual"),
            "semantic_score": display_score("semantic"),
            "signature_score": display_score("signature"),
            "layout_score": display_score("layout"),
            "qr_score": display_score("qr"),
            "diffusion_score": display_score("diffusion"),
            "final_score": round(final_score, 4),
            "decision_score": round(final_score, 4),
            "score_formula": SCORE_FORMULA,
            "authentic_mass": round(fused.authentic, 4),
            "forged_mass": round(fused.forged, 4),
            "uncertainty_mass": round(fused.uncertain, 4),
            "decision": decision,
            "reason_summary": reason,
            "fused_belief": fused.to_dict(),
            "conflict": round(conflict, 4),
            "branch_evidence": branch_evidence,
            "decision_thresholds": dict(THRESHOLDS),
        }

    @staticmethod
    def _average_dependent_evidence(
        first: BeliefMass, second: BeliefMass
    ) -> BeliefMass:
        """Cautiously combine related sources without independence amplification."""
        return BeliefMass(
            authentic=(first.authentic + second.authentic) / 2.0,
            forged=(first.forged + second.forged) / 2.0,
            uncertain=(first.uncertain + second.uncertain) / 2.0,
            source="image_forensics",
            details={"members": [first.source, second.source]},
        )

    # ---- reasoning -----------------------------------------------------------

    def _reason(
        self,
        discounted: dict[str, BeliefMass],
        decision: str,
        conflict: float,
        fused: BeliefMass,
        metadata: dict[str, dict],
        *,
        correlation_adjusted: bool = False,
    ) -> str:
        labels = {
            "visual": "Visual tamper analysis",
            "semantic": "Field/checksum validation",
            "signature": "Digital signature",
            "qr": "Secure QR cross-check",
            "layout": "Document layout",
            "diffusion": "AI-forgery localization",
        }
        committed = [
            (src, mass)
            for src, mass in discounted.items()
            if mass.uncertain < 0.999
        ]
        unavailable = [
            labels.get(src, src)
            for src, info in metadata.items()
            if info.get("status") in {"unavailable", "error"}
        ]
        not_applicable = [
            labels.get(src, src)
            for src, info in metadata.items()
            if info.get("status") == "not_applicable"
        ]

        parts: list[str] = []
        if committed:
            auth_src, auth_mass = max(committed, key=lambda item: item[1].authentic)
            forged_src, forged_mass = max(committed, key=lambda item: item[1].forged)
            if auth_mass.authentic >= 0.05:
                parts.append(
                    f"Strongest authentic support is {labels.get(auth_src, auth_src)} "
                    f"at {_format_percentage(auth_mass.authentic)} belief"
                )
            if forged_mass.forged >= 0.05:
                parts.append(
                    f"Strongest forged support is {labels.get(forged_src, forged_src)} "
                    f"at {_format_percentage(forged_mass.forged)} belief"
                )
        else:
            parts.append("No branch produced committed evidence")

        if unavailable:
            parts.append(f"Unavailable branches: {', '.join(unavailable)}")
        if not_applicable:
            parts.append(
                f"Not-applicable branches contributed no evidence: "
                f"{', '.join(not_applicable)}"
            )
        if correlation_adjusted:
            parts.append(
                "Visual and AI-forgery localization were correlation-adjusted before fusion"
            )
        parts.append(f"Fused uncertainty is {_format_percentage(fused.uncertain)}")
        if conflict > 0:
            parts.append(f"inter-branch conflict is {_format_percentage(conflict)}")

        if decision == "APPROVED":
            conclusion = "The authentic-belief threshold was met with limited uncertainty and conflict"
        elif decision == "FLAGGED":
            conclusion = "The forged-belief threshold was met with limited uncertainty and conflict"
        else:
            conclusion = "Human review is required because evidence is incomplete, mixed, or below a decisive threshold"
        parts.append(conclusion)
        return ". ".join(parts) + "."


fusion_service = FusionService()
