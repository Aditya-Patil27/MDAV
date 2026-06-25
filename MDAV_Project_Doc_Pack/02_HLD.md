# High-Level Design (HLD)
## MDAV: Multimodal Government Document Verification and Automated Authentication

---

### 1. System Overview

MDAV is a modular document verification platform with four major evidence sources:
1. **Visual Forensics** — AI-based tamper detection and localization
2. **OCR & Semantic Validation** — Text extraction + field-level rule checks
3. **Digital Signature Verification** — PKCS#7/CMS validation for signed documents
4. **Blockchain Audit Layer** — Immutable verification records and document hashes

### 2. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      User Dashboard                         │
│              (Next.js + TypeScript + Tailwind)              │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI Backend                            │
│              (Auth, File Ingestion, Orchestration)           │
└──────────────────────────┬──────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────────┐
│  Visual Forensic │ │  OCR/Semantic│ │  Signature       │
│  Branch          │ │  Branch      │ │  Branch          │
│  (Swin-T/ResNet) │ │  (PaddleOCR) │ │  (pyHanko)       │
└──────────────────┘ └──────────────┘ └──────────────────┘
              │            │            │
              └────────────┼────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Confidence Fusion                         │
│            (Weighted Scoring + Explainability)               │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Blockchain Audit Layer                         │
│         (Hash-chain + Timestamp + Verification Log)         │
└─────────────────────────────────────────────────────────────┘
```

### 3. Data Flow

1. User uploads document (image/PDF) via frontend
2. Backend validates file type and size, creates verification job
3. Preprocessing: deskew, normalize, resize, denoise
4. Document-type classification determines routing
5. Branch execution runs in parallel:
   - Visual branch: CNN classifier scores tamper probability
   - OCR branch: Text extraction + semantic rule validation
   - Signature branch: PKCS#7/CMS validation (if signed PDF)
6. Fusion engine combines branch scores into final authenticity score
7. Results stored in PostgreSQL + blockchain audit log
8. Dashboard displays verification result, confidence score, anomalies, audit trail

### 4. Modules

| Module | Responsibility | Technology |
|--------|---------------|------------|
| Frontend | Upload, results, history, audit trail | Next.js, TypeScript, Tailwind, shadcn/ui |
| API Backend | Auth, file ingestion, job orchestration | FastAPI, Python |
| Preprocessing | Deskew, normalize, resize, denoise | OpenCV, Pillow |
| OCR Module | Text extraction and field normalization | PaddleOCR / EasyOCR |
| Semantic Validation | Aadhaar/PAN/date rules, cross-field checks | Python regex, Verhoeff algorithm |
| Visual Analysis | Tamper detection and localization | Swin Transformer / ResNet18 |
| Signature Verification | PKCS#7/CMS validation, cert chain | pyHanko, OpenSSL |
| Fusion Engine | Weighted scoring and explainability | Python, NumPy |
| Storage Layer | Document and result persistence | PostgreSQL, Supabase Storage |
| Audit Layer | Immutable event log and verification history | Hash-chain (simple blockchain) |

### 5. Technology Choices

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Frontend | Next.js + TypeScript | Modern React, SSR, type safety |
| UI Library | shadcn/ui + Tailwind | Clean, enterprise-grade components |
| Charts | Recharts | Lightweight, React-native charts |
| Backend | FastAPI | Async Python, fast, auto-docs |
| DB | PostgreSQL | Reliable, relational, easy to host |
| Storage | Supabase Storage / local | Simple object storage |
| OCR | PaddleOCR | Best open-source OCR for documents |
| Vision Model | EfficientNet-B0 / ResNet18 | CPU-friendly, lightweight CNN |
| Signature | pyHanko | Python PKCS#7/CMS implementation |
| Auth | JWT + simple email/password | Demo-friendly |

### 6. Design Principles

- **Modular over monolithic** — Each branch is independent and demoable
- **Explainable over opaque** — Human-readable reasons for every decision
- **CPU-friendly over compute-heavy** — No GPU required for inference
- **Demo-ready over research-heavy** — Working system over perfect accuracy

### 7. Non-Functional Requirements

- Fast uploads and predictable inference time (< 5s per document)
- Clear error handling with user-friendly messages
- Simple security controls (auth, file validation, rate limiting)
- Maintainable code structure with clear separation of concerns
- Blockchain audit trail is immutable and queryable

### 8. Deployment Targets

| Component | Target |
|-----------|--------|
| Frontend | Vercel / Netlify |
| Backend | Render / Railway / local Docker |
| DB | PostgreSQL / Supabase |
| ML Model | Packaged as Python service or FastAPI route |
