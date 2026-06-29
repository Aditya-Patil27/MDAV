"""Standalone ML inference service for visual tamper detection.

Exposes the DocTamper VisualTamperDetector over HTTP so the backend can
call it as a microservice. If no trained weights are present at MODEL_PATH the
service returns a clearly-flagged mock prediction so the pipeline stays usable
in demo mode.
"""
import os
import tempfile

from fastapi import FastAPI, File, UploadFile

from model import VisualTamperDetector

MODEL_PATH = os.getenv("MDAV_VISION_WEIGHTS", os.getenv("MODEL_PATH", "/app/models/best.pth"))

app = FastAPI(
    title="MDAV ML Service",
    description="Visual tamper localization (DocTamper DCT+RGB U-Net)",
    version="1.0.0",
)

detector = VisualTamperDetector(model_path=MODEL_PATH if os.path.exists(MODEL_PATH) else None)


@app.get("/")
async def root():
    return {"message": "MDAV ML service is running", "model_loaded": detector.model is not None}


@app.get("/health")
async def health():
    return {"status": "healthy", "model_loaded": detector.model is not None}


@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    suffix = os.path.splitext(file.filename or "")[1] or ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        if detector.model is None:
            import random

            tampered = round(random.uniform(0.1, 0.9), 4)
            return {
                "mock": True,
                "class_label": "tampered" if tampered >= 0.5 else "clean",
                "confidence": round(max(tampered, 1 - tampered), 4),
                "probabilities": {"clean": round(1 - tampered, 4), "tampered": tampered},
            }
        result = detector.predict(tmp_path)
        result["mock"] = False
        return result
    finally:
        os.unlink(tmp_path)
