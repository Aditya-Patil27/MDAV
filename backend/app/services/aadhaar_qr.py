"""Aadhaar Secure QR (V2) branch.

The post-2018 Aadhaar QR code is not plain text: it encodes a single large
integer whose bytes are GZIP-compressed, 0xFF-delimited text fields followed by
an optional JPEG2000 photo and a trailing 256-byte RSA-2048 signature produced
by UIDAI's private key.

This branch:
  1. decodes the QR from the document image,
  2. decompresses + parses the Secure QR payload into structured fields,
  3. (optionally) verifies the embedded signature against a UIDAI certificate,
  4. cross-checks the QR fields against the OCR-extracted printed fields, and
  5. emits a :class:`BeliefMass` over {AUTHENTIC, FORGED}.

Key forensic signal: a genuine QR is digitally signed and cannot be forged
without UIDAI's key, so a *mismatch* between the tamper-proof QR and the printed
text (e.g. printed name edited, QR untouched) is strong evidence of forgery.
Absence of a QR is NOT evidence of forgery (a cropped photo legitimately lacks
one) -> that path stays vacuous.

Field order reference: UIDAI "Aadhaar Secure QR Code" specification, V2.
"""

from __future__ import annotations

import gzip
import re
import zlib

from app.services.belief import BeliefMass, from_check, vacuous

# Delimiter between text fields in the decompressed payload.
_DELIM = 0xFF
# Trailing RSA-2048 signature length in bytes.
_SIG_LEN = 256
# JPEG2000 magic (start of the embedded photo), used to stop text parsing.
_JP2_MAGIC = bytes([0x00, 0x00, 0x00, 0x0C, 0x6A, 0x50, 0x20, 0x20])

# Ordered text fields after the leading email/mobile indicator (V2 layout).
_FIELD_ORDER = [
    "reference_id",
    "name",
    "dob",
    "gender",
    "care_of",
    "district",
    "landmark",
    "house",
    "location",
    "pincode",
    "post_office",
    "state",
    "street",
    "sub_district",
    "vtc",
]


class AadhaarQRService:
    """Decode + verify the Aadhaar Secure QR and score authenticity."""

    def analyze(
        self,
        image_path: str,
        ocr_fields: dict | None = None,
        uidai_cert_path: str | None = None,
    ) -> dict:
        """Run the full QR branch on an image and return a result dict.

        ``ocr_fields`` are the printed fields from the OCR branch, used for
        cross-checking. ``uidai_cert_path`` enables signature verification.
        """
        numeric = self.decode_qr_from_image(image_path)
        if numeric is None:
            mass = vacuous(source="qr")
            return self._result(mass, qr_found=False, fields={}, reason="No QR code detected")

        try:
            parsed = self.parse_secure_qr(numeric)
        except Exception as e:  # noqa: BLE001 - corrupt QR is a real-world input
            mass = from_check(
                False, w_fail=0.55, source="qr",
                details={"error": str(e)},
            )
            return self._result(
                mass, qr_found=True, fields={},
                reason="QR present but payload could not be parsed",
            )

        fields = parsed["fields"]
        sig_status = self._verify_signature(parsed, uidai_cert_path)
        mismatches = self._cross_check(fields, ocr_fields or {})
        mass = self._score(sig_status, mismatches, fields)

        return self._result(
            mass,
            qr_found=True,
            fields=fields,
            reason=self._reason(sig_status, mismatches),
            signature_status=sig_status,
            mismatches=mismatches,
        )

    # ---- step 1: decode ------------------------------------------------------

    def decode_qr_from_image(self, image_path: str) -> str | None:
        """Return the raw numeric QR string, or None if no QR is decodable."""
        try:
            import cv2
        except ImportError:
            return None

        img = cv2.imread(image_path)
        if img is None:
            return None

        detector = cv2.QRCodeDetector()
        # detectAndDecodeMulti handles documents with more than one code.
        ok, decoded, _, _ = detector.detectAndDecodeMulti(img)
        candidates = list(decoded) if ok else []
        single, _, _ = detector.detectAndDecode(img)
        if single:
            candidates.append(single)

        for text in candidates:
            text = (text or "").strip()
            if text.isdigit() and len(text) > 100:
                return text
        return None

    # ---- step 2: parse -------------------------------------------------------

    def parse_secure_qr(self, numeric_string: str) -> dict:
        """Parse the Secure QR numeric string into fields + raw segments."""
        numeric_string = numeric_string.strip()
        if not numeric_string.isdigit():
            raise ValueError("QR payload is not a decimal integer")

        big = int(numeric_string)
        raw = big.to_bytes((big.bit_length() + 7) // 8, "big")
        decompressed = self._decompress(raw)
        return self._parse_payload(decompressed)

    @staticmethod
    def _decompress(raw: bytes) -> bytes:
        # UIDAI uses GZIP; fall back to raw deflate for robustness.
        try:
            return gzip.decompress(raw)
        except (OSError, EOFError, zlib.error):
            return zlib.decompress(raw, -zlib.MAX_WBITS)

    def _parse_payload(self, data: bytes) -> dict:
        signature = b""
        body = data
        if len(data) > _SIG_LEN:
            signature = data[-_SIG_LEN:]
            body = data[:-_SIG_LEN]

        # The photo (if present) begins at the JPEG2000 magic; text precedes it.
        photo_idx = body.find(_JP2_MAGIC)
        text_bytes = body if photo_idx == -1 else body[:photo_idx]
        photo = b"" if photo_idx == -1 else body[photo_idx:]

        segments = text_bytes.split(bytes([_DELIM]))
        # Keep ALL segments (including empty ones) so positional mapping holds --
        # an empty field is a real, delimited position in the V2 layout.
        tokens = [s.decode("iso-8859-1", "replace").strip() for s in segments]

        # First token is the email/mobile present indicator in V2; skip it.
        values = tokens[1:] if tokens and tokens[0].isdigit() and len(tokens[0]) <= 2 else tokens

        fields: dict[str, str] = {}
        for key, value in zip(_FIELD_ORDER, values):
            if value:
                fields[key] = value

        if "reference_id" in fields:
            fields["aadhaar_last4"] = self._extract_last4(fields["reference_id"])

        return {
            "fields": fields,
            "signature": signature,
            "signed_body": body,
            "photo_present": bool(photo),
            "raw_tokens": tokens,
        }

    @staticmethod
    def _extract_last4(reference_id: str) -> str:
        digits = re.sub(r"\D", "", reference_id)
        return digits[:4] if len(digits) >= 4 else ""

    # ---- step 3: signature ---------------------------------------------------

    def _verify_signature(self, parsed: dict, uidai_cert_path: str | None) -> str:
        signature = parsed.get("signature") or b""
        if len(signature) != _SIG_LEN:
            return "ABSENT"
        if not uidai_cert_path:
            return "UNVERIFIED"  # structurally present, no cert to check against

        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import padding
            from cryptography.x509 import load_pem_x509_certificate

            with open(uidai_cert_path, "rb") as f:
                cert = load_pem_x509_certificate(f.read())
            cert.public_key().verify(
                signature,
                parsed["signed_body"],
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            return "VALID"
        except Exception:  # noqa: BLE001 - any failure is an invalid signature
            return "INVALID"

    # ---- step 4: cross-check -------------------------------------------------

    def _cross_check(self, qr_fields: dict, ocr_fields: dict) -> list[str]:
        """Return the names of fields that disagree between QR and printed OCR."""
        mismatches: list[str] = []

        qr_name = self._norm(qr_fields.get("name", ""))
        ocr_name = self._norm(ocr_fields.get("name", ""))
        if qr_name and ocr_name and qr_name != ocr_name:
            mismatches.append("name")

        qr_last4 = qr_fields.get("aadhaar_last4", "")
        ocr_aadhaar = re.sub(r"\D", "", str(ocr_fields.get("aadhaar", "")))
        if qr_last4 and len(ocr_aadhaar) >= 4 and ocr_aadhaar[-4:] != qr_last4:
            mismatches.append("aadhaar")

        qr_dob = re.sub(r"\D", "", qr_fields.get("dob", ""))
        ocr_dates = ocr_fields.get("dates", []) or []
        ocr_dob_digits = {re.sub(r"\D", "", d) for d in ocr_dates}
        if qr_dob and ocr_dob_digits and not any(qr_dob in d or d in qr_dob for d in ocr_dob_digits):
            mismatches.append("dob")

        return mismatches

    @staticmethod
    def _norm(s: str) -> str:
        return re.sub(r"\s+", " ", s).strip().lower()

    # ---- step 5: scoring -----------------------------------------------------

    def _score(self, sig_status: str, mismatches: list[str], fields: dict) -> BeliefMass:
        # A confirmed-bad signature or a field mismatch against the signed QR is
        # strong forgery evidence; a valid signature is strong authentic
        # evidence. Everything else is graded weakly and left mostly uncertain.
        if sig_status == "INVALID":
            return from_check(False, w_fail=0.95, source="qr",
                              details={"signature": sig_status})
        if mismatches:
            return from_check(False, w_fail=0.85, source="qr",
                              details={"mismatches": mismatches})
        if sig_status == "VALID":
            return from_check(True, w_pass=0.95, source="qr",
                              details={"signature": sig_status})
        # UNVERIFIED but structurally sound and consistent with OCR -> mild support.
        w = 0.5 if fields else 0.3
        return from_check(True, w_pass=w, source="qr",
                          details={"signature": sig_status})

    # ---- helpers -------------------------------------------------------------

    def _reason(self, sig_status: str, mismatches: list[str]) -> str:
        if sig_status == "INVALID":
            return "QR digital signature failed verification"
        if mismatches:
            return f"QR contents disagree with printed fields: {', '.join(mismatches)}"
        if sig_status == "VALID":
            return "QR signature valid and consistent with printed fields"
        return "QR parsed and consistent; signature not cryptographically verified"

    def _result(self, mass: BeliefMass, **extra) -> dict:
        return {"belief": mass.to_dict(), "_mass": mass, **extra}


aadhaar_qr_service = AadhaarQRService()
