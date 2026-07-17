from datetime import datetime, date

from app.services.belief import BeliefMass, from_check, fuse, vacuous


class SemanticValidator:
    def __init__(self):
        self.validation_rules = {
            "aadhaar": self._validate_aadhaar,
            "pan": self._validate_pan,
            "dates": self._validate_dates,
            "field_presence": self._validate_field_presence,
        }

    def validate(
        self,
        extracted_fields: dict,
        *,
        document_type: str = "unknown",
        document_side: str = "unknown",
        document_type_confidence: float = 0.0,
        ocr_confidence: float = 0.0,
        layout_available: bool = False,
        field_evidence: dict | None = None,
    ) -> dict:
        results = {
            "aadhaar_valid": None,
            "pan_valid": None,
            "dates_valid": None,
            "field_presence_valid": None,
            "consistency_score": 0.0,
            "validation_details": {},
            "status": "inconclusive",
        }
        rule_statuses: dict[str, str] = {
            "aadhaar": "not_applicable",
            "pan": "not_applicable",
            "dates": "not_evaluated",
            "field_presence": "not_evaluated",
        }

        if "aadhaar" in extracted_fields:
            results["aadhaar_valid"] = self._validate_aadhaar(extracted_fields["aadhaar"])
            results["validation_details"]["aadhaar"] = {
                "number": self._mask_identifier(extracted_fields["aadhaar"]),
                "valid": results["aadhaar_valid"],
            }
            rule_statuses["aadhaar"] = (
                "valid" if results["aadhaar_valid"] else "invalid"
            )

        if "pan" in extracted_fields:
            results["pan_valid"] = self._validate_pan(extracted_fields["pan"])
            results["validation_details"]["pan"] = {
                "number": self._mask_identifier(extracted_fields["pan"]),
                "valid": results["pan_valid"],
            }
            rule_statuses["pan"] = "valid" if results["pan_valid"] else "invalid"

        if "dates" in extracted_fields:
            results["dates_valid"] = self._validate_dates(extracted_fields["dates"])
            results["validation_details"]["dates"] = {
                "found": extracted_fields["dates"],
                "valid": results["dates_valid"],
            }
            rule_statuses["dates"] = (
                "valid" if results["dates_valid"] else "invalid"
            )

        field_presence, field_detail = self._validate_field_presence(
            extracted_fields,
            document_type=document_type,
            document_side=document_side,
            document_type_confidence=document_type_confidence,
            ocr_confidence=ocr_confidence,
            layout_available=layout_available,
            field_evidence=field_evidence,
        )
        results["field_presence_valid"] = field_presence
        results["validation_details"]["field_presence"] = {
            "fields_found": list(extracted_fields.keys()),
            "valid": field_presence,
            **field_detail,
        }
        rule_statuses["field_presence"] = field_detail["status"]
        results["validation_details"]["document_context"] = {
            "document_type": document_type,
            "side": document_side,
            "confidence": round(float(document_type_confidence), 4),
            "layout_available": bool(layout_available),
            "ocr_confidence": round(float(ocr_confidence), 4),
        }
        results["validation_details"]["rule_statuses"] = rule_statuses

        scores = []
        for key in ["aadhaar_valid", "pan_valid", "dates_valid", "field_presence_valid"]:
            if results[key] is not None:
                scores.append(1.0 if results[key] else 0.0)

        results["consistency_score"] = sum(scores) / len(scores) if scores else 0.5
        if any(status == "invalid" for status in rule_statuses.values()):
            results["status"] = "active"
        elif any(status == "valid" for status in rule_statuses.values()):
            results["status"] = "active"

        return results

    def to_belief(self, validation_result: dict) -> BeliefMass:
        """Convert a ``validate()`` result into a Dempster-Shafer belief mass.

        Each deterministic check becomes one piece of evidence, combined via
        Dempster's rule. The asymmetry is deliberate (see ``from_check``): a
        passing checksum is weak support for authenticity, while a *failing*
        checksum -- which a genuine document can never produce -- is strong
        evidence of forgery or OCR corruption. Checks that did not run
        (``None``) contribute nothing instead of a misleading 0.5 vote.
        """
        evidence = []
        # Verhoeff failure is near-conclusive; passing is only weak support.
        rule_statuses = (
            validation_result.get("validation_details", {}).get("rule_statuses", {})
        )
        if (
            validation_result.get("aadhaar_valid") is not None
            and rule_statuses.get("aadhaar") in {None, "valid", "invalid"}
        ):
            evidence.append(from_check(
                validation_result["aadhaar_valid"],
                w_pass=0.55, w_fail=0.95, source="semantic.aadhaar",
            ))
        # PAN format is a regex -> a forger trivially satisfies it; weak both ways.
        if (
            validation_result.get("pan_valid") is not None
            and rule_statuses.get("pan") in {None, "valid", "invalid"}
        ):
            evidence.append(from_check(
                validation_result["pan_valid"],
                w_pass=0.40, w_fail=0.75, source="semantic.pan",
            ))
        if (
            validation_result.get("dates_valid") is not None
            and rule_statuses.get("dates") in {None, "valid", "invalid"}
        ):
            evidence.append(from_check(
                validation_result["dates_valid"],
                w_pass=0.35, w_fail=0.70, source="semantic.dates",
            ))
        if (
            validation_result.get("field_presence_valid") is not None
            and rule_statuses.get("field_presence") in {None, "valid", "invalid"}
        ):
            evidence.append(from_check(
                validation_result["field_presence_valid"],
                w_pass=0.25, w_fail=0.55, source="semantic.fields",
            ))

        if not evidence:
            return vacuous(source="semantic")
        return fuse(evidence)

    def _validate_aadhaar(self, aadhaar_number: str) -> bool:
        aadhaar_number = aadhaar_number.replace(" ", "")
        if len(aadhaar_number) != 12:
            return False
        if not aadhaar_number.isdigit():
            return False

        digits = [int(d) for d in aadhaar_number]
        return self._verhoeff_check(digits)

    def _verhoeff_check(self, digits: list) -> bool:
        d = [
            [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
            [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
            [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
            [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
            [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
            [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
            [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
            [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
            [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
            [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
        ]
        p = [
            [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
            [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
            [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
            [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
            [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
            [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
            [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
            [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
        ]

        checksum = 0
        for i, digit in enumerate(reversed(digits)):
            checksum = d[checksum][p[i % 8][digit]]

        return checksum == 0

    def _validate_pan(self, pan_number: str) -> bool:
        import re
        pattern = r"^[A-Z]{5}[0-9]{4}[A-Z]$"
        return bool(re.match(pattern, pan_number))

    def _validate_dates(self, dates: list) -> bool:
        parsed_dates = []
        for date_str in dates:
            for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%Y-%m-%d"]:
                try:
                    parsed = datetime.strptime(date_str, fmt).date()
                    parsed_dates.append(parsed)
                    break
                except ValueError:
                    continue

        if not parsed_dates:
            return False

        today = date.today()
        for d in parsed_dates:
            if d > today:
                return False

        if len(parsed_dates) >= 2:
            sorted_dates = sorted(parsed_dates)
            if sorted_dates[-1] < sorted_dates[0]:
                return False

        return True

    def _validate_field_presence(
        self,
        fields: dict,
        *,
        document_type: str,
        document_side: str,
        document_type_confidence: float,
        ocr_confidence: float,
        layout_available: bool,
        field_evidence: dict | None = None,
    ) -> tuple[bool | None, dict]:
        required_by_context = {
            ("aadhaar", "front"): {"aadhaar", "name", "dates"},
            ("aadhaar", "back"): {"aadhaar", "address"},
            ("aadhaar", "combined"): {"aadhaar", "name", "dates", "address"},
            ("pan", "unknown"): {"pan", "name"},
        }

        if document_type_confidence < 0.65 or document_type == "unknown":
            return None, {
                "status": "not_evaluated",
                "reason": "Document type is not established confidently.",
                "expected_fields": [],
                "missing_fields": [],
            }
        if document_type == "aadhaar" and document_side == "unknown":
            return None, {
                "status": "not_evaluated",
                "reason": "Aadhaar side could not be established.",
                "expected_fields": [],
                "missing_fields": [],
            }

        expected = required_by_context.get((document_type, document_side))
        if expected is None:
            expected = required_by_context.get((document_type, "unknown"))
        if not expected:
            return None, {
                "status": "not_applicable",
                "reason": "No side-specific required-field rule is configured.",
                "expected_fields": [],
                "missing_fields": [],
            }

        found = set(fields)
        missing = sorted(expected - found)
        if not missing:
            return True, {
                "status": "valid",
                "reason": "All fields expected for the detected type and side were found.",
                "expected_fields": sorted(expected),
                "missing_fields": [],
            }
        field_evidence = field_evidence or {}
        covered_missing = {
            field: field_evidence[field]
            for field in missing
            if field in field_evidence
        }
        return None, {
            "status": "not_evaluated",
            "reason": (
                "Expected fields were not extracted. OCR omission is treated as "
                "incomplete evidence, not a document contradiction."
            ),
            "expected_fields": sorted(expected),
            "missing_fields": missing,
            "covered_missing_fields": sorted(covered_missing),
            "field_evidence": covered_missing,
        }

    @staticmethod
    def _mask_identifier(value) -> str:
        text = str(value or "")
        compact = "".join(text.split())
        if len(compact) <= 4:
            return compact
        return f"{'*' * (len(compact) - 4)}{compact[-4:]}"


semantic_validator = SemanticValidator()
