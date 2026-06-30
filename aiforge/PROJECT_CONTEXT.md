# Project Context: AIForge Document Forgery Dataset Generator

## Repository Structure
```
datasets/
    CORD/
    FUNSD/
    SROIE/
    XFUND/
src/
    schema.py
    utils.py
    cord_loader.py
    funsd_loader.py
    sroie_loader.py
    xfund_loader.py
    dataset_loader.py
    field_selector.py
    value_mutator.py
    crop_generator.py
    prompt_builder.py
    puter_generator.py
    crop_paste.py
    mask_generator.py
    annotation_writer.py
    metadata_writer.py
    validator.py
    statistics.py
    visualization.py
    builder.py
main.py
```

## Completed Modules
- **`src/schema.py`**: Unified annotation schemas (`UnifiedDocument`, `UnifiedField`).
- **`src/utils.py`**: RNG seeding, upsampling/downsampling, path helpers, logging.
- **`src/cord_loader.py`**: Loader converting CORD dataset into UnifiedDocument format.
- **`src/funsd_loader.py`**: Loader converting FUNSD dataset into UnifiedDocument format.
- **`src/sroie_loader.py`**: Loader converting SROIE dataset into UnifiedDocument format. Gracefully handles encoding errors.
- **`src/xfund_loader.py`**: Loader converting XFUND dataset into UnifiedDocument format.
- **`src/dataset_loader.py`**: Orchestrator that aggregates all loaders.
- **`src/field_selector.py`**: Prioritizes fields based on value type (Totals -> Prices -> Taxes -> etc.).
- **`src/value_mutator.py`**: Mutates date, money, quantities, IDs semantically.
- **`src/crop_generator.py`**: Standard 50% / min 150px crop calculator.
- **`src/prompt_builder.py`**: Builds Gemini prompts referencing the green rectangle helper.
- **`src/puter_generator.py`**: Connects via Playwright browser context to execute Puter.js inpaint calls.
- **`src/crop_paste.py`**: Pastes only the mutated text area back to original.
- **`src/mask_generator.py`**: Creates the black/white binary L-mode tamper mask.
- **`src/annotation_writer.py`**: Serializes forged UnifiedDocuments to JSON.
- **`src/metadata_writer.py`**: Append-only log of forged datasets to metadata.csv.
- **`src/validator.py`**: End-of-turn integrity and dimensions validator.
- **`src/statistics.py`**: Outputs dataset distributions to statistics.json.
- **`src/visualization.py`**: Grid, closeup, overlay, and chart generator.
- **`src/builder.py`**: Forgery flow pipeline manager.
- **`main.py`**: CLI command parser and execution loop.

## Pending Modules
- None.

## Assumptions
- Playwright Chromium runs locally with user profile directory `~/.gemini/antigravity-ide/browser_context` to retain login credentials.

## Discovered Dataset Structures
- SROIE text files occasionally contain CP1252 characters like the £ symbol, handled using `errors="replace"`.
- XFUND contains occasional missing images, handled gracefully.

## Next Task
- Complete the Puter authentication step in the opened browser window.

## Recent Progress
- The per-sample pipeline now continues after document-level failures instead of halting the full batch.
- Resume support skips already-generated samples when `metadata.csv` already contains a valid forged record.
- Final statistics are rebuilt from the completed dataset metadata, so counts survive interrupted runs.
- Binary mask semantics were aligned to exclusive bbox edges, and duplicate metadata rows are now skipped.
- Optional OCR verification for the edited region is now wired into the retry loop; failed OCR checks trigger retries and exhausted samples are rejected.
- The CLI now warms the persistent Playwright browser session before dataset loading, and the Puter bridge requests a temporary session instead of pushing Google/email signup flows.
- Puter startup auth is now non-blocking: the bridge opens with the persistent profile, does not force a sign-in click at startup, and leaves the manual temporary-session button available only as a fallback.

## 2026-06-29 ComfyUI Migration Update
- Puter.js, Playwright, browser login, and browser persistence were removed from the active generation path.
- Added a backend-agnostic `ImageGenerator` interface in `src/generator_base.py` and a local ComfyUI backend in `src/comfy_generator.py`.
- The pipeline now defaults to a ComfyUI FLUX Fill workflow loaded from `workflows/flux_fill.json` instead of browser automation.
- Added `src/progress_tracker.py` so interrupted runs persist completed ids, failed ids, retry counts, and timestamps to `progress.json`.
- Added Colab-oriented scripts: `setup_colab.py` installs dependencies, clones ComfyUI/custom nodes, and checks model assets; `run_colab.py` launches ComfyUI headlessly.
- Added `requirements.txt` for Python dependencies only and updated path helpers to honor `BASE_DIR` and `OUTPUT_DIR`.
- Obsolete file removed: `src/puter_generator.py`.
- Remaining work: validate the ComfyUI workflow against a live FLUX Fill install in Colab, confirm model downloads/patching on first-run environments, and then clean up any final doc references to the old browser backend.
