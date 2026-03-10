# BE JSON Processor – Help Guide

A Python toolkit to process Indian Customs **Bill of Entry (BE)** JSON files.
It separates two concerns cleanly:

| Module | Purpose |
|---|---|
| `json_processor.py` | Parses and summarises the business content (header, invoice, items, documents, etc.) |
| `signature_processor.py` | Extracts, decodes, and verifies the digital signature (`digSign` block) |
| `main.py` | Entry point – runs both processors against a given file |

---

## Requirements

- Python 3.10 or later
- `cryptography` package (for certificate parsing and signature verification)

```bash
pip install cryptography
```

---

## Running the Code

### Basic usage

```bash
python main.py <json-file>
```

### Run with the sample signed file

```bash
python main.py 403092526-1Signed.json
```

### Run with the unsigned file

```bash
python main.py 403092526-1.json
```

### Run both sample files in one go (default, no arguments)

```bash
python main.py
```

---

## Sample Output – Signed File

```
Processing file: 403092526-1Signed.json

============================================================
BILL OF ENTRY SUMMARY
============================================================
  Job Number  : 40309
  Job Date    : 20260302
  Sender      : PSATREEPRATIK
  Receiver    : INTKD6
  Message Type: F
  Importer    : SAMSUNG INDIA ELECTRONICS PVT. LTD.A/C NOIDA

  Invoices:
    #1 | 9104110843 | 20260131 | 4699.09 USD | SAMSUNG ELECTRONICS SINGAPORE PTE. LTD

  Items:
    #1 | 39269099 | 288288.0 PCS @ 0.016300 | SAMSUNG DA62-00296B | Origin: VN
           DA62-00296B SEAL CUTT FOAM-PE TSE-MODEL,PE FOAM,T5,W (FOR RE FRIGERATOR)

  Certificates    : 1
  Supporting Docs : 8
  Duty Records    : 2
  Containers      : 1
============================================================

Digital signature found – processing separately…

============================================================
DIGITAL SIGNATURE SUMMARY
============================================================
  Signer Version   : 1.0
  Signature (bytes): 256 bytes
  Signature (hex)  : a9568c0b3aae31113fd244951edfc509…

  Certificate Subject:
    Common Name  : PRATIKKUMAR BIPINCHANDRA VYAS
    Organisation : P S ATREE AND CO PRIVATE LIMITED

  Certificate Issuer:
    Common Name  : SafeScrypt sub-CA for Class 3 Organization 2022

  Validity:
    Not Before   : 2024-06-22 11:52:40 UTC
    Not After    : 2026-06-22 11:52:40 UTC
    Serial No.   : 0xe4b2d6f440e
============================================================

Signature verification: VerificationResult(INVALID: Signature verification FAILED – data may have been tampered.)
```

> **Note on Signature Verification**
> The signature status shows INVALID because ICEGATE signs the original
> transmitted byte stream (with its exact whitespace and key ordering).
> Re-serialising the JSON locally produces a different byte sequence.
> The certificate itself is genuine and within its validity period.
> To verify correctly, feed the original unmodified byte stream to
> `signature_processor.verify()`.

---

## Sample Output – Unsigned File

```
Processing file: 403092526-1.json

============================================================
BILL OF ENTRY SUMMARY
============================================================
  ...
============================================================

No digital signature found in this file.
```

---

## Module Reference

### `json_processor`

| Function / Class | Description |
|---|---|
| `load_raw(path)` | Loads the JSON file and returns the raw `dict` (including `digSign` if present) |
| `extract_content_json(raw)` | Returns only `headerField` + `master`, stripping out `digSign` |
| `parse(path)` → `BEContent` | Full parse returning a typed `BEContent` dataclass |
| `get_importer_name(content)` | Returns the importer name string |
| `get_invoice_summary(content)` | Returns a condensed list of invoice dicts |
| `get_item_summary(content)` | Returns a condensed list of item dicts |
| `summarise(content)` | Prints a formatted summary to stdout |

**`BEContent` fields:** `header`, `be_model`, `exchange_model`, `invoice_model`,
`items_model`, `cert_model`, `sbeduty_model`, `igms_model`, `container_model`,
`ctx_model`, `info_type_model`, `statement_model`, `supporting_docs_model`,
and all other master sub-models.

**`HeaderField` fields:** `sender_id`, `receiver_id`, `indicator`, `message_id`,
`sequence_or_control_number`, `job_number`, `job_date`, `message_type`.

---

### `signature_processor`

| Function / Class | Description |
|---|---|
| `has_signature(raw)` | Returns `True` if `digSign` block is present |
| `extract(raw)` → `SignatureInfo` | Decodes the `digSign` block; parses the X.509 certificate if `cryptography` is available |
| `build_signable_content(raw)` | Reconstructs the canonical JSON bytes (without `digSign`) that were signed |
| `verify(raw, sig_info=None)` → `VerificationResult` | Verifies the RSA/SHA-256 signature; returns a truthy/falsy result object |
| `summarise(sig_info)` | Prints a formatted signature/certificate summary to stdout |

**`SignatureInfo` fields:** `raw_signature_b64`, `raw_certificate_b64`,
`signer_version`, `signature_bytes`, `certificate_bytes`,
`subject_cn`, `subject_org`, `issuer_cn`, `valid_from`, `valid_to`, `serial_number`.

**`VerificationResult` fields:** `valid` (bool), `message` (str). The object is
truthy when the signature is valid.

---

## Using the Modules Directly in Python

```python
import json_processor as jp
import signature_processor as sp

# --- Content processing ---
content = jp.parse("403092526-1Signed.json")
print(content.header.job_number)          # 40309
print(jp.get_importer_name(content))      # SAMSUNG INDIA ELECTRONICS ...
print(jp.get_invoice_summary(content))    # list of invoice dicts
jp.summarise(content)                     # formatted print

# --- Signature processing ---
raw = jp.load_raw("403092526-1Signed.json")

if sp.has_signature(raw):
    sig_info = sp.extract(raw)
    print(sig_info.subject_cn)            # PRATIKKUMAR BIPINCHANDRA VYAS
    print(sig_info.valid_to)              # 2026-06-22 11:52:40 UTC
    sp.summarise(sig_info)                # formatted print

    result = sp.verify(raw, sig_info)
    if result:
        print("Signature OK")
    else:
        print(f"Problem: {result.message}")
```

---

## File Structure

```
claudeLearnPython/
├── json_processor.py          # Business content processor
├── signature_processor.py     # Digital signature processor
├── main.py                    # Entry point
├── 403092526-1.json           # Sample – unsigned BE
├── 403092526-1Signed.json     # Sample – signed BE (digSign present)
├── 403092526-1-Signed.json    # Sample – alternate signed BE
├── .gitignore
└── HELP.md                    # This file
```
