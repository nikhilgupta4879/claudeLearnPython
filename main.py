"""
main.py
-------
Entry point demonstrating the use of json_processor and signature_processor
to separately handle BE JSON content and its digital signature.

Usage:
    python main.py                          # uses bundled sample files
    python main.py 403092526-1Signed.json  # specific signed file
    python main.py 403092526-1.json        # unsigned file (no signature section)
"""

import sys
from pathlib import Path

import json_processor as jp
import signature_processor as sp


def run(file_path: Path) -> None:
    print(f"\nProcessing file: {file_path.name}\n")

    # ------------------------------------------------------------------
    # 1. Load raw JSON (needed by both processors)
    # ------------------------------------------------------------------
    raw = jp.load_raw(file_path)

    # ------------------------------------------------------------------
    # 2. Process JSON content (business data only)
    # ------------------------------------------------------------------
    content = jp.parse(file_path)
    jp.summarise(content)

    # ------------------------------------------------------------------
    # 3. Process digital signature (completely separate concern)
    # ------------------------------------------------------------------
    if sp.has_signature(raw):
        print("\nDigital signature found – processing separately…\n")
        sig_info = sp.extract(raw)
        sp.summarise(sig_info)

        result = sp.verify(raw, sig_info)
        print(f"\nSignature verification: {result}\n")
    else:
        print("\nNo digital signature found in this file.\n")


def main() -> None:
    here = Path(__file__).parent

    if len(sys.argv) > 1:
        files = [Path(sys.argv[1])]
        # Allow bare filename relative to script directory
        files = [here / f if not f.is_absolute() else f for f in files]
    else:
        # Demo: process both an unsigned and a signed file
        files = [
            here / "403092526-1.json",        # unsigned
            here / "403092526-1Signed.json",   # signed
        ]

    for fp in files:
        if not fp.exists():
            print(f"File not found: {fp}")
            continue
        run(fp)


if __name__ == "__main__":
    main()
