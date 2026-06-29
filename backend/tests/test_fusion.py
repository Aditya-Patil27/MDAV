"""Tests for the Dempster-Shafer FusionService.

Pure-Python: exercises only belief.py + fusion_service.py, so it runs without
torch / the ML stack.
"""

from app.services.belief import from_check, from_probability, vacuous
from app.services.fusion_service import FusionService, RELIABILITY


fusion = FusionService()


def test_all_vacuous_is_undecided():
    # Total ignorance -> pignistic 0.5, which sits exactly on the review/flag
    # boundary (decide treats >= 0.50 as FLAGGED), and zero conflict.
    out = fusion.fuse({src: vacuous(src) for src in RELIABILITY})
    assert out["final_score"] == 0.5
    assert out["decision"] == "FLAGGED"
    assert out["conflict"] == 0.0


def test_strong_authentic_branches_approve():
    branches = {
        "signature": from_check(True, w_pass=0.90, source="signature"),
        "semantic": from_check(True, w_pass=0.55, source="semantic"),
        "visual": from_probability(0.95, confidence=0.9, source="visual"),
    }
    out = fusion.fuse(branches)
    assert out["final_score"] >= 0.80
    assert out["decision"] == "APPROVED"


def test_one_conclusive_forgery_overrides_soft_authentic_pile():
    # A pile of weak authentic signals...
    branches = {
        "semantic": from_check(True, w_pass=0.55, source="semantic"),
        "layout": from_check(True, w_pass=0.40, source="layout"),
        "visual": from_probability(0.7, confidence=0.5, source="visual"),
        # ...versus one near-conclusive forensic forgery signal.
        "qr": from_check(False, w_fail=0.95, source="qr"),
    }
    out = fusion.fuse(branches)
    assert out["final_score"] < 0.5
    assert out["decision"] == "REVIEW_REQUIRED"


def test_layout_is_weak_cannot_approve_alone():
    # Layout maxes at w_pass=0.40 and is discounted to 0.40 reliability, so on
    # its own it must not reach the approve threshold.
    out = fusion.fuse({"layout": from_check(True, w_pass=0.40, source="layout")})
    assert out["decision"] != "APPROVED"
    assert out["layout_score"] > 0.5  # still leans authentic, just not enough


def test_missing_branches_default_to_neutral_scores():
    out = fusion.fuse({"visual": from_probability(0.9, confidence=0.8, source="visual")})
    # Branches that did not run report a neutral 0.5 display score.
    assert out["semantic_score"] == 0.5
    assert out["signature_score"] == 0.5
    assert out["visual_score"] > 0.5


def test_reliability_discount_weakens_unreliable_source():
    # Identical raw forged belief from two sources of different reliability,
    # fused alone: the high-reliability source commits more forged mass, so its
    # pignistic sits further below 0.5.
    strong = fusion.fuse({"signature": from_check(False, w_fail=0.8, source="signature")})
    weak = fusion.fuse({"layout": from_check(False, w_fail=0.8, source="layout")})
    assert strong["final_score"] < weak["final_score"]  # signature drives forged harder
