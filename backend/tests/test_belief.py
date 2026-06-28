"""Tests for the Dempster-Shafer belief-mass contract."""

import math

import pytest

from app.services.belief import (
    BeliefMass,
    decide,
    from_check,
    from_probability,
    fuse,
    vacuous,
)


def approx(a, b, tol=1e-6):
    return math.isclose(a, b, abs_tol=tol)


def test_masses_normalise_to_one():
    m = BeliefMass(authentic=2.0, forged=1.0, uncertain=1.0)
    assert approx(m.authentic + m.forged + m.uncertain, 1.0)
    assert approx(m.authentic, 0.5)


def test_negative_mass_rejected():
    with pytest.raises(ValueError):
        BeliefMass(authentic=-0.1, forged=0.5, uncertain=0.6)


def test_vacuous_is_pure_uncertainty():
    m = vacuous("x")
    assert m.uncertain == 1.0
    assert m.belief() == 0.0
    assert m.plausibility() == 1.0
    assert approx(m.pignistic(), 0.5)


def test_from_check_is_asymmetric():
    passed = from_check(True, w_pass=0.5, w_fail=0.9)
    failed = from_check(False, w_pass=0.5, w_fail=0.9)
    # A failed check commits more mass than a passed one (forgery is conclusive).
    assert failed.forged > passed.authentic
    assert approx(passed.authentic, 0.5)
    assert approx(failed.forged, 0.9)


def test_discount_reduces_committed_mass():
    m = from_check(True, w_pass=0.8)
    d = m.discount(0.5)
    assert approx(d.authentic, 0.4)
    assert d.uncertain > m.uncertain
    # Full discount -> vacuous.
    assert approx(m.discount(0.0).uncertain, 1.0)


def test_dempster_agreement_reinforces():
    a = from_check(True, w_pass=0.6, source="a")
    b = from_check(True, w_pass=0.6, source="b")
    combined = a.combine(b)
    # Two agreeing AUTHENTIC sources exceed either alone.
    assert combined.authentic > 0.6
    assert combined.source == "a+b"


def test_dempster_conflict_normalised():
    a = from_check(True, w_pass=0.9, source="a")
    b = from_check(False, w_fail=0.9, source="b")
    combined = a.combine(b)
    assert approx(combined.authentic + combined.forged + combined.uncertain, 1.0)
    assert "conflict" in combined.details


def test_total_conflict_raises():
    a = BeliefMass(authentic=1.0, forged=0.0, uncertain=0.0, source="a")
    b = BeliefMass(authentic=0.0, forged=1.0, uncertain=0.0, source="b")
    with pytest.raises(ValueError):
        a.combine(b)


def test_one_strong_forgery_overrides_weak_authentic_pile():
    weak = [from_check(True, w_pass=0.4) for _ in range(4)]
    strong_forged = from_check(False, w_fail=0.95)
    fused = fuse(weak + [strong_forged])
    # The single conclusive forgery signal wins -> not approved.
    assert fused.forged > fused.authentic
    assert decide(fused) != "APPROVED"


def test_from_probability_respects_confidence():
    high = from_probability(0.9, confidence=1.0)
    low = from_probability(0.9, confidence=0.2)
    assert approx(high.uncertain, 0.0)
    assert approx(low.uncertain, 0.8)
    assert high.authentic > low.authentic


def test_decide_thresholds():
    assert decide(from_probability(0.95)) == "APPROVED"
    assert decide(from_probability(0.6)) == "FLAGGED"
    assert decide(from_probability(0.2)) == "REVIEW_REQUIRED"


def test_fuse_empty_is_vacuous():
    assert fuse([]).uncertain == 1.0
