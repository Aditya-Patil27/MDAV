# MDAV Progress Context

## Completed

- 2026-07-08: Integrated the trained `models/best_diffusion.pth` AIForge
  segmentation checkpoint into the backend with metadata-driven architecture,
  threshold-aware localized aggregation, lazy dependencies, fail-soft evidence,
  and an optional explicit Hugging Face classifier fallback.
- 2026-07-08: Added the AIForge model contract, local check CLI, environment
  settings, checkpoint tests, and generated-artifact cleanup rules.
- 2026-07-01: Added a Kaggle-ready `notebooks/train_aiforge_diffusion.ipynb` for training `models/best_diffusion.pth` on `AIForge_MDAV` using the same DCT+RGB ResNet18 U-Net contract consumed by `backend/app/services/diffusion_service.py`.
- 2026-07-01: Promoted the cloned MDAV Git repository to the workspace root and removed the superseded standalone workspace structure.
- 2026-07-01: Replaced `aiforge/` with the validated working archive and deleted the source ZIP.
- 2026-07-01: Preserved the frontend, backend, ML service, model placeholders, named notebooks, documentation pack, Git history, and local ignored `.env`.
- 2026-07-01: Removed generated output, local dataset copies, caches, obsolete workflows, the nested clone, the unnamed Kaggle scratch notebook, and generated TypeScript build metadata.
- AIForge uses NF4 FLUX.1-Fill-dev, deterministic variants/shards, resume tracking, CORD value geometry, Tesseract OCR policies, aligned feather/mask margins, and saved failure artifacts.

## Verified Runtime Evidence

- Working archive test baseline: 47 Python tests passed before consolidation.
- Kaggle T4 pilot: 20 FLUX steps took approximately 102-162 seconds of diffusion per sample; accepted end-to-end samples averaged approximately 158 seconds after model load.
- Full workload: 7,126 variants at two variants per source document.
- Two simultaneous CPU-offloaded FLUX processes exceeded a T4x2 notebook's host RAM; use one process per notebook or separate notebooks for shards.

## Remaining Work

- Run real end-to-end AIForge image inference in Linux/Docker or Kaggle, where
  `jpegio` is supported; its native build fails under the current Windows toolchain.
- Evaluate the receipt/form-trained AIForge checkpoint separately on government
  IDs before treating its validation metrics as cross-domain performance.
- Manually audit a representative pilot across all four datasets before large-scale generation.
- Decide and document whether final runs use `MDAV_OCR_VERIFY=strict` or `changed`.
- Benchmark 10 versus 20 FLUX steps for quality and throughput.
- Persist shard outputs outside ephemeral Kaggle sessions and merge metadata before final statistics.

## Consolidation Verification

- AIForge: all 47 unit tests passed after replacement.
- Python: `compileall` passed for `aiforge/`, `backend/`, and `ml_service/`.
- Backend: all 35 pytest tests passed.
- Frontend: `npm ci` completed and the Next.js production build compiled, linted, type-checked, and generated all eight static pages successfully.
- CodeGraph was rebuilt over the consolidated product repository: 91 files, 1,052 nodes, and 1,836 edges.

## Canonical References

- Product architecture: `README.md` and `MDAV_Project_Doc_Pack/`
- Generator implementation: `aiforge/`
- Generator historical state: `aiforge/PROJECT_CONTEXT.md`
- Generator migration ledger: `aiforge/progress_report.md`
- Current consolidated state: `project_context.md` and this file
