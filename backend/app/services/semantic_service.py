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

    def validate(self, extracted_fields: dict) -> dict:
        results = {
            "aadhaar_valid": None,
            "pan_valid": None,
            "dates_valid": None,
            "field_presence_valid": None,
            "consistency_score": 0.0,
            "validation_details": {},
        }

        if "aadhaar" in extracted_fields:
            results["aadhaar_valid"] = self._validate_aadhaar(extracted_fields["aadhaar"])
            results["validation_details"]["aadhaar"] = {
                "number": extracted_fields["aadhaar"],
                "valid": results["aadhaar_valid"],
            }

        if "pan" in extracted_fields:
            results["pan_valid"] = self._validate_pan(extracted_fields["pan"])
            results["validation_details"]["pan"] = {
                "number": extracted_fields["pan"],
                "valid": results["pan_valid"],
            }

        if "dates" in extracted_fields:
            results["dates_valid"] = self._validate_dates(extracted_fields["dates"])
            results["validation_details"]["dates"] = {
                "found": extracted_fields["dates"],
                "valid": results["dates_valid"],
            }

        results["field_presence_valid"] = self._validate_field_presence(extracted_fields)
        results["validation_details"]["field_presence"] = {
            "fields_found": list(extracted_fields.keys()),
            "valid": results["field_presence_valid"],
        }

        scores = []
        for key in ["aadhaar_valid", "pan_valid", "dates_valid", "field_presence_valid"]:
            if results[key] is not None:
                scores.append(1.0 if results[key] else 0.0)

        results["consistency_score"] = sum(scores) / len(scores) if scores else 0.5

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
        if validation_result.get("aadhaar_valid") is not None:
            evidence.append(from_check(
                validation_result["aadhaar_valid"],
                w_pass=0.55, w_fail=0.95, source="semantic.aadhaar",
            ))
        # PAN format is a regex -> a forger trivially satisfies it; weak both ways.
        if validation_result.get("pan_valid") is not None:
            evidence.append(from_check(
                validation_result["pan_valid"],
                w_pass=0.40, w_fail=0.75, source="semantic.pan",
            ))
        if validation_result.get("dates_valid") is not None:
            evidence.append(from_check(
                validation_result["dates_valid"],
                w_pass=0.35, w_fail=0.70, source="semantic.dates",
            ))
        if validation_result.get("field_presence_valid") is not None:
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

    def _validate_field_presence(self, fields: dict) -> bool:
        required_fields = ["name"]
        found_fields = set(fields.keys())
        return any(f in found_fields for f in required_fields)


semantic_validator = SemanticValidator()
