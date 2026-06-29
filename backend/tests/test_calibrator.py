"""Tests for the reliability calibrator (pure core, no DB / ML stack)."""

from app.services.belief import from_probability
from app.services.reliability_calibrator import (
    LabeledSample,
    evaluate_cost,
    fit_reliabilities,
    propose,
)


def _make_samples(n=200):
    """A discriminative 'good' source and a near-useless 'noise' source."""
    samples = []
    for i in range(n):
        label = i % 2  # alternate authentic(1)/forged(0)
        good_p = 0.9 if label == 1 else 0.1
        samples.append(LabeledSample(
            branch_beliefs={
                "good": from_probability(good_p, confidence=0.8, source="good"),
                "noise": from_probability(0.5, confidence=0.2, source="noise"),
            },
            label=label,
        ))
    return samples


def test_fit_rewards_discriminative_source():
    rel = fit_reliabilities(_make_samples(), prior={"good": 0.5, "noise": 0.5})
    assert rel["good"] > 0.7
    assert rel["noise"] < 0.3
    assert rel["good"] > rel["noise"]


def test_fit_keeps_prior_when_one_class_only():
    # Only authentic samples -> cannot assess discrimination -> prior retained.
    samples = [
        LabeledSample({"good": from_probability(0.9, confidence=0.8, source="good")}, 1)
        for _ in range(50)
    ]
    rel = fit_reliabilities(samples, prior={"good": 0.42})
    assert rel["good"] == 0.42


def test_evaluate_cost_is_asymmetric():
    forged_but_approved = LabeledSample(
        {"x": from_probability(0.9, confidence=1.0, source="x")}, label=0)
    authentic_and_approved = LabeledSample(
        {"x": from_probability(0.9, confidence=1.0, source="x")}, label=1)
    out = evaluate_cost(
        [forged_but_approved, authentic_and_approved],
        {"x": 1.0}, approve_threshold=0.8,
    )
    assert out["false_accepts"] == 1
    assert out["true_accepts"] == 1
    assert out["mean_cost"] == 5.0  # (10 + 0) / 2


def test_propose_fits_challenger_and_gates():
    report = propose(
        _make_samples(300),
        champion_reliability={"good": 0.5, "noise": 0.5},
        seed=1, min_eval=30,
    )
    assert report["n_eval"] >= 30
    assert report["challenger_reliability"]["good"] > report["champion_reliability"]["good"]
    assert isinstance(report["promote"], bool)


def test_propose_refuses_without_enough_data():
    report = propose([], champion_reliability={"good": 0.5})
    assert report["promote"] is False
    assert "insufficient" in report["reason"]
