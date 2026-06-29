import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.database import Base, engine
from app.models import models  # noqa: F401 - register tables on Base before create_all
from app.routes import documents, auth, dashboard

# Create any missing tables on startup. For the dev SQLite DB this bootstraps the
# schema (there is no migration tool wired in). NOTE: create_all does not ALTER
# existing tables -- if you added columns to a model, delete the local mdav.db so
# it is recreated, or add a migration.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="MDAV API",
    description="Multimodal Government Document Verification and Automated Authentication",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])

# Serve stored artifacts (e.g. tamper heatmaps under <storage>/heatmaps) so the
# frontend can render them via /files/heatmaps/<name>.
_STORAGE = os.getenv("STORAGE_PATH", "./storage")
os.makedirs(_STORAGE, exist_ok=True)
app.mount("/files", StaticFiles(directory=_STORAGE), name="files")


@app.get("/")
async def root():
    return {"message": "MDAV API is running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
