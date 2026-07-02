# models/

Trained model weights live here. **Weights are git-ignored** (`*.pth`, `*.pt`) —
they are handed over out-of-band, never committed.

| File | Branch | Produced by | Contract |
|------|--------|-------------|----------|
| `best.pth` | Visual tamper localization (DocTamper) | [`notebooks/train_visual_doctamper.ipynb`](../notebooks/train_visual_doctamper.ipynb) | DCT+RGB ResNet18 U-Net, 2-class mask. Loaded by `backend/app/services/vision_service.py`. |
| `best_layout_detector.pt` | Aadhaar field layout (YOLOv8n) | [`notebooks/train_layout_yolo.ipynb`](../notebooks/train_layout_yolo.ipynb) | Ultralytics YOLOv8n, 640px, 5 classes. Loaded by `backend/app/services/layout_service.py`. |
| `diffusion/` (folder) | AI/diffusion forgery | Pretrained HF image-classifier — drop the 3 files in, see [`diffusion/README.md`](diffusion/README.md) | HF `AutoModelForImageClassification` (real-vs-AI). Loaded by `backend/app/services/diffusion_service.py` via `MDAV_DIFFUSION_MODEL`. Swap in an AIForge-trained model later — no code change. |

## How services find these

- **Docker** mounts this directory to `/app/models` (see `docker-compose.yml`),
  and the backend env points `MDAV_VISION_WEIGHTS` / `MDAV_LAYOUT_WEIGHTS` there.
- **Local** runs: set the paths in `backend/.env` (see `backend/.env.example`):
  ```
  MDAV_VISION_WEIGHTS=../models/best.pth
  MDAV_LAYOUT_WEIGHTS=../models/best_layout_detector.pt
  MDAV_DIFFUSION_MODEL=../models/diffusion              # folder, see diffusion/README.md
  ```

If a weight file is absent, its branch degrades gracefully to a **vacuous**
Dempster-Shafer belief (contributes no evidence) — the pipeline still runs.
