# Value Region Localization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restrict every AI edit to the exact original value substring while preserving full-line annotation text.

**Architecture:** CORD exposes source-ground-truth label/value spans without changing the schema. A standalone OCR locator strictly resolves value text to crop-local coordinates for every dataset. Builder fails closed when localization is uncertain and threads the resolved bbox through generation, compositing, masking, and OCR verification.

**Tech Stack:** Python, Pillow, pytesseract, unittest, CodeGraph.

---

### Task 1: CORD value spans

**Files:** Modify `src/cord_loader.py`; test `tests/test_pipeline_contracts.py`.

- [x] Add a failing synthetic CORD test for `is_key` label/value separation.
- [x] Run the focused test and confirm it fails because value metadata/bbox is absent.
- [x] Preserve full line text while storing `label_text`, `value_text`, and the value-only geometry.
- [x] Run the focused test and re-query `_parse_cord_json` / `_merge_words` references.

### Task 2: Strict OCR locator

**Files:** Create `src/ocr_locator.py`; create `tests/test_ocr_locator.py`.

- [x] Add failing tests for exact token-run localization, missing text, low confidence, and unavailable pytesseract.
- [x] Run the focused tests and confirm failure because the module is absent.
- [x] Implement exception-safe, punctuation-preserving matching and bbox translation.
- [x] Run focused tests and re-query `locate_substring_bbox` references.

### Task 3: Builder integration

**Files:** Modify `src/builder.py`; test `tests/test_pipeline_contracts.py`.

- [x] Add failing builder tests for fail-closed localization and narrowed generator bbox.
- [x] Run focused tests and confirm the old full-field behavior fails them.
- [x] Mutate value-only text, reconstruct full annotation text, and thread the resolved bbox through prompt, generator, paste, mask, and OCR verification.
- [x] Run focused tests and re-query all affected call sites.

### Task 4: Final verification

**Files:** Modify `progress_report.md`.

- [x] Run the full test suite and compile check.
- [x] Confirm final call sites with CodeGraph.
- [x] Record concise completed-task entries and remaining Kaggle validation work.
