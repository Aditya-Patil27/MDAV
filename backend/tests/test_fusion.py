"""Tests for the Dempster-Shafer FusionService.

Pure-Python: exercises only belief.py + fusion_service.py, so it runs without
torch / the ML stack.
"""

from app.services.belief import from_check, from_probability, vacuous
from app.services.fusion_service import FusionService, RELIABILITY


fusion = FusionService()


def test_all_vacuous_is_undecided():
    # Total ignorance must never be interpreted as a positive or negative vote.
    out = fusion.fuse({src: vacuous(src) for src in RELIABILITY})
    assert out["final_score"] == 0.5
    assert out["decision"] == "REVIEW_REQUIRED"
    assert out["uncertainty_mass"] == 1.0
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
    assert out["decision"] != "APPROVED"


def test_layout_is_weak_cannot_approve_alone():
    # Layout maxes at w_pass=0.40 and is discounted to 0.40 reliability, so on
    # its own it must not reach the approve threshold.
    out = fusion.fuse({"layout": from_check(True, w_pass=0.40, source="layout")})
    assert out["decision"] != "APPROVED"
    assert out["layout_score"] > 0.5  # still leans authentic, just not enough


def test_missing_branches_do_not_fabricate_neutral_scores():
    out = fusion.fuse({"visual": from_probability(0.9, confidence=0.8, source="visual")})
    assert out["semantic_score"] is None
    assert out["signature_score"] is None
    assert out["visual_score"] > 0.5


def test_reliability_discount_weakens_unreliable_source():
    # Identical raw forged belief from two sources of different reliability,
    # fused alone: the high-reliability source commits more forged mass, so its
    # pignistic sits further below 0.5.
    strong = fusion.fuse({"signature": from_check(False, w_fail=0.8, source="signature")})
    weak = fusion.fuse({"layout": from_check(False, w_fail=0.8, source="layout")})
    assert strong["final_score"] < weak["final_score"]  # signature drives forged harder


def test_branch_payload_separates_raw_and_discounted_mass_once():
    raw = from_probability(0.2, confidence=0.9, source="diffusion")
    out = fusion.fuse({"diffusion": raw})
    evidence = out["branch_evidence"]["diffusion"]
    expected = raw.discount(RELIABILITY["diffusion"])
    assert evidence["raw_mass"]["forged"] == round(raw.forged, 4)
    assert evidence["discounted_mass"]["forged"] == round(expected.forged, 4)
    assert evidence["discounted_mass"]["forged"] < evidence["raw_mass"]["forged"]


def test_decision_explanation_uses_actual_evidence_and_availability():
    out = fusion.fuse(
        {
            "visual": vacuous("visual"),
            "semantic": from_check(True, w_pass=0.55, source="semantic"),
            "diffusion": _diffusion(ai_forgery_prob=0.9, confidence=0.85),
        },
        branch_metadata={
            "visual": {"status": "unavailable"},
            "semantic": {"status": "active"},
            "diffusion": {"status": "active"},
            "signature": {"status": "not_applicable"},
        },
    )
    reason = out["reason_summary"]
    assert "Strongest authentic support is Field/checksum validation" in reason
    assert "Strongest forged support is AI-forgery localization" in reason
    assert "Unavailable branches: Visual tamper analysis" in reason
    assert "Not-applicable branches contributed no evidence: Digital signature" in reason
    assert f"Fused uncertainty is {out['uncertainty_mass'] * 100:.1f}%" in reason


def test_strong_low_uncertainty_forgery_is_flagged():
    out = fusion.fuse({
        "signature": from_check(False, w_fail=0.95, source="signature")
    })
    assert out["forged_mass"] >= 0.5
    assert out["uncertainty_mass"] < 0.35
    assert out["decision"] == "FLAGGED"


def _diffusion(ai_forgery_prob: float, confidence: float):
    # Mirrors diffusion_service.analyze: belief = from_probability(1 - prob).
    return from_probability(1.0 - ai_forgery_prob, confidence=confidence, source="diffusion")


def test_diffusion_hot_map_with_conflicting_visual_signal_requires_review():
    # A pile of weak authentic branches...
    branches = {
        "semantic": from_check(True, w_pass=0.55, source="semantic"),
        "layout": from_check(True, w_pass=0.40, source="layout"),
        "visual": from_probability(0.6, confidence=0.4, source="visual"),
        # ...versus a confident AIForge AI-forgery hit.
        "diffusion": _diffusion(ai_forgery_prob=0.97, confidence=0.9),
    }
    out = fusion.fuse(branches)
    assert out["diffusion_score"] < 0.5      # branch itself leans forged
    assert out["decision"] != "APPROVED"


def test_diffusion_catches_what_visual_misses():
    # DocTamper visual branch sees nothing (leans authentic), but the AIForge
    # branch flags diffusion-inpainting -> the fused decision must not approve.
    branches = {
        "visual": from_probability(0.7, confidence=0.6, source="visual"),
        "diffusion": _diffusion(ai_forgery_prob=0.9, confidence=0.85),
    }
    out = fusion.fuse(branches)
    assert out["final_score"] < 0.5
    assert out["decision"] != "APPROVED"


def test_correlated_visual_and_diffusion_evidence_is_not_double_counted():
    visual = from_probability(0.1, confidence=0.8, source="visual")
    diffusion = from_probability(0.1, confidence=0.8, source="diffusion")

    combined = fusion.fuse({"visual": visual, "diffusion": diffusion})
    visual_only = fusion.fuse({"visual": visual})
    diffusion_only = fusion.fuse({"diffusion": diffusion})

    # Dependent localizers are averaged before global fusion, so identical
    # texture responses do not become stronger merely because two models saw it.
    assert diffusion_only["forged_mass"] < combined["forged_mass"] < visual_only["forged_mass"]
    assert combined["branch_evidence"]["visual"]["correlation_group"] == "image_forensics"
    assert combined["branch_evidence"]["diffusion"]["correlation_group"] == "image_forensics"


def test_clean_doc_visual_and_diffusion_agree_approve():
    branches = {
        "signature": from_check(True, w_pass=0.90, source="signature"),
        "visual": from_probability(0.95, confidence=0.9, source="visual"),
        "diffusion": _diffusion(ai_forgery_prob=0.03, confidence=0.9),
    }
    out = fusion.fuse(branches)
    assert out["diffusion_score"] > 0.5      # branch leans authentic
    assert out["final_score"] >= 0.80
    assert out["decision"] == "APPROVED"
