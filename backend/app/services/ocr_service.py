from paddleocr import PaddleOCR
import os


class OCRService:
    def __init__(self):
        self.ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)

    def extract_text(self, image_path: str) -> dict:
        result = self.ocr.ocr(image_path, cls=True)

        if not result or not result[0]:
            return {"raw_text": "", "extracted_fields": {}, "confidence": 0.0}

        lines = []
        total_confidence = 0.0
        count = 0

        for line in result[0]:
            text = line[1][0]
            confidence = line[1][1]
            lines.append(text)
            total_confidence += confidence
            count += 1

        raw_text = "\n".join(lines)
        avg_confidence = total_confidence / count if count > 0 else 0.0

        extracted_fields = self._extract_fields(raw_text)

        return {
            "raw_text": raw_text,
            "extracted_fields": extracted_fields,
            "confidence": avg_confidence,
        }

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

        name_indicators = ["Name", "NAME", "name", "पता"]
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
