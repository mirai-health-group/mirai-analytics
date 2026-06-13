"""De-identifying loader for a Mid-sized Kenyan Hospital billing exports.

Reads the 'Insurances Workings' sheet and returns a DataFrame containing
ONLY non-identifiable analytical fields. Patient identifiers (name, MRN,
insurance membership number) are never read into the frame.

Safety principle: this is an ALLOWLIST, not a denylist. Only the columns
named in SAFE_COLUMNS are kept; anything else in the source — including any
identifier columns, present or added in future exports — is ignored by
omission. Raw exports must stay out of git (data/private/ is gitignored).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# Source column name -> clean analytical name. Allowlist only.
SAFE_COLUMNS = {
    "CENTER_NAME": "branch",
    "CREDITCOMPANY1": "payer",
    "CATEGORY": "category",
    "INVOICE_NO": "invoice_no",
    "OP/IP": "setting",
    "DATE": "invoice_date",
    "ADMISSION_DATE": "admission_date",
    "SCHEME2": "scheme",
    "AGE": "age",
    "INVOICE_AMOUNT": "invoice_amount_kes",
}

# Never loaded — listed only so a safety check can assert their absence.
IDENTIFIER_COLUMNS = ["NAME1", "MRN", "MEMBERSHIPNO"]


def load_nwh_billing(
    path: str | Path,
    sheet: str = "Insurances Workings",
) -> pd.DataFrame:
    """Load and de-identify an NWH billing export.

    Returns a DataFrame with only the allowlisted analytical columns,
    real rows only (those with an invoice number), and tidy types.
    """
    raw = pd.read_excel(path, sheet_name=sheet, usecols="A:O")

    keep = [c for c in raw.columns if c in SAFE_COLUMNS]
    df = raw[keep].rename(columns=SAFE_COLUMNS)

    # Real rows only — must carry an invoice number
    df = df[df["invoice_no"].notna()].copy()

    # Readable setting labels
    df["setting"] = df["setting"].map({"O": "outpatient", "I": "inpatient"}).fillna(df["setting"])

    # Tidy types
    df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce")
    df["admission_date"] = pd.to_datetime(df["admission_date"], errors="coerce")
    df["age"] = pd.to_numeric(df["age"], errors="coerce")
    df["invoice_amount_kes"] = pd.to_numeric(df["invoice_amount_kes"], errors="coerce")

    return df.reset_index(drop=True)


def assert_no_identifiers(df: pd.DataFrame) -> None:
    """Raise if any identifier-like column slipped into the frame."""
    leaked = [
        col for col in df.columns for ident in IDENTIFIER_COLUMNS if ident.lower() in col.lower()
    ]
    if leaked:
        raise ValueError(f"Identifier columns present: {leaked}")
