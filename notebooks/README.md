# notebooks/

Training notebooks run on Kaggle or Colab GPUs. Each produces a weight file
that is handed to `models/` and consumed by a backend branch.

| Notebook | Trains | Output | Consumed by |
|----------|--------|--------|-------------|
| `train_visual_doctamper.ipynb` | DCT+RGB ResNet18 U-Net tamper localizer | `best.pth` | `vision_service.py` |
| `train_aiforge_diffusion.ipynb` | DCT+RGB ResNet18 U-Net AI-forgery localizer on `AIForge_MDAV` | `best_diffusion.pth` | `diffusion_service.py` |
| `train_layout_yolo.ipynb` | YOLOv8n Aadhaar field detector and COCO-to-YOLO prep | `best_layout_detector.pt` | `layout_service.py` |

The inference contract, including architecture and exact preprocessing, must
match the backend loader. If you retrain or change preprocessing, update the
corresponding service.
