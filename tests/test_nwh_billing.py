"""Unit tests for the de-identifying NWH billing loader.

The most important test here is the privacy guard: we build a fake Excel
that DELIBERATELY contains identifier columns (NAME1, MRN, MEMBERSHIPNO),
run it through the loader, and assert those columns never appear in the
output. Uses synthetic fake data only — never the real file.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from mirai_analytics.ingest.nwh_billing import (
    assert_no_identifiers,
    load_nwh_billing,
)


@pytest.fixture
def fake_excel(tmp_path: Path) -> str:
    """Write a tiny fake NWH-shaped Excel, including identifier columns."""
    df = pd.DataFrame(
        {
            "CENTER_NAME": ["Test Branch", "Test Branch"],
            "CREDITCOMPANY1": ["SHA", "JUBILEE INSURANCE"],
            "CATEGORY": ["SHA", "INSURANCES"],
            "INVOICE_NO": ["INV001", "INV002"],
            "OP/IP": ["O", "I"],
            "MCC": [None, None],
            "DATE": pd.to_datetime(["2025-08-01", "2025-08-02"]),
            "MRN": ["MRN-AAA", "MRN-BBB"],  # identifier — must be dropped
            "NAME1": ["Jane Test", "John Test"],  # identifier — must be dropped
            "ADMISSION_DATE": pd.to_datetime(["2025-08-01", "2025-08-02"]),
            "CREDITCOMPANY": ["SHA", "JUBILEE INSURANCE"],
            "SCHEME2": ["Scheme A", "Scheme B"],
            "MEMBERSHIPNO": [111111, 222222],  # identifier — must be dropped
            "AGE": [30, 45],
            "INVOICE_AMOUNT": [1500.0, 23000.0],
        }
    )
    path = tmp_path / "fake_billing.xlsx"
    df.to_excel(path, sheet_name="Insurances Workings", index=False)
    return str(path)


def test_loads_rows(fake_excel: str) -> None:
    df = load_nwh_billing(fake_excel)
    assert len(df) == 2


def test_no_identifier_columns(fake_excel: str) -> None:
    """The privacy guard: name, MRN, membership number must not survive."""
    df = load_nwh_billing(fake_excel)
    cols = set(df.columns)
    assert "NAME1" not in cols
    assert "MRN" not in cols
    assert "MEMBERSHIPNO" not in cols
    # and no renamed echo of them either
    for col in df.columns:
        assert "name" not in col.lower() or col == "branch"
        assert "mrn" not in col.lower()


def test_assert_no_identifiers_passes_on_clean(fake_excel: str) -> None:
    df = load_nwh_billing(fake_excel)
    assert_no_identifiers(df)  # should not raise


def test_assert_no_identifiers_raises_on_dirty() -> None:
    """If a frame somehow has an identifier column, the guard must catch it."""
    dirty = pd.DataFrame({"NAME1": ["x"], "branch": ["y"]})
    with pytest.raises(ValueError):
        assert_no_identifiers(dirty)


def test_setting_normalised(fake_excel: str) -> None:
    df = load_nwh_billing(fake_excel)
    assert set(df["setting"]) <= {"outpatient", "inpatient"}


def test_expected_columns_present(fake_excel: str) -> None:
    df = load_nwh_billing(fake_excel)
    for col in ["branch", "payer", "category", "setting", "age", "invoice_amount_kes"]:
        assert col in df.columns
