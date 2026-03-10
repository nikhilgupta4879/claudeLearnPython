"""
json_processor.py
-----------------
Handles loading and extracting the business content from a BE (Bill of Entry)
JSON file.  The digital signature section (digSign) is intentionally excluded
here; see signature_processor.py for that.
"""

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class HeaderField:
    sender_id: str
    receiver_id: str
    indicator: str
    message_id: str
    sequence_or_control_number: int
    job_number: int
    job_date: str
    message_type: str


@dataclass
class BEContent:
    """Holds the parsed content sections of a Bill of Entry JSON."""
    header: HeaderField
    be_model: list[dict[str, Any]] = field(default_factory=list)
    exchange_model: list[dict[str, Any]] = field(default_factory=list)
    invoice_model: list[dict[str, Any]] = field(default_factory=list)
    items_model: list[dict[str, Any]] = field(default_factory=list)
    cert_model: list[dict[str, Any]] = field(default_factory=list)
    sbeduty_model: list[dict[str, Any]] = field(default_factory=list)
    igms_model: list[dict[str, Any]] = field(default_factory=list)
    container_model: list[dict[str, Any]] = field(default_factory=list)
    ctx_model: list[dict[str, Any]] = field(default_factory=list)
    info_type_model: list[dict[str, Any]] = field(default_factory=list)
    statement_model: list[dict[str, Any]] = field(default_factory=list)
    supporting_docs_model: list[dict[str, Any]] = field(default_factory=list)
    # Less-common sections kept as-is
    permission_model: list[dict[str, Any]] = field(default_factory=list)
    license_model: list[dict[str, Any]] = field(default_factory=list)
    rsp_model: list[dict[str, Any]] = field(default_factory=list)
    depb_model: list[dict[str, Any]] = field(default_factory=list)
    bond_model: list[dict[str, Any]] = field(default_factory=list)
    hss_model: list[dict[str, Any]] = field(default_factory=list)
    reimport_model: list[dict[str, Any]] = field(default_factory=list)
    misc_ch_model: list[dict[str, Any]] = field(default_factory=list)
    sw_const_model: list[dict[str, Any]] = field(default_factory=list)
    sw_prod_model: list[dict[str, Any]] = field(default_factory=list)
    ctrl_model: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_raw(file_path: str | Path) -> dict:
    """Read a BE JSON file and return the raw dict (including digSign if present)."""
    with open(file_path, encoding="utf-8") as fh:
        return json.load(fh)


def extract_content_json(raw: dict) -> dict:
    """Return only the content sections (headerField + master), without digSign."""
    return {k: v for k, v in raw.items() if k != "digSign"}


def parse(file_path: str | Path) -> BEContent:
    """
    Load a BE JSON file and return a structured BEContent object.
    The digSign section is ignored here.
    """
    raw = load_raw(file_path)
    hdr_raw = raw["headerField"]
    master = raw.get("master", {})

    header = HeaderField(
        sender_id=hdr_raw.get("senderID", ""),
        receiver_id=hdr_raw.get("receiverID", ""),
        indicator=hdr_raw.get("indicator", ""),
        message_id=hdr_raw.get("messageID", ""),
        sequence_or_control_number=hdr_raw.get("sequenceOrControlNumber", 0),
        job_number=hdr_raw.get("jobNumber", 0),
        job_date=hdr_raw.get("jobDate", ""),
        message_type=hdr_raw.get("messageType", ""),
    )

    return BEContent(
        header=header,
        be_model=master.get("beModel", []),
        exchange_model=master.get("exchangeModel", []),
        invoice_model=master.get("invoiceModel", []),
        items_model=master.get("itemsModel", []),
        cert_model=master.get("certModel", []),
        sbeduty_model=master.get("sbedutyModel", []),
        igms_model=master.get("igmsModel", []),
        container_model=master.get("containerModel", []),
        ctx_model=master.get("ctxModel", []),
        info_type_model=master.get("infoTypeModel", []),
        statement_model=master.get("statementModel", []),
        supporting_docs_model=master.get("supportingDocsModel", []),
        permission_model=master.get("permissionModel", []),
        license_model=master.get("licenseModel", []),
        rsp_model=master.get("rspModel", []),
        depb_model=master.get("depbModel", []),
        bond_model=master.get("bondModel", []),
        hss_model=master.get("hssModel", []),
        reimport_model=master.get("reimportModel", []),
        misc_ch_model=master.get("misc_chModel", []),
        sw_const_model=master.get("sw_ConstModel", []),
        sw_prod_model=master.get("sw_ProdModel", []),
        ctrl_model=master.get("ctrlModel", []),
    )


# ---------------------------------------------------------------------------
# Helpers – quick accessors
# ---------------------------------------------------------------------------

def get_importer_name(content: BEContent) -> str:
    """Return the importer name from beModel[0], or empty string."""
    if content.be_model:
        return content.be_model[0].get("nameOfImporter", "")
    return ""


def get_invoice_summary(content: BEContent) -> list[dict]:
    """Return a condensed view of each invoice."""
    return [
        {
            "invoiceSerialNumber": inv.get("invoiceSerialNumber"),
            "actualInvoiceNumber": inv.get("actualInvoiceNumber"),
            "invoiceDate": inv.get("invoiceDate"),
            "invoiceValue": inv.get("invoiceValue"),
            "invoiceCurrency": inv.get("invoiceCurrency"),
            "supplierName": inv.get("supplierName"),
        }
        for inv in content.invoice_model
    ]


def get_item_summary(content: BEContent) -> list[dict]:
    """Return a condensed view of each item."""
    return [
        {
            "itemSerialNumber": item.get("itemSerialNumber"),
            "ritcCode": item.get("ritcCode"),
            "description": " ".join(
                filter(None, [item.get("itemDescription1"), item.get("itemDescription2")])
            ),
            "quantity": item.get("quantity"),
            "unitQuantityCode": item.get("unitQuantityCode"),
            "unitPriceInvoiced": item.get("unitPriceInvoiced"),
            "brandName": item.get("brandName"),
            "model": item.get("model"),
            "countryOfOrigin": item.get("countryOfOrigin"),
        }
        for item in content.items_model
    ]


def summarise(content: BEContent) -> None:
    """Print a human-readable summary of the BE content."""
    h = content.header
    print("=" * 60)
    print("BILL OF ENTRY SUMMARY")
    print("=" * 60)
    print(f"  Job Number  : {h.job_number}")
    print(f"  Job Date    : {h.job_date}")
    print(f"  Sender      : {h.sender_id}")
    print(f"  Receiver    : {h.receiver_id}")
    print(f"  Message Type: {h.message_type}")
    print(f"  Importer    : {get_importer_name(content)}")
    print()

    print("  Invoices:")
    for inv in get_invoice_summary(content):
        print(
            f"    #{inv['invoiceSerialNumber']} | {inv['actualInvoiceNumber']} | "
            f"{inv['invoiceDate']} | {inv['invoiceValue']} {inv['invoiceCurrency']} | "
            f"{inv['supplierName']}"
        )

    print()
    print("  Items:")
    for itm in get_item_summary(content):
        print(
            f"    #{itm['itemSerialNumber']} | {itm['ritcCode']} | "
            f"{itm['quantity']} {itm['unitQuantityCode']} @ {itm['unitPriceInvoiced']} | "
            f"{itm['brandName']} {itm['model']} | Origin: {itm['countryOfOrigin']}"
        )
        print(f"           {itm['description']}")

    print()
    print(f"  Certificates    : {len(content.cert_model)}")
    print(f"  Supporting Docs : {len(content.supporting_docs_model)}")
    print(f"  Duty Records    : {len(content.sbeduty_model)}")
    print(f"  Containers      : {len(content.container_model)}")
    print("=" * 60)
