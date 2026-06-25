# MDAV: Multimodal Government Document Verification and Automated Authentication

**Project 45 (Governance) | Group 25**

| Field | Details |
|-------|---------|
| Project Title | MDAV: Multimodal Government Document Verification and Automated Authentication |
| Domain / Track | Governance |
| Guide Name | Prof. Dr. Jyoti Kanjalkar |
| Group Number | 25 |
| Group Members | Adish S. Nair, Aditya P. Patil |
| Date | 22 June 2026 |

## Overview

MDAV is a modular, multimodal verification platform that combines:
1. **Visual Forensics** — AI-based tamper detection and localization
2. **OCR & Semantic Validation** — Text extraction + field-level rule checks (Aadhaar, PAN, dates)
3. **Digital Signature Verification** — PKCS#7/CMS validation for signed documents
4. **Blockchain Audit Layer** — Immutable verification records and document hashes

## Architecture

```
Upload → Preprocess → Branch Execution → Score Fusion → Store Results → Dashboard
                           ↓
              ┌────────────┼────────────┐
              ↓            ↓            ↓
         Visual AI    OCR/Semantic   Signature
         (Swin-T/     (PaddleOCR +   (pyHanko +
          ResNet)      Rules)        OpenSSL)
              ↓            ↓            ↓
              └────────────┼────────────┘
                           ↓
                   Confidence Fusion
                           ↓
                   Blockchain Audit
```

## Files in This Pack

| File | Purpose |
|------|---------|
| `01_PRD.md` | Product Requirements Document |
| `02_HLD.md` | High-Level Design |
| `03_LLD.md` | Low-Level Design |
| `04_ML_Design.md` | ML/Model Design and Dataset Plan |
| `05_Testing.md` | Testing Plan |
| `06_Deployment.md` | Deployment Plan |
| `07_Frontend_References.md` | UI/UX Reference Links |

## Recommended Use

1. Share `01_PRD.md` with product and guide review.
2. Share `02_HLD.md` and `03_LLD.md` with the development team.
3. Use `04_ML_Design.md` to keep ML scope realistic in a 2-week build.
4. Use `05_Testing.md` and `06_Deployment.md` for implementation and demo readiness.

## Tech Stack

- **Frontend**: Next.js, TypeScript, Tailwind CSS, shadcn/ui, Recharts
- **Backend**: FastAPI, Python
- **OCR**: PaddleOCR / EasyOCR
- **Vision**: Swin Transformer / ResNet18 (lightweight CNN)
- **Signature**: pyHanko, OpenSSL
- **DB**: PostgreSQL
- **Storage**: Supabase Storage / local
- **Blockchain**: Simple hash-chain audit log
