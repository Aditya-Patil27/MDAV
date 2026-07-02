"""Tests for the DiffusionService (AI-generated forgery branch).

Runs without torch/transformers: the model fails to load (mock mode), and belief
mapping is checked by injecting a fake ``_predict`` -- so these exercise the
branch contract, not the heavy classifier.
"""

from app.services.diffusion_service import DiffusionService


def _mock_service():
    # A bogus model id -> load fails -> service is in mock mode (model is None).
    return DiffusionService(model_id="___no_such_model___")


def test_no_model_is_vacuous_and_pending():
    out = _mock_service().analyze("anything.png")
    assert out["status"] in ("pending", "error")
    assert out["ai_forgery_prob"] is None
    assert out["_mass"].uncertain == 1.0          # vacuous -> contributes nothing
    assert out["_mass"].pignistic() == 0.5


def test_high_ai_prob_maps_to_forged_belief():
    svc = _mock_service()
    svc.model = object()                          # pretend a model is loaded
    svc._predict = lambda path: (0.95, 0.9)       # confident AI-generated
    out = svc.analyze("x.png")
    assert out["status"] == "active"
    assert out["ai_forgery_prob"] == 0.95
    m = out["_mass"]
    assert m.forged > m.authentic                 # belief leans FORGED
    assert m.pignistic() < 0.5


def test_low_ai_prob_maps_to_authentic_belief():
    svc = _mock_service()
    svc.model = object()
    svc._predict = lambda path: (0.02, 0.9)       # confident real/human
    out = svc.analyze("x.png")
    assert out["status"] == "active"
    m = out["_mass"]
    assert m.authentic > m.forged                 # belief leans AUTHENTIC
    assert m.pignistic() > 0.5


def test_predict_failure_stays_vacuous():
    svc = _mock_service()
    svc.model = object()

    def boom(path):
        raise RuntimeError("bad image")

    svc._predict = boom
    out = svc.analyze("x.png")
    assert out["status"] == "error"
    assert out["_mass"].uncertain == 1.0
