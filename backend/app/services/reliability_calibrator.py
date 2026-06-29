"""Online calibration of Dempster-Shafer source reliabilities from feedback.

The fusion layer discounts each branch by a per-source *reliability*. Those start
as hand-set priors (``fusion_service._DEFAULT_RELIABILITY``); this module learns
better values from reviewer-confirmed outcomes and proposes them behind a
**champion/challenger** gate -- a challenger is only promoted if it beats the
current champion on a held-out split under an asymmetric cost (a false-accept of
a forged document is far worse than a false-reject).

Design notes
------------
* The core (``fit_reliabilities``, ``evaluate_cost``, ``propose``) is pure and
  operates on ``LabeledSample`` objects, so it is unit-testable without a DB.
* Reliability is estimated interpretably: a source's reliability is how well its
  own pignistic separates authentic from forged (balanced accuracy), shrunk
  toward the prior when evidence is thin. A source no better than chance -> ~0
  reliability (it stops influencing fusion); a discriminative source -> ~1.
* Nothing here touches the live config. ``write_champion`` is the only writer,
  and the CLI only calls it on an explicit ``--promote``.
"""

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field

from app.services import belief
from app.services.belief import BeliefMass
from app.services.fusion_service import _DEFAULT_RELIABILITY, _DEFAULT_THRESHOLDS

# Asymmetric misclassification costs (forged-accepted is the expensive mistake).
COST_FALSE_ACCEPT = 10.0   # approved a forged document
COST_FALSE_REJECT = 1.0    # did not approve an authentic document

_VACUOUS_UNCERTAIN = 0.95  # a branch this ignorant contributed no real evidence


@dataclass
class LabeledSample:
    """One reviewer-confirmed verification: raw per-branch beliefs + truth."""
    branch_beliefs: dict[str, BeliefMass]
    label: int  # 1 = authentic, 0 = forged
    meta: dict = field(default_factory=dict)


def belief_from_dict(d: dict, source: str = "") -> BeliefMass:
    return BeliefMass(
        authentic=float(d["authentic"]),
        forged=float(d["forged"]),
        uncertain=float(d["uncertain"]),
        source=source,
    )


def _is_committed(m: BeliefMass) -> bool:
    return m.uncertain < _VACUOUS_UNCERTAIN


# ---- fitting -----------------------------------------------------------------


def fit_reliabilities(
    samples: list[LabeledSample],
    *,
    sources: list[str] | None = None,
    prior: dict[str, float] | None = None,
    n_min: int = 20,
) -> dict[str, float]:
    """Estimate each source's reliability from its discriminative accuracy.

    reliability_s = w * clamp(2*(balanced_accuracy_s - 0.5), 0, 1) + (1-w)*prior_s
    where w = n / (n + n_min) shrinks thin-evidence sources toward the prior.
    """
    prior = prior or _DEFAULT_RELIABILITY
    sources = sources or sorted({s for smp in samples for s in smp.branch_beliefs})

    out: dict[str, float] = {}
    for s in sources:
        pos_hits = pos_n = neg_hits = neg_n = 0
        for smp in samples:
            m = smp.branch_beliefs.get(s)
            if m is None or not _is_committed(m):
                continue
            p = m.pignistic()
            if smp.label == 1:
                pos_n += 1
                pos_hits += 1 if p > 0.5 else 0
            else:
                neg_n += 1
                neg_hits += 1 if p < 0.5 else 0

        prior_s = prior.get(s, 0.5)
        if pos_n == 0 or neg_n == 0:
            # Can't assess discrimination (only one class seen) -> keep the prior.
            out[s] = prior_s
            continue
        tpr = pos_hits / pos_n
        tnr = neg_hits / neg_n
        bal_acc = 0.5 * (tpr + tnr)
        disc = max(0.0, min(1.0, 2.0 * (bal_acc - 0.5)))
        n = pos_n + neg_n
        w = n / (n + n_min)
        out[s] = round(w * disc + (1.0 - w) * prior_s, 4)
    return out


# ---- evaluation --------------------------------------------------------------


def fused_pignistic(sample: LabeledSample, reliability: dict[str, float]) -> float:
    discounted = [
        m.discount(reliability.get(src, 0.5))
        for src, m in sample.branch_beliefs.items()
    ]
    if not discounted:
        return 0.5
    try:
        return belief.fuse(discounted).pignistic()
    except ValueError:  # total conflict -> maximally undecided
        return 0.5


def evaluate_cost(
    samples: list[LabeledSample],
    reliability: dict[str, float],
    *,
    approve_threshold: float,
    c_false_accept: float = COST_FALSE_ACCEPT,
    c_false_reject: float = COST_FALSE_REJECT,
) -> dict:
    """Mean asymmetric cost (and confusion counts) over ``samples``."""
    fa = fr = tp = tn = 0
    total = 0.0
    for smp in samples:
        p = fused_pignistic(smp, reliability)
        approved = p >= approve_threshold
        if approved and smp.label == 0:
            fa += 1
            total += c_false_accept
        elif not approved and smp.label == 1:
            fr += 1
            total += c_false_reject
        elif approved and smp.label == 1:
            tp += 1
        else:
            tn += 1
    n = len(samples) or 1
    return {
        "mean_cost": round(total / n, 4),
        "false_accepts": fa,
        "false_rejects": fr,
        "true_accepts": tp,
        "true_rejects": tn,
        "n": len(samples),
    }


# ---- champion / challenger ---------------------------------------------------


def propose(
    samples: list[LabeledSample],
    *,
    champion_reliability: dict[str, float] | None = None,
    thresholds: dict[str, float] | None = None,
    seed: int = 42,
    eval_frac: float = 0.3,
    min_eval: int = 30,
    margin: float = 0.02,
    n_min: int = 20,
) -> dict:
    """Fit a challenger on a train split and gate it against the champion.

    Returns a report; ``promote=True`` only when the challenger's held-out cost
    beats the champion by at least ``margin`` (relative) and there is enough
    held-out data to trust the comparison.
    """
    champion_reliability = champion_reliability or dict(_DEFAULT_RELIABILITY)
    thresholds = thresholds or dict(_DEFAULT_THRESHOLDS)
    approve = thresholds["approved"]

    rng = random.Random(seed)
    shuffled = samples[:]
    rng.shuffle(shuffled)
    cut = int(len(shuffled) * (1 - eval_frac))
    train, eval_ = shuffled[:cut], shuffled[cut:]

    report = {
        "n_total": len(samples),
        "n_train": len(train),
        "n_eval": len(eval_),
        "champion_reliability": champion_reliability,
        "promote": False,
        "reason": "",
    }

    if len(eval_) < min_eval:
        report["reason"] = f"insufficient held-out data ({len(eval_)} < {min_eval})"
        return report

    challenger = fit_reliabilities(
        train, sources=sorted(champion_reliability), prior=champion_reliability, n_min=n_min
    )
    champ_eval = evaluate_cost(eval_, champion_reliability, approve_threshold=approve)
    chal_eval = evaluate_cost(eval_, challenger, approve_threshold=approve)

    report["challenger_reliability"] = challenger
    report["champion_eval"] = champ_eval
    report["challenger_eval"] = chal_eval

    champ_cost = champ_eval["mean_cost"]
    chal_cost = chal_eval["mean_cost"]
    improved = chal_cost <= champ_cost * (1 - margin)
    # Never promote something that increases the expensive error.
    safe = chal_eval["false_accepts"] <= champ_eval["false_accepts"]

    report["promote"] = bool(improved and safe)
    report["reason"] = (
        f"challenger cost {chal_cost} vs champion {champ_cost} "
        f"(FA {chal_eval['false_accepts']} vs {champ_eval['false_accepts']}); "
        + ("promote" if report["promote"] else "keep champion")
    )
    return report


# ---- persistence + DB adapter ------------------------------------------------


def write_champion(report: dict, *, path: str | None = None, thresholds: dict | None = None) -> str:
    """Write the challenger reliabilities as the new champion config file."""
    from app.services.fusion_service import FUSION_CONFIG_PATH, _DEFAULT_THRESHOLDS

    path = path or FUSION_CONFIG_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        "reliability": report["challenger_reliability"],
        "thresholds": thresholds or _DEFAULT_THRESHOLDS,
        "meta": {
            "n_train": report.get("n_train"),
            "n_eval": report.get("n_eval"),
            "champion_eval": report.get("champion_eval"),
            "challenger_eval": report.get("challenger_eval"),
        },
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return path


def load_samples_from_db(db) -> list[LabeledSample]:
    """Join persisted per-branch beliefs (FusedResult) with reviewer labels."""
    from app.models.models import FusedResult, ReviewFeedback

    samples: list[LabeledSample] = []
    for fb in db.query(ReviewFeedback).all():
        if fb.true_label not in ("authentic", "forged"):
            continue
        fused = db.query(FusedResult).filter(FusedResult.job_id == fb.job_id).first()
        if not fused or not fused.branches:
            continue
        beliefs: dict[str, BeliefMass] = {}
        for src, info in fused.branches.items():
            b = info.get("belief") if isinstance(info, dict) else None
            if not b:
                continue
            try:
                beliefs[src] = belief_from_dict(b, source=src)
            except (KeyError, TypeError, ValueError):
                continue
        if beliefs:
            samples.append(LabeledSample(beliefs, 1 if fb.true_label == "authentic" else 0,
                                         meta={"job_id": fb.job_id}))
    return samples
