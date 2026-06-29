# notebooks/

Training notebooks (run on Kaggle / Colab GPUs). Each produces a weight file
that is handed to `models/` and consumed by a backend branch.

| Notebook | Trains | Output | Consumed by |
|----------|--------|--------|-------------|
| `train_visual_doctamper.ipynb` | DCT+RGB ResNet18 U-Net tamper localizer | `best.pth` | `vision_service.py` |
| `train_layout_yolo.ipynb` | YOLOv8n Aadhaar field detector + COCO→YOLO prep | `best_layout_detector.pt` | `layout_service.py` |

> The **inference contract** (architecture + exact preprocessing) for each model
> must match the backend loader. If you retrain or change preprocessing, update
> the corresponding service. The AIForge diffusion model has no notebook here yet
> — see [`docs/AIForge_Agent_Brief.md`](../docs/AIForge_Agent_Brief.md).
