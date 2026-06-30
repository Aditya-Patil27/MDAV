# AIForge Branch — Agent Brief

**Mission:** build the **AI/diffusion-forgery detector** ("AIForge") and deliver it
so it drops into MDAV's existing `diffusion_service` slot with zero changes to the
fusion layer, API, or frontend.

This document is written to be **handed directly to an AI coding agent**. The
ready-to-paste prompt is at the bottom; the sections above are the spec it needs.

---

## 1. Context (what MDAV is and where you fit)

MDAV verifies government IDs by running several independent **branches**, each of
which emits a Dempster-Shafer **belief mass** over `{AUTHENTIC, FORGED}`. A fusion
layer discounts each branch by a learned *reliability* and combines them.

Existing branches: visual tamper localization (DocTamper U-Net), Aadhaar layout
(YOLO), OCR+semantic checksums, digital signature (X.509), Aadhaar Secure QR.

**Your branch is new and complementary.** The visual branch catches *classical*
tampering (copy-move, splicing, recompression). **AIForge detects AI-generated /
diffusion- or GAN-inpainted content** — regions synthesized by a generative model
rather than cut-and-pasted. Different artifact, different detector.

The slot already exists and currently returns a "vacuous" (no-evidence) belief:
[`backend/app/services/diffusion_service.py`](../backend/app/services/diffusion_service.py).
Your job is to (a) train the model and (b) implement two methods in that file.

**Dataset generator is already built** — it lives in [`aiforge/`](../aiforge/) (the
"AIForge Document Forgery Dataset Generator"). It loads document datasets (CORD,
FUNSD, SROIE, XFUND), mutates field values, and **inpaints the edited region with
FLUX.1-Fill-dev** (NF4-quantized, diffusion), producing **paired (forged image,
binary tamper mask)** samples — mask values `0` = authentic, `255` = tampered,
exact image size (`aiforge/src/mask_generator.py`). Run it on Kaggle to produce
the training set. **Because the labels are per-pixel masks, the detector should
be a segmentation model** (see §4).

---

## 2. The integration contract (do not deviate)

The fusion layer consumes a single scalar from your branch. Implement
`diffusion_service` so that for an input image it produces:

```
ai_forgery_prob : float in [0, 1]   # P(document contains AI-generated content)
confidence      : float in [0, 1]   # how sure the model is (drives committed mass)
```

These map to belief **exactly like the visual branch** (already coded for you):

```python
from app.services.belief import from_probability
mass = from_probability(1.0 - ai_forgery_prob, confidence=confidence, source="diffusion")
```

You implement only these two methods in `diffusion_service.py`:

```python
def _try_load(self) -> None:
    # set self.model from os.path.exists(self.model_path); lazy-import torch.
    # on any failure: self.model = None, self._load_failed_reason = "<why>"

def _predict(self, image_path: str) -> tuple[float, float]:
    # return (ai_forgery_prob, confidence). Reproduce training preprocessing EXACTLY.
```

Everything downstream (`analyze`, belief mapping, fusion, DB persistence under
`FusedResult.branches`, API response, the frontend "AI/Diffusion Forgery" card,
and the reliability calibrator) **already handles your branch** once `_predict`
returns real numbers. Do not touch them.

### Hard requirements
- **Lazy imports.** `import torch` (and friends) *inside* the methods, never at
  module top — the backend must still import on a machine without torch.
- **Graceful failure.** Missing weights / missing deps → `self.model = None`; the
  branch stays vacuous, the pipeline keeps running. Never raise at import.
- **Weights path:** read from env `MDAV_DIFFUSION_WEIGHTS` (already wired; default
  `/app/models/best_diffusion.pth`). Ship the trained file to `models/`.
- **State-dict checkpoint**, loadable with `torch.load(..., weights_only=False)`;
  if you save a full training checkpoint, put the weights under a `"model"` key
  (mirrors `best.pth`).

---

## 3. The deliverable — model contract (THIS IS THE PART THAT BITES)

The visual model was once handed over as a bare `.pth` with no spec, and it cost
real time to reverse-engineer the architecture and preprocessing from tensor
shapes. **Do not repeat that.** Along with the weights, deliver a one-page
`MODEL_CONTRACT.md` stating:

1. **Architecture** — exact class definition (backbone, classifier/seg head,
   input channels). Ship the `nn.Module` code, not a description.
2. **Input** — H×W, RGB vs BGR vs grayscale, resize/crop policy, and the exact
   normalization (mean/std or scale).
3. **Any auxiliary stream** — if you use frequency/DCT/noise-print features (common
   for AI-gen detection), specify how they're computed bit-for-bit.
4. **Output** — logits vs sigmoid/softmax, shape, and which index/channel is the
   "AI-generated" class. If it's a localization mask, also give the
   aggregation → scalar (e.g. high-percentile of the positive map).
5. **Versions** — torch / torchvision (and any extra lib) versions used to train.
6. A 10-line `predict(image_path)` reference snippet that reproduces inference.

If the contract is clear, wiring `_predict` is ~20 lines.

---

## 4. Dataset & modeling guidance

- **Primary data (recommended, de-risked):** self-generated **Stable-Diffusion
  inpainting** over clean ID templates — inpaint photo/name/number regions, keep
  paired clean originals. This guarantees reconstructable labels and avoids
  depending on an external "AIForge" corpus that may be hard to source.
- **Cross-dataset robustness:** add a public AI-generated-image set and a few
  GAN-inpainted samples so the detector isn't SD-specific.
- **Negatives:** clean scans + *classically* tampered docs (so AIForge learns to
  fire on generative artifacts specifically, not on any edit — the visual branch
  already owns classical tampering).
- **Output choice — segmentation (primary).** The `aiforge/` generator emits
  per-pixel tamper masks, so train a **segmentation model** that outputs an
  AI-forgery mask (same shape as the DocTamper visual branch: 2-channel logits or
  1-channel sigmoid at image resolution). In `_predict`, aggregate the mask to a
  scalar exactly like `vision_service._aggregate` (e.g. high-percentile of the
  positive map + area ratio) → that scalar is `ai_forgery_prob`. A whole-image
  classifier is an acceptable fallback but throws away the mask supervision you
  already have.
- **Privacy:** no real ID PII. Use synthetic/template IDs only.

---

## 5. Acceptance checklist

- [ ] `MODEL_CONTRACT.md` + `nn.Module` code delivered with the weights.
- [ ] `best_diffusion.pth` placed in `models/`; loads via `weights_only=False`.
- [ ] `diffusion_service._try_load` + `_predict` implemented; lazy imports; mock-safe.
- [ ] `_predict` returns calibrated `ai_forgery_prob, confidence` in `[0,1]`.
- [ ] On a clean doc → low prob; on an SD-inpainted doc → high prob (sanity demo).
- [ ] Backend still imports and `pytest backend/tests -q` stays green.
- [ ] No changes to `fusion_service.py`, `documents.py`, schemas, or the frontend.

---

## 6. Ready-to-paste prompt (give this to your agent)

> You are extending an existing repo (MDAV). Build the **AIForge** AI/diffusion-
> forgery detection branch. Read `docs/AIForge_Agent_Brief.md` and
> `backend/app/services/diffusion_service.py` and `vision_service.py` first.
>
> Deliver:
> 1. A training notebook/script (Kaggle) that trains a **segmentation** detector
>    for AI-generated/inpainted regions in ID documents. The dataset generator
>    already exists in `aiforge/` — it produces paired (forged image, binary
>    tamper mask) samples via FLUX.1-Fill inpainting; run it on Kaggle to build
>    the set. Train on those masks (per-pixel AI-forgery target). **No real ID
>    PII.** Save a `.pth` (state-dict, or full checkpoint with weights under
>    `"model"`).
> 2. A one-page `MODEL_CONTRACT.md`: exact `nn.Module` code, input size + RGB/BGR
>    + normalization, any frequency/DCT/noise stream, output (sigmoid/softmax,
>    shape, AI-gen index), torch version, and a 10-line `predict()` snippet.
> 3. Implement `DiffusionService._try_load` and `_predict(image_path)` in
>    `backend/app/services/diffusion_service.py` so `_predict` returns
>    `(ai_forgery_prob, confidence)` in `[0,1]`, reproducing the training
>    preprocessing exactly.
>
> Hard constraints: import torch lazily *inside* methods; if weights/deps are
> missing set `self.model = None` and never raise at import; read weights from env
> `MDAV_DIFFUSION_WEIGHTS`. Do NOT modify `fusion_service.py`, `documents.py`,
> schemas, or the frontend — the branch already plugs into Dempster-Shafer fusion
> via `from_probability(1 - ai_forgery_prob, confidence)`. Keep
> `cd backend && python -m pytest tests -q` green.
