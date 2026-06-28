"""Shared belief-mass contract for Dempster-Shafer evidence fusion.

Every verification branch (semantic, QR, signature, visual/.pth) emits a
``BeliefMass`` over the frame of discernment {AUTHENTIC, FORGED}. The power
set has three focal elements:

    m({AUTHENTIC})  -> belief the document is authentic
    m({FORGED})     -> belief the document is forged
    m({A, F}) = uncertain -> uncommitted mass (ignorance)

m(empty set) is fixed at 0. The three masses are non-negative and sum to 1.

Why Dempster-Shafer instead of a weighted average: it represents *ignorance*
explicitly (a branch that has no evidence stays vacuous instead of voting 0.5),
and the combination rule is naturally asymmetric -- a single failed
deterministic check (invalid Verhoeff, broken signature) drives strong FORGED
mass that a pile of weak AUTHENTIC evidence cannot wash out.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

_EPS = 1e-9


@dataclass(frozen=True)
class BeliefMass:
    """A mass assignment over {AUTHENTIC, FORGED} plus the uncertain superset.

    Construct via the factory helpers (``vacuous``, ``from_check``,
    ``from_probability``) rather than raw numbers where possible -- they encode
    the asymmetry policy in one place.
    """

    authentic: float
    forged: float
    uncertain: float
    source: str = ""
    details: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("authentic", "forged", "uncertain"):
            v = getattr(self, name)
            if v < -_EPS:
                raise ValueError(f"{self.source or 'belief'}: negative mass {name}={v}")
        total = self.authentic + self.forged + self.uncertain
        if total < _EPS:
            raise ValueError(f"{self.source or 'belief'}: masses sum to zero")
        # Normalise to guard against floating-point drift / loose callers.
        if abs(total - 1.0) > 1e-6:
            object.__setattr__(self, "authentic", self.authentic / total)
            object.__setattr__(self, "forged", self.forged / total)
            object.__setattr__(self, "uncertain", self.uncertain / total)

    # ---- evidential measures -------------------------------------------------

    def belief(self) -> float:
        """Bel(AUTHENTIC) -- mass that necessarily supports authenticity."""
        return self.authentic

    def plausibility(self) -> float:
        """Pl(AUTHENTIC) -- mass not committed against authenticity."""
        return self.authentic + self.uncertain

    def pignistic(self) -> float:
        """Pignistic probability of AUTHENTIC: split uncertain mass evenly.

        This is the calibrated scalar a downstream threshold consumes; it is
        what makes branches comparable to the visual ``.pth`` probability.
        """
        return self.authentic + self.uncertain / 2.0

    # ---- transforms ----------------------------------------------------------

    def discount(self, reliability: float) -> "BeliefMass":
        """Shafer discounting: scale committed mass by source reliability.

        reliability=1.0 trusts the source fully; reliability=0.0 makes it
        vacuous. Discounting *before* combination is how branches are weighted
        asymmetrically (e.g. trust signature > semantic heuristics).
        """
        a = max(0.0, min(1.0, reliability))
        return BeliefMass(
            authentic=self.authentic * a,
            forged=self.forged * a,
            uncertain=1.0 - a * (self.authentic + self.forged),
            source=self.source,
            details=self.details,
        )

    def combine(self, other: "BeliefMass") -> "BeliefMass":
        """Dempster's rule of combination with conflict normalisation."""
        a1, f1, u1 = self.authentic, self.forged, self.uncertain
        a2, f2, u2 = other.authentic, other.forged, other.uncertain

        # Conflict = mass assigned to AUTHENTIC by one and FORGED by the other.
        conflict = a1 * f2 + f1 * a2
        norm = 1.0 - conflict
        if norm < _EPS:
            raise ValueError(
                f"total conflict combining {self.source!r} and {other.source!r}"
            )

        authentic = (a1 * a2 + a1 * u2 + u1 * a2) / norm
        forged = (f1 * f2 + f1 * u2 + u1 * f2) / norm
        uncertain = (u1 * u2) / norm

        src = "+".join(s for s in (self.source, other.source) if s)
        return BeliefMass(
            authentic=authentic,
            forged=forged,
            uncertain=uncertain,
            source=src,
            details={"conflict": conflict, **self.details, **other.details},
        )

    # ---- serialisation -------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "authentic": round(self.authentic, 4),
            "forged": round(self.forged, 4),
            "uncertain": round(self.uncertain, 4),
            "belief": round(self.belief(), 4),
            "plausibility": round(self.plausibility(), 4),
            "pignistic": round(self.pignistic(), 4),
            "source": self.source,
            "details": self.details,
        }


# ---- factories ---------------------------------------------------------------


def vacuous(source: str = "") -> BeliefMass:
    """Total ignorance: no evidence either way (the safe default)."""
    return BeliefMass(authentic=0.0, forged=0.0, uncertain=1.0, source=source)


def from_check(
    passed: bool,
    *,
    w_pass: float = 0.5,
    w_fail: float = 0.9,
    source: str = "",
    details: dict | None = None,
) -> BeliefMass:
    """Belief from a single deterministic check, with built-in asymmetry.

    A passed check (e.g. a valid Verhoeff checksum) is *weak* evidence of
    authenticity -- a forger can produce a valid checksum -- so ``w_pass`` is
    modest and the rest stays uncertain. A failed check is *strong* evidence of
    forgery, so ``w_fail`` is high. Defaults encode exactly that asymmetry.
    """
    details = details or {}
    if passed:
        return BeliefMass(
            authentic=w_pass, forged=0.0, uncertain=1.0 - w_pass,
            source=source, details=details,
        )
    return BeliefMass(
        authentic=0.0, forged=w_fail, uncertain=1.0 - w_fail,
        source=source, details=details,
    )


def from_probability(
    p_authentic: float,
    *,
    confidence: float = 1.0,
    source: str = "",
    details: dict | None = None,
) -> BeliefMass:
    """Belief from a calibrated probability (e.g. the visual ``.pth`` output).

    ``confidence`` (0..1) controls how much committed mass the probability
    carries vs. how much is left uncertain -- a low-confidence model output
    stays mostly vacuous. This is the adapter the Kaggle-trained localizer
    plugs into: ``from_probability(1 - tamper_prob, confidence=model_conf)``.
    """
    p = max(0.0, min(1.0, p_authentic))
    c = max(0.0, min(1.0, confidence))
    details = details or {}
    return BeliefMass(
        authentic=p * c,
        forged=(1.0 - p) * c,
        uncertain=1.0 - c,
        source=source,
        details=details,
    )


def fuse(masses: Iterable[BeliefMass]) -> BeliefMass:
    """Combine many branch beliefs via Dempster's rule (order-independent)."""
    masses = [m for m in masses if m is not None]
    if not masses:
        return vacuous("fusion")
    result = masses[0]
    for m in masses[1:]:
        result = result.combine(m)
    return result


def decide(
    mass: BeliefMass,
    *,
    approve_threshold: float = 0.80,
    review_threshold: float = 0.50,
) -> str:
    """Map a fused belief to a decision using the pignistic probability."""
    p = mass.pignistic()
    if p >= approve_threshold:
        return "APPROVED"
    if p >= review_threshold:
        return "FLAGGED"
    return "REVIEW_REQUIRED"
