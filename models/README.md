# models/

Trained model weights live here. Weights are git-ignored (`*.pth`, `*.pt`);
they are handed over out of band, never committed.

| File | Branch | Produced by | Contract |
|------|--------|-------------|----------|
| `best.pth` | Visual tamper localization (DocTamper) | [`notebooks/train_visual_doctamper.ipynb`](../notebooks/train_visual_doctamper.ipynb) | DCT+RGB ResNet18 U-Net, 2-class mask. Loaded by `backend/app/services/vision_service.py`. |
| `best_diffusion.pth` | AI/diffusion forgery localization (AIForge) | [`notebooks/train_aiforge_diffusion.ipynb`](../notebooks/train_aiforge_diffusion.ipynb) | DCT+RGB ResNet18 U-Net, 2-class AI-edit mask. See [`MODEL_CONTRACT_AIFORGE.md`](MODEL_CONTRACT_AIFORGE.md). |
| `diffusion/` | Optional AI-image classifier fallback | Supplied separately | Complete local Transformers model folder. Used only when `MDAV_DIFFUSION_MODEL` is explicitly configured and the AIForge checkpoint is unavailable. |
| `best_layout_detector.pt` | Aadhaar field layout (YOLOv8n) | [`notebooks/train_layout_yolo.ipynb`](../notebooks/train_layout_yolo.ipynb) | Ultralytics YOLOv8n, 640px, 5 classes. Loaded by `backend/app/services/layout_service.py`. |

## How services find these

- Docker mounts this directory to `/app/models` through `docker-compose.yml`.
- Local runs use the paths in `backend/.env` or `backend/.env.example`:

```text
MDAV_VISION_WEIGHTS=../models/best.pth
MDAV_LAYOUT_WEIGHTS=../models/best_layout_detector.pt
MDAV_DIFFUSION_WEIGHTS=../models/best_diffusion.pth
MDAV_DIFFUSION_THRESHOLD=0.95
MDAV_DIFFUSION_MIN_COMPONENT_PIXELS=16
MDAV_VISUAL_PIXEL_THRESHOLD=0.80
MDAV_VISUAL_MIN_COMPONENT_PIXELS=16
MDAV_IDENTITY_FORENSICS_CONFIDENCE_CAP=0.25
# Optional: MDAV_DIFFUSION_MODEL=../models/diffusion
```

If a weight file is absent, its branch degrades gracefully to a vacuous
Dempster-Shafer belief so the pipeline can still run.

The local segmentation checkpoint is preferred. An explicitly configured
`MDAV_DIFFUSION_MODEL` can provide a Hugging Face classifier fallback; see
[`diffusion/README.md`](diffusion/README.md). No classifier is downloaded by
default.

The visual and AIForge checkpoint outputs are pixel-localization evidence, not
independent whole-document classifiers. Both services require an above-threshold
connected component before committing forged belief, and their evidence is
correlation-adjusted before global fusion. The identity-document confidence cap
is a conservative cold-start control; replace it only after evaluating genuine
and tampered Aadhaar/PAN samples at document level.
