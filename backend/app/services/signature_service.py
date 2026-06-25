import hashlib
import os


class SignatureService:
    def __init__(self):
        self.pyhanko_available = False
        try:
            import pyhanko
            self.pyhanko_available = True
        except ImportError:
            pass

    def verify(self, file_path: str) -> dict:
        if not file_path.lower().endswith(".pdf"):
            return {
                "signature_detected": False,
                "certificate_valid": None,
                "hash_valid": None,
                "validation_result": "NOT_APPLICABLE",
                "details": {"reason": "File is not a PDF"},
            }

        if self.pyhanko_available:
            return self._verify_with_pyhanko(file_path)
        else:
            return self._mock_verification(file_path)

    def _verify_with_pyhanko(self, file_path: str) -> dict:
        try:
            from pyhanko.sign.validation import validate_pdf_signature
            from pyhanko.pdf_utils.reader import PdfFileReader

            with open(file_path, "rb") as f:
                reader = PdfFileReader(f)
                sig_fields = reader.embedded_signatures

                if not sig_fields:
                    return {
                        "signature_detected": False,
                        "certificate_valid": None,
                        "hash_valid": None,
                        "validation_result": "NO_SIGNATURE",
                        "details": {"reason": "No digital signature found in PDF"},
                    }

                status = validate_pdf_signature(sig_fields[0])

                return {
                    "signature_detected": True,
                    "certificate_valid": status.intact and status.valid,
                    "hash_valid": status.intact,
                    "validation_result": "VALID" if status.intact else "INVALID",
                    "details": {
                        "signer": str(status.signer_cert.subject.human_friendly),
                        "intact": status.intact,
                        "valid": status.valid,
                        "trust_status": str(status.trust_status),
                    },
                }
        except Exception as e:
            return {
                "signature_detected": False,
                "certificate_valid": None,
                "hash_valid": None,
                "validation_result": "ERROR",
                "details": {"error": str(e)},
            }

    def _mock_verification(self, file_path: str) -> dict:
        file_hash = self._compute_hash(file_path)

        return {
            "signature_detected": False,
            "certificate_valid": None,
            "hash_valid": None,
            "validation_result": "NO_SIGNATURE",
            "details": {
                "reason": "pyHanko not installed; mock verification",
                "file_hash": file_hash,
            },
        }

    def _compute_hash(self, file_path: str) -> str:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()


signature_service = SignatureService()
