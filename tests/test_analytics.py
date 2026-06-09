"""Unit tests for the analytics layer (rejections + operations).

Strategy: build tiny hand-crafted DataFrames where the correct answer is
obvious by inspection, then assert the functions compute it. This is more
reliable than testing against generated data, whose numbers shift.
"""

from __future__ import annotations

import pandas as pd
import pytest

from mirai_analytics.analytics import operations as ops
from mirai_analytics.analytics import rejections as rej


@pytest.fixture
def small_claims() -> pd.DataFrame:
    """Six claims with known properties:
    - 4 insurer (2 SHA, 2 Jubilee), 2 cash
    - SHA: 1 rejected of 2 (50%); Jubilee: 0 rejected of 2 (0%)
    - 1 rejected claim worth 10000
    """
    return pd.DataFrame(
        {
            "claim_id": ["C1", "C2", "C3", "C4", "C5", "C6"],
            "encounter_id": ["E1", "E2", "E3", "E4", "E5", "E6"],
            "patient_id": ["P1", "P2", "P3", "P4", "P5", "P6"],
            "payer": ["SHA", "SHA", "Jubilee", "Jubilee", "Cash", "Cash"],
            "total_amount_kes": [10000.0, 5000.0, 3000.0, 4000.0, 2000.0, 1000.0],
            "status": ["rejected", "paid", "paid", "approved", "paid", "paid"],
            "rejection_reason_code": ["LATE-003", None, None, None, None, None],
        }
    )


def test_insurer_claims_excludes_cash(small_claims: pd.DataFrame) -> None:
    """Cash claims must be excluded from insurer analysis."""
    ins = rej.insurer_claims(small_claims)
    assert len(ins) == 4
    assert "Cash" not in ins["payer"].values


def test_rejection_summary(small_claims: pd.DataFrame) -> None:
    """1 rejected of 4 insurer claims = 25%, KES 10000 at risk."""
    summary = rej.rejection_summary(small_claims)
    assert summary["total_insurer_claims"] == 4.0
    assert summary["rejected_claims"] == 1.0
    assert summary["rejection_rate"] == 0.25
    assert summary["value_at_risk_kes"] == 10000.0


def test_rejection_rate_by_payer(small_claims: pd.DataFrame) -> None:
    """SHA 50% rejection, Jubilee 0%; SHA sorted first (worst)."""
    result = rej.rejection_rate_by_payer(small_claims)
    sha_row = result[result["payer"] == "SHA"].iloc[0]
    jub_row = result[result["payer"] == "Jubilee"].iloc[0]
    assert sha_row["rejection_rate"] == 0.5
    assert jub_row["rejection_rate"] == 0.0
    assert result.iloc[0]["payer"] == "SHA"  # worst first


def test_top_rejection_reasons(small_claims: pd.DataFrame) -> None:
    """Only one rejection, reason LATE-003, so it's 100% share."""
    result = rej.top_rejection_reasons(small_claims)
    assert result.iloc[0]["rejection_reason_code"] == "LATE-003"
    assert result.iloc[0]["count"] == 1
    assert result.iloc[0]["share"] == 1.0


def test_empty_claims_does_not_crash() -> None:
    """An empty insurer set should yield rate 0, not divide-by-zero."""
    empty = pd.DataFrame(
        {
            "claim_id": [],
            "encounter_id": [],
            "patient_id": [],
            "payer": [],
            "total_amount_kes": [],
            "status": [],
            "rejection_reason_code": [],
        }
    )
    summary = rej.rejection_summary(empty)
    assert summary["rejection_rate"] == 0.0
    assert summary["value_at_risk_kes"] == 0.0


# ─────────────────────────────────────────────────────────
# Operations tests
# ─────────────────────────────────────────────────────────


@pytest.fixture
def small_encounters() -> pd.DataFrame:
    """Five encounters across 4 patients:
    - P1 has 2 encounters (1 outpatient, 1 inpatient)
    - 3 outpatient/emergency, 2 inpatient/day_case
    - one encounter has no diagnosis (the inpatient one)
    """
    return pd.DataFrame(
        {
            "encounter_id": ["E1", "E2", "E3", "E4", "E5"],
            "patient_id": ["P1", "P1", "P2", "P3", "P4"],
            "encounter_type": ["outpatient", "inpatient", "outpatient", "day_case", "emergency"],
            "ward": ["OPD", "Medical Ward A", "Casualty", "Surgical Ward", "OPD"],
            "primary_diagnosis_code": ["B54", None, "B54", "S72.0", "A09"],
        }
    )


def test_volume_summary(small_encounters: pd.DataFrame) -> None:
    """4 unique patients, 5 encounters, 2 IP (inpatient+day_case), 3 OP."""
    v = ops.volume_summary(small_encounters)
    assert v["unique_patients"] == 4.0
    assert v["total_encounters"] == 5.0
    assert v["inpatient_encounters"] == 2.0
    assert v["outpatient_encounters"] == 3.0


def test_encounters_by_clinic_merges_casualty_into_opd(
    small_encounters: pd.DataFrame,
) -> None:
    """OPD and Casualty collapse to one row: E1, E3, E5 = 3 encounters."""
    result = ops.encounters_by_clinic(small_encounters)
    opd_row = result[result["ward"] == "OPD"].iloc[0]
    assert opd_row["encounters"] == 3
    assert "Casualty" not in result["ward"].values


def test_revenue_by_category_join(small_encounters: pd.DataFrame) -> None:
    """Join claims to encounters; sum billed and collected per type."""
    claims = pd.DataFrame(
        {
            "claim_id": ["C1", "C2"],
            "encounter_id": ["E1", "E2"],  # E1 outpatient, E2 inpatient
            "total_amount_kes": [1000.0, 8000.0],
            "paid_amount_kes": [1000.0, 4000.0],
        }
    )
    result = ops.revenue_by_category(claims, small_encounters)
    ip_row = result[result["encounter_type"] == "inpatient"].iloc[0]
    assert ip_row["billed_kes"] == 8000.0
    assert ip_row["collected_kes"] == 4000.0
    assert ip_row["shortfall_kes"] == 4000.0
    assert ip_row["collection_rate"] == 0.5


def test_top_conditions_excludes_missing_diagnosis(
    small_encounters: pd.DataFrame,
) -> None:
    """Inpatient setting = inpatient + day_case. E2 has no dx (excluded),
    E4 (day_case) has S72.0. So only S72.0 appears."""
    result = ops.top_conditions(small_encounters, setting="inpatient")
    assert "S72.0" in result["diagnosis_code"].values
    # E2's missing diagnosis must not appear
    assert len(result) == 1


def test_top_conditions_outpatient(small_encounters: pd.DataFrame) -> None:
    """Outpatient setting = outpatient + emergency. B54 (E1, E3) and A09 (E5).
    B54 appears twice so it ranks first."""
    result = ops.top_conditions(small_encounters, setting="outpatient")
    assert result.iloc[0]["diagnosis_code"] == "B54"
    assert result.iloc[0]["encounters"] == 2


def test_patient_demographics() -> None:
    """Known ages and sexes produce correct bands and counts."""
    patients = pd.DataFrame(
        {
            "patient_id": ["P1", "P2", "P3", "P4"],
            "sex": ["female", "female", "male", "female"],
            "date_of_birth": pd.to_datetime(
                [
                    "2023-01-01",  # ~under_5
                    "2010-01-01",  # ~5_17
                    "1990-01-01",  # ~18_40
                    "1950-01-01",  # ~60_plus
                ]
            ),
        }
    )
    demo = ops.patient_demographics(patients)
    by_sex = demo["by_sex"]
    female_count = by_sex[by_sex["sex"] == "female"]["patients"].iloc[0]
    assert female_count == 3
    # age bands present and summing to 4
    assert demo["by_age"]["patients"].sum() == 4
