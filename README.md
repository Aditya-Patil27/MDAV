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
(Aadhaar, PAN, passport, driving licence) by combining **six independent
branches** and fusing them with **Dempster-Shafer evidence theory** into a single,
explainable trust decision. Every verification is recorded in a **SHA-256
hash-chained audit log**, so results are tamper-evident and reproducible.

Instead of relying on a single model, MDAV cross-checks a document the way a
human reviewer would — *Does the image look edited? Is any region AI-generated?
Do the fields make sense? Is the QR's signed data consistent with the print? Is
the digital signature valid?* — and explains **why** it reached its decision.

## How It Works

A single upload fans out across independent branches, each emitting a
Dempster-Shafer **belief mass** over `{AUTHENTIC, FORGED}`:

```
Upload ─▶ Layout (YOLO) ─▶ field crops ─▶ OCR ─▶ ┌─ Semantic checksums (Aadhaar/PAN/dates)
                                                  ├─ Aadhaar Secure-QR cross-check
                          Visual tamper (DocTamper U-Net) ─┤
                          AI/diffusion forgery (AIForge) ──┤
                          Digital signature (pyHanko/X.509)─┘
                                      │
                          Dempster-Shafer fusion  (per-source reliability discount)
                                      ▼
                              Decision ─▶ Hash-chained Audit Log
                                      │
                          Reviewer feedback ─▶ online reliability calibration
```

### Branches

| Branch | What it checks | Tech |
|--------|----------------|------|
| **Layout** | Localizes Aadhaar fields; crops feed OCR | YOLOv8n (Ultralytics) |
| **OCR + Semantic** | Extracts fields; validates Aadhaar (Verhoeff)/PAN/dates | PaddleOCR + rule validator |
| **Visual** | Per-pixel *classical* tamper localization (copy-move/splice) | DCT+RGB ResNet18 U-Net (DocTamper) |
| **AIForge** | AI-generated / diffusion-inpainted content *(branch slot — model WIP)* | PyTorch *(see [`docs/AIForge_Agent_Brief.md`](docs/AIForge_Agent_Brief.md))* |
| **Secure QR** | Decodes the signed Aadhaar QR, cross-checks vs printed fields | UIDAI Secure QR v2 + RSA |
| **Signature** | Detects & validates embedded digital signatures | pyHanko · cryptography |

### Decision Fusion (Dempster-Shafer)

Each branch emits a belief mass; fusion discounts it by a per-source
**reliability** and combines everything with Dempster's rule
([`fusion_service.py`](backend/app/services/fusion_service.py),
[`belief.py`](backend/app/services/belief.py)). Discounting (not additive
weighting) means an unreliable branch decays toward *"don't know"* rather than
voting 0.5 — so one conclusive forensic signal (broken signature, QR/print
mismatch) overrides a pile of soft heuristics.

The fused belief's **pignistic** probability maps to a decision:

| P(authentic) | Decision |
|-------|----------|
| ≥ 0.80 | ✅ `APPROVED` |
| 0.50 – 0.80 | ⚠️ `FLAGGED` |
| < 0.50 | ⛔ `REVIEW_REQUIRED` |

Each result ships with a plain-language `reason_summary` and the per-branch
belief masses + inter-branch conflict.

### Online reliability calibration

Source reliabilities are not fixed. Reviewer-confirmed labels (`POST
/api/documents/{id}/feedback`) feed an offline calibrator
([`reliability_calibrator.py`](backend/app/services/reliability_calibrator.py))
that re-estimates each branch's reliability under an **asymmetric cost** (a
false-accept of a forgery is far costlier than a false-reject) and proposes new
values behind a **champion/challenger** gate. Run it with
`python -m scripts.calibrate_reliability` (`--promote` to apply). The DS fusion
and audit chain stay fully explainable — only the interpretable reliability
parameters are learned.

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
| `GET`  | `/api/documents/{id}` | Get full verification results (per-branch beliefs) |
| `POST` | `/api/documents/{id}/feedback` | Submit a reviewer's ground-truth label (calibration) |
| `GET`  | `/api/documents/{id}/audit` | Get the audit-trail record |
| `GET`  | `/api/history` | List past verifications |
| `GET`  | `/api/dashboard/stats` | Aggregate dashboard statistics |
| `GET`  | `/api/dashboard/recent` | Recent verifications |

Accepted uploads: `.jpg`, `.jpeg`, `.png`, `.pdf` (max 20 MB).

## Project Structure

```
MDAV/
├── frontend/                 # Next.js 14 + TypeScript + Tailwind
│   └── src/
│       ├── app/              # Pages: upload, results, history, dashboard
│       ├── components/       # BranchScoreBars, BranchEvidence, ScoreRing, ...
│       ├── lib/              # API client
│       └── types/            # Shared TypeScript types
├── backend/                  # FastAPI + Python
│   ├── app/
│   │   ├── routes/           # auth, documents (+ feedback), dashboard
│   │   ├── services/         # belief, fusion, vision, layout, aadhaar_qr,
│   │   │                     #   diffusion, semantic, signature, ocr, audit,
│   │   │                     #   reliability_calibrator
│   │   ├── models/           # SQLAlchemy models & Pydantic schemas
│   │   └── utils/            # JWT auth, hashing
│   ├── scripts/              # calibrate_reliability.py (champion/challenger)
│   └── tests/                # belief, fusion, qr, calibrator (pytest)
├── ml_service/               # Standalone visual-model inference microservice
├── models/                   # Trained weights (git-ignored) — see models/README.md
├── notebooks/                # Training notebooks (Kaggle/Colab)
├── docs/                     # Docs incl. AIForge_Agent_Brief.md
├── MDAV_Project_Doc_Pack/    # PRD, HLD, LLD, ML design, testing, deployment
├── test_samples/             # Sample documents
└── docker-compose.yml
```

## Tech Stack

- **Frontend** — Next.js 14, TypeScript, Tailwind CSS, Recharts, Axios
- **Backend** — FastAPI, SQLAlchemy, PostgreSQL/SQLite, JWT (python-jose), Pydantic v2
- **ML / CV** — PyTorch, segmentation-models-pytorch (DocTamper U-Net), Ultralytics YOLOv8, jpegio (DCT), PaddleOCR, OpenCV
- **Fusion** — Dempster-Shafer evidence theory + online reliability calibration
- **Signatures** — pyHanko, cryptography (X.509); Aadhaar Secure-QR (RSA)
- **Integrity** — SHA-256 hash-chained audit log

## Documentation

Full design docs live in [`MDAV_Project_Doc_Pack/`](MDAV_Project_Doc_Pack/):
PRD, High-Level Design, Low-Level Design, ML Design, Testing, and Deployment.

## License

Released under the MIT License. See [`LICENSE`](LICENSE) for details.
