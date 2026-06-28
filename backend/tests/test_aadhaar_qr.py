"""Tests for the Aadhaar Secure QR branch.

We synthesise a Secure-QR-shaped payload (GZIP'd, 0xFF-delimited fields with a
256-byte trailing signature) so the parser and scoring are testable without an
image, a camera, or a real Aadhaar.
"""

import gzip

import pytest

from app.services.aadhaar_qr import AadhaarQRService

SIG_LEN = 256


def build_secure_qr(fields, *, with_signature=True, with_photo=False):
    """Encode field values the way a real Secure QR does, returning the numeric string.

    ``fields`` is the ordered list of text values (after the email/mobile
    indicator): reference_id, name, dob, gender, ...
    """
    delim = b"\xff"
    tokens = [b"2"]  # email/mobile present indicator
    tokens += [str(v).encode("iso-8859-1") for v in fields]
    body = delim.join(tokens)
    if with_photo:
        body += delim + bytes([0x00, 0x00, 0x00, 0x0C, 0x6A, 0x50, 0x20, 0x20]) + b"\x00" * 32
    if with_signature:
        body += bytes(range(256))  # fake 256-byte signature tail
    compressed = gzip.compress(body)
    big = int.from_bytes(compressed, "big")
    return str(big)


@pytest.fixture
def service():
    return AadhaarQRService()


def test_parse_roundtrip(service):
    numeric = build_secure_qr(
        ["1234ABCD", "Ravi Kumar", "01-01-1990", "M", "S/O Someone",
         "Pune", "", "", "", "411001", "", "Maharashtra", "", "", "Pune City"]
    )
    parsed = service.parse_secure_qr(numeric)
    fields = parsed["fields"]
    assert fields["name"] == "Ravi Kumar"
    assert fields["dob"] == "01-01-1990"
    assert fields["gender"] == "M"
    assert fields["pincode"] == "411001"
    assert fields["aadhaar_last4"] == "1234"
    assert len(parsed["signature"]) == SIG_LEN


def test_parse_with_photo_stops_text_at_photo(service):
    numeric = build_secure_qr(
        ["9999XY", "Asha", "15-08-1988", "F"], with_photo=True
    )
    parsed = service.parse_secure_qr(numeric)
    assert parsed["photo_present"] is True
    assert parsed["fields"]["name"] == "Asha"


def test_non_numeric_payload_rejected(service):
    with pytest.raises(ValueError):
        service.parse_secure_qr("not-a-number")


def test_clean_match_supports_authentic(service):
    fields = {"name": "Ravi Kumar", "dob": "01-01-1990", "aadhaar_last4": "1234"}
    ocr = {"name": "Ravi Kumar", "dates": ["01-01-1990"], "aadhaar": "999911111234"}
    mismatches = service._cross_check(fields, ocr)
    assert mismatches == []
    mass = service._score("UNVERIFIED", mismatches, fields)
    assert mass.belief() > mass.forged


def test_name_mismatch_is_strong_forgery_signal(service):
    fields = {"name": "Ravi Kumar", "aadhaar_last4": "1234"}
    ocr = {"name": "Vijay Sharma", "aadhaar": "999911111234"}
    mismatches = service._cross_check(fields, ocr)
    assert "name" in mismatches
    mass = service._score("UNVERIFIED", mismatches, fields)
    # Tamper-proof QR disagreeing with printed text -> forged dominates.
    assert mass.forged > mass.belief()


def test_aadhaar_last4_mismatch_detected(service):
    fields = {"aadhaar_last4": "1234"}
    ocr = {"aadhaar": "9999 1111 9876"}
    assert "aadhaar" in service._cross_check(fields, ocr)


def test_invalid_signature_is_conclusive(service):
    mass = service._score("INVALID", [], {"name": "X"})
    assert mass.forged > 0.9


def test_valid_signature_strong_authentic(service):
    mass = service._score("VALID", [], {"name": "X"})
    assert mass.belief() > 0.9


def test_missing_qr_path_is_vacuous(service, tmp_path):
    # No cv2 / unreadable path -> decode returns None -> vacuous, not forged.
    result = service.analyze(str(tmp_path / "nope.png"))
    assert result["qr_found"] is False
    assert result["_mass"].uncertain == 1.0
