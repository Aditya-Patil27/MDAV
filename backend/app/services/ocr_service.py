class OCRService:
    def __init__(self):
        self.ocr = None

    def _ensure_loaded(self):
        if self.ocr is None:
            from paddleocr import PaddleOCR

            self.ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        return self.ocr

    def extract_text(self, image_path: str, regions: list | None = None) -> dict:
        """OCR a document.

        ``regions`` are optional YOLO layout detections
        (``[{"label","bbox":[x1,y1,x2,y2],...}]``). When provided, each labelled
        field is OCR'd from its own tight crop and used as the authoritative
        value for that field -- a crop reads far more reliably than regex over
        whole-page text, and it maps text to a field directly instead of
        guessing. Whole-image OCR still runs as raw text + regex fallback.
        """
        ocr = self._ensure_loaded()
        result = ocr.ocr(image_path, cls=True)

        lines = []
        total_confidence = 0.0
        count = 0

        for line in (result[0] if result and result[0] else []):
            text = line[1][0]
            confidence = line[1][1]
            lines.append(text)
            total_confidence += confidence
            count += 1

        raw_text = "\n".join(lines)
        avg_confidence = total_confidence / count if count > 0 else 0.0

        # Whole-image regex extraction is the baseline / fallback.
        extracted_fields = self._extract_fields(raw_text)
        field_sources = {k: "page" for k in extracted_fields}
        field_evidence = {
            key: {
                "source": "page",
                "text_found": True,
                "ocr_confidence": round(float(avg_confidence), 4),
            }
            for key in extracted_fields
        }

        # Layout crops override where present (higher-trust, field-targeted).
        if regions:
            crop_fields, crop_evidence = self._ocr_regions(image_path, regions)
            for key, value in crop_fields.items():
                extracted_fields[key] = value
                field_sources[key] = "layout_crop"
            field_evidence.update(crop_evidence)

        return {
            "raw_text": raw_text,
            "extracted_fields": extracted_fields,
            "confidence": avg_confidence,
            "field_sources": field_sources,
            "field_evidence": field_evidence,
        }

    # Layout class label -> semantic field name the validator expects.
    _LABEL_TO_FIELD = {
        "aadhaar_number": "aadhaar",
        "dob": "dates",
        "name": "name",
        "address": "address",
        "gender": "gender",
    }

    def _ocr_regions(self, image_path: str, regions: list) -> tuple[dict, dict]:
        """OCR layout crops and retain field-level coverage diagnostics."""
        import cv2

        img = cv2.imread(image_path)
        if img is None:
            return {}, {}
        h, w = img.shape[:2]

        out: dict = {}
        evidence: dict = {}
        for det in regions:
            field = self._LABEL_TO_FIELD.get(det.get("label"))
            if field is None:
                continue
            field_evidence = {
                "source": "layout_crop",
                "layout_detected": True,
                "layout_confidence": round(float(det.get("confidence", 0.0)), 4),
                "text_found": False,
                "ocr_confidence": 0.0,
            }
            x1, y1, x2, y2 = det.get("bbox", [0, 0, 0, 0])
            # Clamp + small pad; skip degenerate boxes.
            x1, y1 = max(0, x1 - 2), max(0, y1 - 2)
            x2, y2 = min(w, x2 + 2), min(h, y2 + 2)
            if x2 - x1 < 4 or y2 - y1 < 4:
                field_evidence["reason"] = "layout crop is too small for OCR"
                evidence[field] = field_evidence
                continue
            crop = img[y1:y2, x1:x2]
            text, crop_confidence = self._ocr_crop_text(crop)
            field_evidence["ocr_confidence"] = round(float(crop_confidence), 4)
            if not text:
                evidence[field] = field_evidence
                continue
            if field == "aadhaar":
                digits = "".join(ch for ch in text if ch.isdigit())
                if digits:
                    out["aadhaar"] = digits
                    field_evidence["text_found"] = True
            elif field == "dates":
                import re
                m = re.search(r"\d{2}[/-]\d{2}[/-]\d{4}|\d{4}[/-]\d{2}[/-]\d{2}", text)
                out["dates"] = [m.group()] if m else [text]
                field_evidence["text_found"] = True
            else:
                out[field] = text
                field_evidence["text_found"] = True
            evidence[field] = field_evidence
        return out, evidence

    def _ocr_crop_text(self, crop) -> tuple[str, float]:
        res = self._ensure_loaded().ocr(crop, cls=True)
        if not res or not res[0]:
            return "", 0.0
        lines = res[0]
        text = " ".join(line[1][0] for line in lines).strip()
        confidence = sum(float(line[1][1]) for line in lines) / len(lines)
        return text, confidence

    def _extract_fields(self, text: str) -> dict:
        import re

        fields = {}

        aadhaar_match = re.search(r"\b\d{4}\s?\d{4}\s?\d{4}\b", text)
        if aadhaar_match:
            fields["aadhaar"] = aadhaar_match.group().replace(" ", "")

        pan_match = re.search(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", text)
        if pan_match:
            fields["pan"] = pan_match.group()

        date_patterns = [
            r"\b(\d{2}[/-]\d{2}[/-]\d{4})\b",
            r"\b(\d{4}[/-]\d{2}[/-]\d{2})\b",
        ]
        dates = []
        for pattern in date_patterns:
            matches = re.findall(pattern, text)
            dates.extend(matches)
        if dates:
            fields["dates"] = dates

        name_indicators = ["Name", "NAME", "name", "नाम"]
        for indicator in name_indicators:
            if indicator in text:
                idx = text.index(indicator)
                name_text = text[idx + len(indicator):idx + len(indicator) + 50].strip()
                name_lines = name_text.split("\n")
                if name_lines:
                    fields["name"] = name_lines[0].strip()
                    break

        return fields


ocr_service = OCRService()
