"""
xfund_loader.py — XFUND dataset parser.

Converts raw XFUND JSON annotations into UnifiedDocument instances.

XFUND annotation structure (discovered from file scan):
Single JSON file per language+split: {lang}.{split}.json

{
  "lang": str,          e.g. "de"
  "version": str,
  "split": str,         e.g. "train"
  "documents": [
    {
      "id": str,         e.g. "de_train_0"
      "uid": str,
      "document": [
        {
          "box": [x1, y1, x2, y2],
          "text": str,
          "label": str,  "other" | "header" | "question" | "answer"
          "words": [{"box": [x1,y1,x2,y2], "text": str}, ...],
          "linking": [[src_id, tgt_id], ...],
          "id": int
        }
      ],
      "img": {
        "fname": str,    e.g. "de_train_0.jpg"
        "width": int,
        "height": int
      }
    }
  ]
}

Language codes (actual values in the JSON "lang" field):
  de, en, es, fr, it, ja, pt, zh
Image dir: XFUND/XFUND and FUNSD/{lang}.{split}/
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.schema import UnifiedDocument, UnifiedField
from src.utils import resolve_dataset_root

logger = logging.getLogger(__name__)

XFUND_DOCUMENT_TYPE = "form"

# Language → ISO 639-1 code (direct passthrough since XFUND uses ISO codes)
_LANG_MAP: dict[str, str] = {
    "de": "de",
    "en": "en",
    "es": "es",
    "fr": "fr",
    "it": "it",
    "ja": "ja",
    "pt": "pt",
    "zh": "zh",
}

# Available language+split file pairs
_XFUND_FILES: list[tuple[str, str]] = [
    ("de", "train"), ("de", "val"),
    ("en", "train"), ("en", "val"),
    ("es", "train"), ("es", "val"),
    ("fr", "train"), ("fr", "val"),
    ("it", "train"), ("it", "val"),
    ("ja", "train"), ("ja", "val"),
    ("pt", "train"), ("pt", "val"),
    ("zh", "train"), ("zh", "val"),
]


def _bbox_to_polygon(bbox: list[int]) -> list[list[int]]:
    """Convert [x1,y1,x2,y2] to four-corner polygon.

    Args:
        bbox: Axis-aligned bounding box.

    Returns:
        Four-point polygon [[x,y], ...].
    """
    x1, y1, x2, y2 = bbox
    return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]


def _parse_xfund_document(
    raw_doc: dict,
    lang: str,
    split: str,
    img_dir: Path,
) -> UnifiedDocument | None:
    """Parse a single XFUND document entry into a UnifiedDocument.

    Args:
        raw_doc: Raw document dict from the XFUND JSON.
        lang: Language code string.
        split: Split name.
        img_dir: Directory containing the image file.

    Returns:
        UnifiedDocument or None if the image is missing.
    """
    img_meta = raw_doc.get("img", {})
    fname = img_meta.get("fname", "")
    width = img_meta.get("width", 0)
    height = img_meta.get("height", 0)

    image_path = img_dir / fname
    if not image_path.exists():
        logger.warning("XFUND image missing: %s — skipping", image_path)
        return None

    doc_id_raw = raw_doc.get("id", "")
    # Produce a stable, unique image_id
    image_id = f"xfund_{doc_id_raw}"

    fields: list[UnifiedField] = []

    for item in raw_doc.get("document", []):
        item_id = item.get("id", 0)
        label = item.get("label", "other")
        text = item.get("text", "").strip()
        bbox = item.get("box", [0, 0, 0, 0])
        words_raw = item.get("words", [])
        linking = item.get("linking", [])

        if not text:
            continue

        # Build polygon from word boxes if available, else from item box
        if words_raw:
            word_boxes = [w.get("box", bbox) for w in words_raw]
            xs = [b[0] for b in word_boxes] + [b[2] for b in word_boxes]
            ys = [b[1] for b in word_boxes] + [b[3] for b in word_boxes]
            poly = []
            for wb in word_boxes:
                poly.extend(_bbox_to_polygon(wb))
        else:
            poly = _bbox_to_polygon(bbox)

        field = UnifiedField(
            field_id=f"{image_id}_item{item_id}",
            label=label,
            text=text,
            bbox=bbox,
            polygon=poly,
            confidence=1.0,
            extra={
                "xfund_item_id": item_id,
                "linking": linking,
                "word_count": len(words_raw),
                "words": [w.get("text", "") for w in words_raw],
            },
        )
        fields.append(field)

    language = _LANG_MAP.get(lang, lang)

    return UnifiedDocument(
        image_id=image_id,
        dataset="XFUND",
        split=split,
        language=language,
        document_type=XFUND_DOCUMENT_TYPE,
        width=width,
        height=height,
        image_path=image_path,
        fields=fields,
        metadata={
            "xfund_lang": lang,
            "xfund_doc_id": doc_id_raw,
            "uid": raw_doc.get("uid", ""),
        },
    )


def _load_xfund_file(
    json_path: Path,
    lang: str,
    split: str,
    img_dir: Path,
) -> list[UnifiedDocument]:
    """Load all documents from one XFUND JSON file.

    Args:
        json_path: Path to the XFUND JSON file.
        lang: Language code.
        split: Split name.
        img_dir: Directory containing images.

    Returns:
        List of UnifiedDocument instances.
    """
    try:
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load XFUND file %s: %s", json_path, exc)
        return []

    documents: list[UnifiedDocument] = []
    for raw_doc in data.get("documents", []):
        doc = _parse_xfund_document(raw_doc, lang, split, img_dir)
        if doc is not None:
            documents.append(doc)

    logger.info("XFUND %s.%s: parsed %d documents", lang, split, len(documents))
    return documents


def load_xfund(
    languages: list[str] | None = None,
    splits: list[str] | None = None,
) -> list[UnifiedDocument]:
    """Load XFUND dataset for selected languages and splits.

    Args:
        languages: List of language codes to load (e.g. ["de", "en"]).
                   Defaults to all 8 languages.
        splits: List of split names. Defaults to ["train", "val"].

    Returns:
        List of UnifiedDocument instances.
    """
    if languages is None:
        languages = ["de", "en", "es", "fr", "it", "ja", "pt", "zh"]
    if splits is None:
        splits = ["train", "val"]

    # XFUND files live in "XFUND and FUNSD" sub-directory
    xfund_root = resolve_dataset_root() / "XFUND" / "XFUND and FUNSD"

    if not xfund_root.exists():
        logger.error("XFUND root directory not found: %s", xfund_root)
        return []

    documents: list[UnifiedDocument] = []

    for lang in languages:
        for split in splits:
            json_path = xfund_root / f"{lang}.{split}.json"
            img_dir = xfund_root / f"{lang}.{split}"

            if not json_path.exists():
                logger.warning("XFUND file not found: %s — skipping", json_path)
                continue
            if not img_dir.exists():
                logger.warning("XFUND image dir not found: %s — skipping", img_dir)
                continue

            docs = _load_xfund_file(json_path, lang, split, img_dir)
            documents.extend(docs)

    logger.info("XFUND: loaded %d documents total", len(documents))
    return documents
