"""Convert the AADHAAR-CARD-DETAILS COCO export into a YOLO dataset.

The Roboflow export ships COCO JSON with meaningless numeric class names
(0..4) and a single `train` split. This script:
  * remaps category ids -> semantic field names,
  * converts COCO bboxes ([x, y, w, h] absolute) -> YOLO ([cx, cy, w, h] norm),
  * carves a deterministic train/val split, and
  * writes a YOLO directory tree + data.yaml ready for `yolo detect train`.

Output lives under ml_service/data/ (gitignored -- the images are real PII).

Usage:
    python ml_service/prepare_aadhaar_yolo.py \
        --src AADHAAR-CARD-DETAILS.coco \
        --out ml_service/data/aadhaar_yolo \
        --val-frac 0.15
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

# COCO category_id (from the export) -> YOLO class index + name.
# Decoded by inspecting annotated samples; class 0 is a Roboflow placeholder.
COCO_TO_YOLO = {
    1: (0, "aadhaar_number"),
    2: (1, "dob"),
    3: (2, "gender"),
    4: (3, "name"),
    5: (4, "address"),
}
CLASS_NAMES = [name for _, (_, name) in sorted(COCO_TO_YOLO.items())]


def convert(src: Path, out: Path, val_frac: float, seed: int = 42) -> dict:
    coco = json.loads((src / "train" / "_annotations.coco.json").read_text(encoding="utf-8"))
    images = {img["id"]: img for img in coco["images"]}

    anns_by_image: dict[int, list] = {}
    for ann in coco["annotations"]:
        if ann["category_id"] not in COCO_TO_YOLO:
            continue  # skip placeholder / unknown categories
        anns_by_image.setdefault(ann["image_id"], []).append(ann)

    # Deterministic split: hash image id so re-runs are stable.
    import random
    ids = sorted(images.keys())
    random.Random(seed).shuffle(ids)
    n_val = int(len(ids) * val_frac)
    val_ids = set(ids[:n_val])

    counts = {"train": 0, "val": 0, "boxes": 0, "skipped_no_ann": 0}
    for split in ("train", "val"):
        (out / "images" / split).mkdir(parents=True, exist_ok=True)
        (out / "labels" / split).mkdir(parents=True, exist_ok=True)

    for img_id in ids:
        img = images[img_id]
        anns = anns_by_image.get(img_id, [])
        if not anns:
            counts["skipped_no_ann"] += 1
            continue
        split = "val" if img_id in val_ids else "train"

        src_img = src / "train" / img["file_name"]
        if not src_img.exists():
            continue
        shutil.copy2(src_img, out / "images" / split / img["file_name"])

        w, h = img["width"], img["height"]
        lines = []
        for ann in anns:
            cls_idx = COCO_TO_YOLO[ann["category_id"]][0]
            x, y, bw, bh = ann["bbox"]
            cx = (x + bw / 2) / w
            cy = (y + bh / 2) / h
            lines.append(f"{cls_idx} {cx:.6f} {cy:.6f} {bw / w:.6f} {bh / h:.6f}")
            counts["boxes"] += 1

        label_path = out / "labels" / split / (Path(img["file_name"]).stem + ".txt")
        label_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        counts[split] += 1

    data_yaml = (
        f"path: {out.resolve().as_posix()}\n"
        f"train: images/train\n"
        f"val: images/val\n"
        f"nc: {len(CLASS_NAMES)}\n"
        f"names: {CLASS_NAMES}\n"
    )
    (out / "data.yaml").write_text(data_yaml, encoding="utf-8")
    return counts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", default="AADHAAR-CARD-DETAILS.coco", type=Path)
    ap.add_argument("--out", default="ml_service/data/aadhaar_yolo", type=Path)
    ap.add_argument("--val-frac", default=0.15, type=float)
    args = ap.parse_args()

    counts = convert(args.src, args.out, args.val_frac)
    print(f"YOLO dataset written to {args.out}")
    print(f"  classes: {CLASS_NAMES}")
    print(f"  train images: {counts['train']}")
    print(f"  val images:   {counts['val']}")
    print(f"  total boxes:  {counts['boxes']}")
    print(f"  skipped (no annotations): {counts['skipped_no_ann']}")
    print(f"  data.yaml:    {args.out}/data.yaml")


if __name__ == "__main__":
    main()
