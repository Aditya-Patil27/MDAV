"""Train the Aadhaar layout/field detector (YOLOv8) — reproducible wrapper.

This trains the *layout* branch (field localization: aadhaar_number, dob,
gender, name, address), NOT the forgery/tamper model. The output ``best.pt``
crops fields for OCR and powers the layout-consistency belief mass.

Prereqs:
    pip install ultralytics
    # dataset prepared via: python ml_service/prepare_aadhaar_yolo.py

Local (RTX 3050 6GB):
    python ml_service/train_layout.py --batch 16

Colab (T4 16GB):
    python ml_service/train_layout.py --batch 32
    # (after fixing data.yaml `path:` to the Colab dataset location)

The trained weights land in runs/detect/<name>/weights/best.pt (gitignored).
"""

from __future__ import annotations

import argparse
from pathlib import Path

DEFAULT_DATA = "ml_service/data/aadhaar_yolo/data.yaml"


def resolve_device(requested: str) -> str:
    """Return the device string, warning loudly if CUDA was expected but absent."""
    if requested != "auto":
        return requested
    try:
        import torch
        if torch.cuda.is_available():
            print(f"[device] CUDA: {torch.cuda.get_device_name(0)}")
            return "0"
        print("[device] WARNING: CUDA not available -> training on CPU (~10x slower). "
              "On Windows, reinstall the CUDA torch build from pytorch.org.")
        return "cpu"
    except ImportError:
        print("[device] torch not found; letting ultralytics choose.")
        return ""


def train(args: argparse.Namespace):
    data_path = Path(args.data)
    if not data_path.exists():
        raise FileNotFoundError(
            f"data.yaml not found at {data_path}. Run prepare_aadhaar_yolo.py first, "
            "or pass --data with the correct path (on Colab, point it at /content/...)."
        )

    from ultralytics import YOLO  # lazy: keeps this file inspectable without the dep

    device = resolve_device(args.device)
    model = YOLO(args.model)
    results = model.train(
        data=str(data_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=device,
        patience=args.patience,
        cache=args.cache,
        name=args.name,
    )

    best = Path(results.save_dir) / "weights" / "best.pt"
    print(f"\n[done] best weights: {best}")
    print("       hand this off as the layout detector (loads in layout_service.py).")
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=DEFAULT_DATA, help="path to YOLO data.yaml")
    ap.add_argument("--model", default="yolov8n.pt", help="base weights (yolov8n.pt / yolov8s.pt)")
    ap.add_argument("--epochs", type=int, default=80)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=16, help="16 for 6GB GPUs, 32 for T4; -1 = auto")
    ap.add_argument("--device", default="auto", help="'auto', '0', 'cpu'")
    ap.add_argument("--patience", type=int, default=20, help="early-stop patience on val mAP")
    ap.add_argument("--cache", default="ram", help="'ram' | 'disk' | False (RAM speeds small sets up)")
    ap.add_argument("--name", default="aadhaar_layout", help="run name under runs/detect/")
    train(ap.parse_args())


if __name__ == "__main__":
    main()
