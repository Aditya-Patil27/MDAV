# MDAV — Multimodal Government Document Verification

> AI-powered, multi-signal authentication for government-issued documents, with a tamper-evident audit trail.

[![Backend](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Frontend](https://img.shields.io/badge/Frontend-Next.js%2014-000000?logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![ML](https://img.shields.io/badge/ML-PyTorch-EE4C2C?logo=pytorch&logoColor=white)](https://pytorch.org/)
[![Database](https://img.shields.io/badge/DB-PostgreSQL-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](#license)

**Project 45 (Governance) · Group 25**
Adish S. Nair, Aditya P. Patil · Guide: Prof. Dr. Jyoti Kanjalkar

---

## Overview

MDAV verifies the authenticity of scanned or photographed government documents
(Aadhaar, PAN, passport, driving licence) by combining **four independent
signals** and fusing them into a single, explainable trust decision. Every
verification is recorded in a **SHA-256 hash-chained audit log**, so results are
tamper-evident and reproducible.

Instead of relying on a single model, MDAV cross-checks a document the way a
human reviewer would — *Does the image look edited? Do the fields make sense? Is
the digital signature valid?* — and explains **why** it reached its decision.

## How It Works

A single upload runs through a five-stage pipeline:

```
Upload ─▶ Preprocess ─▶ ┌─ OCR + Semantic validation  (field/format checks)
                        ├─ Vision tamper detection      (EfficientNet-B0)
                        └─ Digital signature check       (pyHanko / X.509)
                                      │
                                      ▼
                              Score Fusion ─▶ Decision ─▶ Hash-chained Audit Log
```

### Signals

| Signal | What it checks | Tech |
|--------|----------------|------|
| **OCR** | Extracts raw text and structured fields | PaddleOCR |
| **Semantic** | Validates Aadhaar/PAN formats, dates, required fields | Rule-based validator |
| **Vision** | Probability that the image was digitally tampered | PyTorch · EfficientNet-B0 |
| **Signature** | Detects & validates embedded digital signatures | pyHanko · cryptography |

### Decision Fusion

Signal scores are combined into a final authenticity score in `[0, 1]`
([`fusion_service.py`](backend/app/services/fusion_service.py)):

- **With** a digital signature: `0.40·visual + 0.35·semantic + 0.25·signature`
- **Without** a signature: `0.60·visual + 0.40·semantic`

The final score maps to a decision:

| Score | Decision |
|-------|----------|
| ≥ 0.80 | ✅ `APPROVED` |
| 0.50 – 0.80 | ⚠️ `FLAGGED` |
| < 0.50 | ⛔ `REVIEW_REQUIRED` |

Each result ships with a plain-language `reason_summary` explaining the outcome.

## Quick Start

### Using Docker (recommended)

```bash
docker-compose up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Interactive API docs | http://localhost:8000/docs |

### Manual setup

**Backend**
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

**Frontend**
```bash
cd frontend
npm install
npm run dev
```

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/register` | Register a new user |
| `POST` | `/api/auth/login` | Log in and obtain a JWT |
| `POST` | `/api/documents/upload` | Upload a document and run verification |
| `GET`  | `/api/documents/{id}` | Get full verification results |
| `GET`  | `/api/documents/{id}/audit` | Get the audit-trail record |
| `GET`  | `/api/dashboard/stats` | Aggregate dashboard statistics |
| `GET`  | `/api/dashboard/recent` | Recent verifications (history feed) |

Accepted uploads: `.jpg`, `.jpeg`, `.png`, `.pdf` (max 20 MB).

## Project Structure

```
MDAV/
├── frontend/                 # Next.js 14 + TypeScript + Tailwind
│   └── src/
│       ├── app/              # Pages: upload, results, history, dashboard
│       ├── components/       # React components (e.g. Navbar)
│       ├── lib/              # API client
│       └── types/            # Shared TypeScript types
├── backend/                  # FastAPI + Python
│   └── app/
│       ├── routes/           # auth, documents, dashboard endpoints
│       ├── services/         # OCR, vision, semantic, signature, fusion, audit
│       ├── models/           # SQLAlchemy models & Pydantic schemas
│       └── utils/            # JWT auth, hashing
├── ml_service/               # Standalone ML inference microservice + training
│   ├── inference.py          # FastAPI server (POST /predict) on port 8001
│   ├── model.py              # Visual tamper detector (EfficientNet-B0)
│   └── train.py              # Training pipeline
├── docs/                     # Documentation
├── MDAV_Project_Doc_Pack/    # PRD, HLD, LLD, ML design, testing, deployment
├── test_samples/             # Sample documents
└── docker-compose.yml
```

## Tech Stack

- **Frontend** — Next.js 14, TypeScript, Tailwind CSS, Recharts, Axios
- **Backend** — FastAPI, SQLAlchemy, PostgreSQL, JWT (python-jose), Pydantic v2
- **ML / CV** — PyTorch, EfficientNet-B0, PaddleOCR, OpenCV
- **Signatures** — pyHanko, cryptography (X.509)
- **Integrity** — SHA-256 hash-chained audit log

## Documentation

Full design docs live in [`MDAV_Project_Doc_Pack/`](MDAV_Project_Doc_Pack/):
PRD, High-Level Design, Low-Level Design, ML Design, Testing, and Deployment.

## Project Status

This is an academic prototype. The architecture and end-to-end pipeline are
complete and runnable, with the following caveats worth knowing:

- **Trained weights are not bundled.** The visual tamper detector needs a trained
  EfficientNet-B0 checkpoint at `VISION_MODEL_PATH` (or a running `ml_service`).
  Without weights, the vision stage returns **mock scores** so the pipeline stays
  demoable. Train your own with [`ml_service/train.py`](ml_service/train.py).
- **Vision can run two ways.** In-process inside the backend, or delegated to the
  standalone `ml_service` by setting `VISION_SERVICE_URL` (the default in
  `docker-compose.yml`). The backend falls back gracefully: remote → local → mock.
- **OCR is live** (PaddleOCR); **signature validation** requires a PDF with an
  embedded digital signature, otherwise it reports `NO_SIGNATURE`.
- **Auth is available but not enforced.** Registration/login and JWT issuance work,
  but the upload and dashboard endpoints currently run open for demo convenience.
  Enforcing auth would also require a login screen in the frontend.

## License

Released under the MIT License. See [`LICENSE`](LICENSE) for details.
