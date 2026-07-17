# MDAV Project Context

## Canonical Repository

This repository is the consolidated MDAV product codebase. The former standalone AIForge development workspace was removed on 2026-07-01, and the cloned Git repository was promoted to this root. There must not be a nested `MDAV/` repository.

## Product Structure

```text
MDAV/
  frontend/                  Next.js reviewer interface
  backend/                   FastAPI API, evidence branches, and fusion logic
  ml_service/                Training and inference utilities
  models/                    Model documentation/placeholders; weights are external
  notebooks/                 Named Kaggle/training notebooks
  test_samples/              Ignored/local verification inputs
  docs/                      Product and AIForge documentation
  MDAV_Project_Doc_Pack/     PRD, architecture, ML, test, and deployment references
  aiforge/                   AI-generated document forgery dataset generator
```

Datasets, generated outputs, model weights, progress files, metadata CSVs, caches, secrets, and local environment files are intentionally excluded from Git.

## AIForge Generator

`aiforge/` contains the validated working Kaggle implementation supplied in `aiforge.zip` and installed on 2026-07-01. Its active path is:

```text
authentic document -> unified loader -> field selection -> semantic mutation
-> value-region localization -> pad to multiple of 64 -> FLUX.1-Fill-dev
-> unpad -> feathered paste -> expanded binary mask -> OCR policy
-> annotation/metadata/progress -> statistics/visualizations
```

Key implementation decisions:

- Diffusers `FluxFillPipeline` with pre-quantized NF4 transformer and T5 components.
- CPU model offload is enabled by default to fit a 16 GB T4.
- CORD uses `is_key` ground truth to separate label and value geometry and is marked as Korean (`ko`).
- Tesseract uses PSM 7 plus a numeric PSM 8 whitelist pass; PaddleOCR was removed from this generator because its Kaggle dependency/runtime path was unstable.
- `MDAV_OCR_VERIFY` supports `strict`, `changed`, and `off`; `strict` requires the requested value, while `changed` accepts a region when the original value is gone.
- The tamper mask expands by the same margin used by FLUX and feathered compositing so every modified pixel is labeled.
- Rejected generations can be inspected under `_failed/` using region, placement, and JSON diagnostic artifacts.
- Two deterministic variants per source document and resumable, deterministic sharding are supported.

## Kaggle Runtime Findings

- The four loaders produced 7,126 work items at two variants per document.
- A real T4 pilot at 20 steps averaged about 158 seconds per accepted sample after model loading, projecting roughly 313 GPU-hours on one T4.
- The current pipeline uses one CUDA device per process. Two CPU-offloaded FLUX processes in one T4x2 notebook exceeded Kaggle's approximately 31 GB host RAM and restarted the notebook.
- Use one process per notebook, or separate Kaggle notebooks/accounts for concurrent shards. Re-running the same output directory resumes from `progress.json` and `metadata.csv`.
- Ten inference steps may approximately halve diffusion time but requires a quality pilot before a full run.

## Methodological Caveat

`MDAV_OCR_VERIFY=changed` improves throughput but may accept rendered text that differs from the requested mutated annotation. It is suitable only when the benchmark target is visual AI tampering rather than exact semantic replacement. Final benchmark reports must state the OCR mode, inference steps, model IDs, seed, and acceptance policy.

## External Requirements

- Accept the gated `black-forest-labs/FLUX.1-Fill-dev` license.
- Provide `HF_TOKEN` through Kaggle secrets or environment variables.
- Attach the CORD, FUNSD, SROIE, and XFUND datasets externally; do not commit them.
- Preserve shard outputs before Kaggle sessions expire.

## AIForge Detector Integration (2026-07-08)

- `models/best_diffusion.pth` is the preferred backend for the `diffusion`
  evidence branch.
- The checkpoint is an MDAVNet DCT+RGB ResNet18 U-Net with 21 DCT bins, a
  16-channel DCT embedding, JPEG quality 95 preprocessing, two output classes,
  and a checkpoint-selected pixel threshold of 0.95.
- `backend/app/services/diffusion_service.py` reads architecture and threshold
  metadata before constructing the network and falls back to notebook constants
  only when metadata is absent.
- Missing weights, native `jpegio`, or other optional ML dependencies produce
  vacuous `diffusion` belief instead of stopping document verification.
- An explicitly configured `MDAV_DIFFUSION_MODEL` remains an optional Hugging
  Face classifier fallback; no model is downloaded by default.
- The complete handoff is documented in `models/MODEL_CONTRACT_AIFORGE.md`.
