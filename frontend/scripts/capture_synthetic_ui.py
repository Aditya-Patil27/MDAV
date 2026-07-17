"""Capture privacy-safe MDAV UI screenshots against synthetic API responses."""

from __future__ import annotations

import io
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from PIL import Image, ImageDraw
from playwright.sync_api import Route, sync_playwright


BASE_URL = "http://127.0.0.1:3001"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "ui-validation"


def _document_png(*, heatmap: bool = False) -> bytes:
    image = Image.new("RGB", (820, 520), "#f8f8f5")
    draw = ImageDraw.Draw(image)
    draw.rectangle((28, 28, 792, 492), outline="#9ca3af", width=2)
    draw.text((64, 58), "SYNTHETIC DOCUMENT - NOT REAL", fill="#111827")
    for row, width in enumerate((620, 510, 680, 430, 590, 530)):
        y = 125 + row * 52
        draw.rectangle((66, y, 66 + width, y + 12), fill="#d1d5db")
    if heatmap:
        draw.rectangle((485, 210, 710, 280), fill="#dc2626", outline="#7f1d1d", width=3)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


ACTIVITY = [
    {"date": f"2026-07-{day:02d}", "approved": day % 4 + 1, "review_required": day % 3, "flagged": 1 if day % 5 == 0 else 0}
    for day in range(3, 17)
]

HISTORY_ITEMS = [
    {
        "document_id": f"synthetic-doc-{index:03d}",
        "filename": (
            "extremely_long_synthetic_government_document_filename_for_responsive_testing_front_side.png"
            if index == 1 else f"synthetic_document_{index:02d}.png"
        ),
        "doc_type": ["aadhaar", "pan", "unknown"][index % 3],
        "doc_side": "front" if index % 3 == 1 else "unknown",
        "doc_type_confidence": 0.92 if index % 3 else 0.45,
        "doc_type_source": "ocr",
        "decision": ["REVIEW_REQUIRED", "APPROVED", "FLAGGED"][index % 3],
        "final_score": [0.56, 0.91, 0.18][index % 3],
        "uncertainty": [0.42, 0.08, 0.13][index % 3],
        "conflict": [0.11, 0.02, 0.07][index % 3],
        "active_branches": [3, 5, 4][index % 3],
        "total_branches": 6,
        "created_at": f"2026-07-{16 - index:02d}T09:30:00Z",
    }
    for index in range(1, 18)
]


def _mass(authentic: float, forged: float, uncertain: float) -> dict:
    return {"authentic": authentic, "forged": forged, "uncertain": uncertain}


def _branch(name: str, *, status: str, mass: dict, probability=None, confidence=None, reliability=0.8, reason: str, detail=None) -> dict:
    return {
        "branch": name,
        "display_name": name.replace("_", " ").title(),
        "label": name,
        "status": status,
        "applicable": status not in {"not_applicable"},
        "raw_probability": probability,
        "probability_label": "forgery" if name == "diffusion" else "tampering" if name == "visual" else None,
        "confidence": confidence,
        "reliability": reliability,
        "raw_mass": mass,
        "belief": mass,
        "mass": mass,
        "score": mass["authentic"] + 0.5 * mass["uncertain"],
        "raw_score": mass["authentic"] + 0.5 * mass["uncertain"],
        "reason": reason,
        "detail": detail or {},
    }


RESULT = {
    "document_id": "synthetic-doc-001",
    "filename": HISTORY_ITEMS[0]["filename"],
    "doc_type": "aadhaar",
    "doc_side": "front",
    "doc_type_confidence": 0.92,
    "doc_type_source": "ocr",
    "possible_doc_type": None,
    "preview_url": "/files/synthetic.png",
    "status": "completed",
    "ocr": {"raw_text": "SYNTHETIC DOCUMENT\nAadhaar 1234 5678 9012\nDOB 01/01/2000", "extracted_fields": {"aadhaar": "1234 5678 9012"}, "confidence": 0.88},
    "semantic": {
        "aadhaar_valid": True,
        "pan_valid": None,
        "dates_valid": True,
        "field_presence_valid": None,
        "consistency_score": 1.0,
        "status": "active",
        "validation_details": {"rule_statuses": {"aadhaar": "valid", "pan": "not_applicable", "dates": "valid", "field_presence": "not_evaluated"}},
    },
    "vision": {"tamper_probability": None, "confidence": 0.0, "heatmap_path": None, "explanation": "Visual model weights are unavailable."},
    "signature": {"signature_detected": False, "certificate_valid": None, "hash_valid": None, "validation_result": "NOT_APPLICABLE", "details": {}},
    "fused": {
        "visual_score": None,
        "semantic_score": 0.74,
        "signature_score": 0.5,
        "layout_score": 0.62,
        "qr_score": 0.5,
        "diffusion_score": 0.31,
        "final_score": 0.56,
        "decision_score": 0.56,
        "score_formula": "pignistic_authenticity_v1",
        "authentic_mass": 0.37,
        "forged_mass": 0.25,
        "uncertainty_mass": 0.38,
        "conflict": 0.11,
        "decision": "REVIEW_REQUIRED",
        "reason_summary": "Review required because fused uncertainty is above the configured threshold. Semantic evidence supports authenticity, while AI-generated forgery localization provides contrary localized evidence.",
        "decision_thresholds": {"approved": 0.8, "flagged": 0.5, "max_uncertainty": 0.35, "max_conflict": 0.3},
        "branches": {
            "visual": _branch("conventional visual forensics", status="unavailable", mass=_mass(0, 0, 1), reliability=0.82, reason="Model weights are unavailable."),
            "semantic": _branch("OCR and semantic validation", status="active", mass=_mass(0.48, 0.08, 0.44), confidence=0.56, reliability=0.88, reason="Aadhaar checksum and dates passed; required-field completeness was not evaluated.", detail={"consistency_score": 1.0}),
            "signature": _branch("PDF digital signature", status="not_applicable", mass=_mass(0, 0, 1), reliability=0.95, reason="Embedded PDF signature verification does not apply to image input."),
            "qr": _branch("Aadhaar Secure QR", status="not_applicable", mass=_mass(0, 0, 1), reliability=0.95, reason="QR is not expected on the submitted front side."),
            "layout": _branch("document layout detection", status="active", mass=_mass(0.26, 0.12, 0.62), confidence=0.38, reliability=0.72, reason="Expected identity-document regions were detected.", detail={"fields_detected": ["photo", "name", "identifier"]}),
            "diffusion": _branch("AI-generated forgery localization", status="active", mass=_mass(0.12, 0.50, 0.38), probability=0.83, confidence=0.62, reliability=0.76, reason="A compact region exceeded the AIForge threshold.", detail={"threshold_area": 0.014, "max_prob": 0.98, "high_quantile": 0.86, "model_type": "aiforge_segmentation"}),
        },
    },
    "created_at": "2026-07-16T09:29:00Z",
    "verified_at": "2026-07-16T09:30:00Z",
}

AUDIT = {
    "id": "synthetic-audit-001",
    "document_hash": "a" * 64,
    "verification_timestamp": "2026-07-16T09:30:00Z",
    "verification_status": "REVIEW_REQUIRED",
    "authenticity_score": 0.56,
    "previous_hash": "b" * 64,
    "block_hash": "c" * 64,
    "score_formula": "pignistic_authenticity_v1",
}


def _route(route: Route) -> None:
    url = route.request.url
    if "/api/dashboard/stats" in url:
        route.fulfill(json={"total_documents": 42, "total_verifications": 39, "approved_count": 24, "review_required_count": 11, "flagged_count": 4, "average_uncertainty": 0.22, "average_conflict": 0.07, "verifications_last_7_days": 18, "activity": ACTIVITY, "branch_availability": {"visual": {"active": 27, "total": 39, "rate": 0.692}, "semantic": {"active": 35, "total": 39, "rate": 0.897}, "signature": {"active": 8, "total": 39, "rate": 0.205}, "diffusion": {"active": 31, "total": 39, "rate": 0.795}}})
    elif "/api/dashboard/history" in url:
        query = parse_qs(urlparse(url).query)
        page_size = int(query.get("page_size", [15])[0])
        route.fulfill(json={"items": HISTORY_ITEMS[:page_size], "total": len(HISTORY_ITEMS), "page": 1, "page_size": page_size, "total_pages": (len(HISTORY_ITEMS) + page_size - 1) // page_size})
    elif "/api/documents/synthetic-doc-001/audit" in url:
        route.fulfill(json=AUDIT)
    elif "/api/documents/synthetic-doc-001" in url:
        route.fulfill(json=RESULT)
    elif "/files/heatmaps/" in url:
        route.fulfill(status=200, content_type="image/png", body=_document_png(heatmap=True))
    elif "/files/synthetic.png" in url:
        route.fulfill(status=200, content_type="image/png", body=_document_png())
    else:
        route.continue_()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    checks = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        for name, width, height in (("desktop", 1440, 1000), ("tablet", 768, 1024), ("mobile", 390, 844)):
            context = browser.new_context(viewport={"width": width, "height": height})
            page = context.new_page()
            page.route("**/*", _route)
            for route_name, path in (("dashboard", "/dashboard"), ("history", "/history"), ("results", "/results?id=synthetic-doc-001")):
                page.goto(f"{BASE_URL}{path}", wait_until="networkidle")
                page.screenshot(path=OUTPUT_DIR / f"{route_name}-{name}.png", full_page=True)
                checks.append({"page": route_name, "viewport": name, "width": width, "scroll_width": page.evaluate("document.documentElement.scrollWidth"), "overflow": page.evaluate("document.documentElement.scrollWidth > window.innerWidth")})
            context.close()
        browser.close()
    (OUTPUT_DIR / "layout-checks.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()
