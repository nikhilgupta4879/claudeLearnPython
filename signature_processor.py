"""
signature_processor.py
-----------------------
Handles the digital signature section (digSign) of a signed BE JSON file.

The digSign block contains:
  startSignature   – Base64-encoded RSA signature over the JSON content
  startCertificate – Base64-encoded DER X.509 certificate of the signer
  signerVersion    – schema version string

Signature verification requires the 'cryptography' package:
    pip install cryptography

If the package is not available or its native extensions cannot load,
extraction and decoding still work; only the verify step is skipped.
"""

import base64
import json
from dataclasses import dataclass
from pathlib import Path


def _load_crypto():
    """Lazily import cryptography; returns (x509, hashes, padding, InvalidSignature) or None."""
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.exceptions import InvalidSignature
        return x509, hashes, padding, InvalidSignature
    except BaseException:
        return None


# ---------------------------------------------------------------------------
# Data container
# ---------------------------------------------------------------------------

@dataclass
class SignatureInfo:
    """Decoded information extracted from the digSign section."""
    raw_signature_b64: str
    raw_certificate_b64: str
    signer_version: str
    # Decoded bytes
    signature_bytes: bytes
    certificate_bytes: bytes
    # Certificate fields (populated when cryptography is available)
    subject_cn: str = ""
    subject_org: str = ""
    issuer_cn: str = ""
    valid_from: str = ""
    valid_to: str = ""
    serial_number: str = ""


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def has_signature(raw: dict) -> bool:
    """Return True if the raw JSON dict contains a digSign block."""
    return "digSign" in raw and bool(raw["digSign"])


def extract(raw: dict) -> SignatureInfo:
    """
    Extract and decode the digSign block from a raw BE JSON dict.

    Raises KeyError  if no digSign section is found.
    Raises ValueError if Base64 decoding fails.
    """
    if not has_signature(raw):
        raise KeyError("No 'digSign' section found in the provided JSON.")

    dig = raw["digSign"]
    sig_b64 = dig["startSignature"]
    cert_b64 = dig["startCertificate"]
    version = dig.get("signerVersion", "")

    sig_bytes = base64.b64decode(sig_b64)
    cert_bytes = base64.b64decode(cert_b64)

    info = SignatureInfo(
        raw_signature_b64=sig_b64,
        raw_certificate_b64=cert_b64,
        signer_version=version,
        signature_bytes=sig_bytes,
        certificate_bytes=cert_bytes,
    )

    crypto = _load_crypto()
    if crypto is not None:
        _populate_cert_fields(info, cert_bytes, crypto[0])

    return info


def _populate_cert_fields(info: SignatureInfo, cert_bytes: bytes, x509_mod) -> None:
    """Parse the X.509 certificate and fill the human-readable fields."""
    cert = x509_mod.load_der_x509_certificate(cert_bytes)

    def _get_attr(name_obj, oid):
        try:
            return name_obj.get_attributes_for_oid(oid)[0].value
        except (IndexError, Exception):
            return ""

    info.subject_cn = _get_attr(cert.subject, x509_mod.NameOID.COMMON_NAME)
    info.subject_org = _get_attr(cert.subject, x509_mod.NameOID.ORGANIZATION_NAME)
    info.issuer_cn = _get_attr(cert.issuer, x509_mod.NameOID.COMMON_NAME)
    info.valid_from = cert.not_valid_before_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
    info.valid_to = cert.not_valid_after_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
    info.serial_number = hex(cert.serial_number)


# ---------------------------------------------------------------------------
# Signed content construction
# ---------------------------------------------------------------------------

def build_signable_content(raw: dict) -> bytes:
    """
    Re-construct the byte string that was signed.

    Convention: the signature covers the JSON content excluding digSign,
    serialised compact (no extra spaces).
    """
    content = {k: v for k, v in raw.items() if k != "digSign"}
    return json.dumps(content, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

class VerificationResult:
    def __init__(self, valid: bool, message: str):
        self.valid = valid
        self.message = message

    def __bool__(self):
        return self.valid

    def __repr__(self):
        status = "VALID" if self.valid else "INVALID"
        return f"VerificationResult({status}: {self.message})"


def verify(raw: dict, sig_info: SignatureInfo | None = None) -> VerificationResult:
    """
    Verify that the signature in digSign is valid for the JSON content.

    Parameters
    ----------
    raw      : the full raw dict loaded from the signed JSON file
    sig_info : pre-extracted SignatureInfo; will be extracted if not supplied

    Returns a VerificationResult (truthy when signature is valid).
    """
    crypto = _load_crypto()
    if crypto is None:
        return VerificationResult(
            False,
            "cryptography package not available – cannot verify. "
            "Run: pip install cryptography",
        )

    x509_mod, hashes, padding, InvalidSignature = crypto

    if sig_info is None:
        sig_info = extract(raw)

    cert = x509_mod.load_der_x509_certificate(sig_info.certificate_bytes)
    public_key = cert.public_key()
    content_bytes = build_signable_content(raw)

    try:
        public_key.verify(
            sig_info.signature_bytes,
            content_bytes,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return VerificationResult(True, "Signature is valid.")
    except InvalidSignature:
        return VerificationResult(
            False,
            "Signature verification FAILED – data may have been tampered.",
        )
    except Exception as exc:
        return VerificationResult(False, f"Verification error: {exc}")


# ---------------------------------------------------------------------------
# Human-readable output
# ---------------------------------------------------------------------------

def summarise(sig_info: SignatureInfo) -> None:
    """Print a human-readable summary of the signature information."""
    print("=" * 60)
    print("DIGITAL SIGNATURE SUMMARY")
    print("=" * 60)
    print(f"  Signer Version   : {sig_info.signer_version}")
    print(f"  Signature (bytes): {len(sig_info.signature_bytes)} bytes")
    print(f"  Signature (hex)  : {sig_info.signature_bytes[:16].hex()}…")

    if sig_info.subject_cn:
        print()
        print("  Certificate Subject:")
        print(f"    Common Name  : {sig_info.subject_cn}")
        print(f"    Organisation : {sig_info.subject_org}")
        print()
        print("  Certificate Issuer:")
        print(f"    Common Name  : {sig_info.issuer_cn}")
        print()
        print("  Validity:")
        print(f"    Not Before   : {sig_info.valid_from}")
        print(f"    Not After    : {sig_info.valid_to}")
        print(f"    Serial No.   : {sig_info.serial_number}")
    else:
        print()
        print("  (Install 'cryptography' for certificate details)")

    print("=" * 60)
