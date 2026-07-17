"""Contract and smoke tests for the AIForge diffusion branch."""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import numpy as np
import pytest

from app.services.diffusion_service import DiffusionService


REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKPOINT = REPO_ROOT / "models" / "best_diffusion.pth"
FORGED_SAMPLE = (
    REPO_ROOT
    / "AIForge_MDAV"
    / "images"
    / "cord"
    / "test"
    / "cord_000000_forged_0.png"
)


def _missing_service(tmp_path):
    return DiffusionService(model_path=str(tmp_path / "missing.pth"))


def test_missing_weights_returns_vacuous_pending_result(tmp_path):
    service = _missing_service(tmp_path)

    result = service.analyze("unused.png")

    assert result["status"] == "pending"
    assert result["ai_forgery_prob"] is None
    assert result["confidence"] == 0.0
    assert result["_mass"].source == "diffusion"
    assert result["_mass"].uncertain == pytest.approx(1.0)
    assert result["_mass"].pignistic() == pytest.approx(0.5)


def test_module_has_no_top_level_ml_imports():
    module = importlib.import_module("app.services.diffusion_service")
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".", 1)[0]
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }

    assert imported.isdisjoint(
        {"torch", "torchvision", "jpegio", "cv2", "segmentation_models_pytorch", "transformers"}
    )


def test_import_survives_when_torch_is_unavailable(monkeypatch, tmp_path):
    module_name = "app.services.diffusion_service"
    original_import = __import__

    def guarded_import(name, *args, **kwargs):
        if name == "torch" or name.startswith("torch."):
            raise ImportError("simulated missing torch")
        return original_import(name, *args, **kwargs)

    monkeypatch.setenv("MDAV_DIFFUSION_WEIGHTS", str(tmp_path / "present.pth"))
    (tmp_path / "present.pth").write_bytes(b"not needed because torch is unavailable")
    monkeypatch.setattr("builtins.__import__", guarded_import)
    previous = sys.modules.pop(module_name, None)
    try:
        module = importlib.import_module(module_name)
        assert module.diffusion_service.model_loaded is False
        assert "ImportError" in module.diffusion_service._load_failed_reason
    finally:
        sys.modules.pop(module_name, None)
        if previous is not None:
            sys.modules[module_name] = previous


def test_threshold_aware_aggregation_reports_diagnostics(tmp_path):
    service = _missing_service(tmp_path)
    service.threshold = 0.95
    service._last_valid = (100, 100)
    prob_map = np.zeros((100, 100), dtype=np.float32)
    prob_map[40:50, 40:50] = 0.99

    probability, confidence = service._aggregate(prob_map)

    assert probability == pytest.approx(0.99, abs=1e-4)
    assert 0.70 <= confidence <= 1.0
    assert service._last_prediction_details["threshold"] == 0.95
    assert service._last_prediction_details["threshold_area"] == pytest.approx(0.01)
    assert service._last_prediction_details["positive_region_detected"] is True
    assert service._last_prediction_details["largest_component_pixels"] == 100


def test_subthreshold_map_is_inconclusive_not_forged_evidence(tmp_path):
    service = _missing_service(tmp_path)
    service.threshold = 0.95
    service._last_valid = (100, 100)
    prob_map = np.full((100, 100), 0.80, dtype=np.float32)

    probability, confidence = service._aggregate(prob_map)

    assert probability == 0.0
    assert confidence == 0.0
    assert service._last_prediction_details["positive_region_detected"] is False
    assert service._last_prediction_details["threshold_area"] == 0.0


def test_identity_document_limits_ai_forge_confidence(tmp_path):
    service = _missing_service(tmp_path)
    service.model = object()
    service.backend = "segmentation"
    service._predict = lambda _: (0.99, 0.90)
    service._last_prediction_details = {
        "positive_region_detected": True,
        "model_type": "aiforge_segmentation",
    }

    result = service.analyze("unused.png", document_type="pan")

    assert result["status"] == "active"
    assert result["confidence"] == pytest.approx(0.25)
    assert result["details"]["domain_limited"] is True


def test_no_positive_segmentation_region_returns_vacuous_inconclusive(tmp_path):
    service = _missing_service(tmp_path)
    service.model = object()
    service.backend = "segmentation"

    def no_region(_):
        service._last_prediction_details = {
            "positive_region_detected": False,
            "threshold": 0.95,
        }
        return 0.0, 0.0

    service._predict = no_region
    result = service.analyze("unused.png")

    assert result["status"] == "inconclusive"
    assert result["ai_forgery_prob"] is None
    assert result["_mass"].uncertain == pytest.approx(1.0)


def test_analyze_includes_segmentation_details_in_belief(tmp_path):
    service = _missing_service(tmp_path)
    service.model = object()
    service.threshold = 0.95
    service._last_prediction_details = {
        "threshold": 0.95,
        "threshold_area": 0.012,
        "max_prob": 0.99,
        "high_quantile": 0.97,
        "model_type": "aiforge_segmentation",
    }
    service._predict = lambda _: (0.97, 0.99)

    result = service.analyze("unused.png")

    assert result["status"] == "active"
    assert result["_mass"].details["model_type"] == "aiforge_segmentation"
    assert result["_mass"].details["threshold"] == 0.95
    assert result["_mass"].details["threshold_area"] == 0.012


def test_high_ai_prob_maps_to_forged_belief(tmp_path):
    service = _missing_service(tmp_path)
    service.model = object()
    service._predict = lambda _: (0.95, 0.9)

    result = service.analyze("unused.png")

    assert result["status"] == "active"
    assert result["ai_forgery_prob"] == 0.95
    assert result["_mass"].forged > result["_mass"].authentic
    assert result["_mass"].pignistic() < 0.5


def test_low_ai_prob_maps_to_authentic_belief(tmp_path):
    service = _missing_service(tmp_path)
    service.model = object()
    service._predict = lambda _: (0.02, 0.9)

    result = service.analyze("unused.png")

    assert result["status"] == "active"
    assert result["_mass"].authentic > result["_mass"].forged
    assert result["_mass"].pignistic() > 0.5


def test_invalid_image_returns_vacuous_error(tmp_path):
    service = _missing_service(tmp_path)
    service.model = object()

    result = service.analyze(str(tmp_path / "not-an-image.png"))

    assert result["status"] == "error"
    assert result["ai_forgery_prob"] is None
    assert result["_mass"].uncertain == pytest.approx(1.0)


def test_predict_failure_stays_vacuous(tmp_path):
    service = _missing_service(tmp_path)
    service.model = object()

    def boom(_path):
        raise RuntimeError("bad image")

    service._predict = boom
    result = service.analyze("unused.png")

    assert result["status"] == "error"
    assert result["_mass"].uncertain == pytest.approx(1.0)


def test_check_script_serializes_public_result(tmp_path):
    from scripts.check_aiforge_model import public_result

    service = _missing_service(tmp_path)
    result = public_result(service.analyze("unused.png"))

    assert "_mass" not in result
    assert result["status"] == "pending"
    assert result["belief"]["uncertain"] == pytest.approx(1.0)


@pytest.fixture(scope="session")
def loaded_real_service():
    if not CHECKPOINT.exists():
        pytest.skip("models/best_diffusion.pth is not available")
    for dependency in ("torch", "torchvision", "segmentation_models_pytorch"):
        try:
            importlib.import_module(dependency)
        except Exception as exc:  # noqa: BLE001 - optional local ML stack
            pytest.skip(f"optional ML dependency {dependency!r} unavailable: {exc}")

    service = DiffusionService(model_path=str(CHECKPOINT))
    assert service.model_loaded, service._load_failed_reason
    return service


def test_real_checkpoint_loads_with_metadata_contract(loaded_real_service):
    service = loaded_real_service
    assert service.backend == "segmentation"
    assert service.threshold == pytest.approx(0.95)
    assert service.architecture["dct_bins"] == 21
    assert service.architecture["dct_dim"] == 16
    assert service.architecture["jpeg_quality"] == 95
    assert service.architecture["classes"] == 2


def test_clean_sample_is_low_when_available(loaded_real_service):
    try:
        importlib.import_module("jpegio")
    except Exception as exc:  # noqa: BLE001 - optional native dependency
        pytest.skip(f"optional ML dependency 'jpegio' unavailable: {exc}")
    clean_candidates = [
        path
        for path in (REPO_ROOT / "test_samples").glob("**/*")
        if path.suffix.lower() in {".png", ".jpg", ".jpeg"}
    ]
    if not clean_candidates:
        pytest.skip("no suitable clean image is available under test_samples/")

    probability, confidence = loaded_real_service._predict(str(clean_candidates[0]))
    assert 0.0 <= confidence <= 1.0
    assert probability < 0.60


def test_aiforge_sample_is_high_when_available(loaded_real_service):
    try:
        importlib.import_module("jpegio")
    except Exception as exc:  # noqa: BLE001 - optional native dependency
        pytest.skip(f"optional ML dependency 'jpegio' unavailable: {exc}")
    if not FORGED_SAMPLE.exists():
        pytest.skip("AIForge forged sample is not available")

    probability, confidence = loaded_real_service._predict(str(FORGED_SAMPLE))
    assert 0.0 <= confidence <= 1.0
    assert probability >= 0.60
