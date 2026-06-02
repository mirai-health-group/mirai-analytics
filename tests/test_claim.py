"""Unit tests for the Claim model.

Covers: happy paths, required-field enforcement, Payer and ClaimStatus
enum validation, submission date bounds, Decimal positivity constraints,
rejection reason code format, optional field handling, and the cross-field
paid-vs-total rule.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from mirai_analytics.models.claim import Claim, ClaimStatus, Payer

# ─────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────


@pytest.fixture
def valid_claim_data() -> dict:
    """Baseline valid Claim data with required fields only."""
    return {
        "claim_id": "CLM-001",
        "encounter_id": "ENC-001",
        "patient_id": "MIRAI-001",
        "payer": "SHA",
        "total_amount_kes": Decimal("5000.00"),
        "submission_date": date(2026, 5, 20),
        "status": "submitted",
    }


# ─────────────────────────────────────────────────────────
# Happy path
# ─────────────────────────────────────────────────────────


def test_valid_claim_constructs_successfully(valid_claim_data: dict) -> None:
    """Required fields produce a valid Claim; optional fields default to None."""
    claim = Claim(**valid_claim_data)

    assert claim.claim_id == "CLM-001"
    assert claim.encounter_id == "ENC-001"
    assert claim.patient_id == "MIRAI-001"
    assert claim.payer == Payer.SHA
    assert claim.total_amount_kes == Decimal("5000.00")
    assert claim.submission_date == date(2026, 5, 20)
    assert claim.status == ClaimStatus.SUBMITTED
    assert claim.rejection_reason_code is None
    assert claim.paid_amount_kes is None


# ─────────────────────────────────────────────────────────
# Required fields — missing data is rejected
# ─────────────────────────────────────────────────────────


def test_missing_claim_id_is_rejected(valid_claim_data: dict) -> None:
    """claim_id is required."""
    data = {k: v for k, v in valid_claim_data.items() if k != "claim_id"}
    with pytest.raises(ValidationError) as exc_info:
        Claim(**data)
    assert "claim_id" in str(exc_info.value)


def test_missing_payer_is_rejected(valid_claim_data: dict) -> None:
    """payer is required."""
    data = {k: v for k, v in valid_claim_data.items() if k != "payer"}
    with pytest.raises(ValidationError) as exc_info:
        Claim(**data)
    assert "payer" in str(exc_info.value)


def test_missing_total_amount_is_rejected(valid_claim_data: dict) -> None:
    """total_amount_kes is required."""
    data = {k: v for k, v in valid_claim_data.items() if k != "total_amount_kes"}
    with pytest.raises(ValidationError) as exc_info:
        Claim(**data)
    assert "total_amount_kes" in str(exc_info.value)


# ─────────────────────────────────────────────────────────
# Payer enum validation
# ─────────────────────────────────────────────────────────


def test_payer_jubilee_is_valid(valid_claim_data: dict) -> None:
    """Jubilee is a major Kenyan insurer — must be accepted."""
    claim = Claim(**{**valid_claim_data, "payer": "Jubilee"})
    assert claim.payer == Payer.JUBILEE


def test_payer_cash_is_valid(valid_claim_data: dict) -> None:
    """Cash (self-pay) is a valid payer category."""
    claim = Claim(**{**valid_claim_data, "payer": "Cash"})
    assert claim.payer == Payer.CASH


def test_payer_unknown_insurer_is_rejected(valid_claim_data: dict) -> None:
    """Insurers not in the Payer enum must be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Claim(**{**valid_claim_data, "payer": "NHIF"})
    assert "payer" in str(exc_info.value)


# ─────────────────────────────────────────────────────────
# ClaimStatus enum validation
# ─────────────────────────────────────────────────────────


def test_status_approved_is_valid(valid_claim_data: dict) -> None:
    """'approved' is a valid claim status."""
    claim = Claim(**{**valid_claim_data, "status": "approved"})
    assert claim.status == ClaimStatus.APPROVED


def test_status_rejected_is_valid(valid_claim_data: dict) -> None:
    """'rejected' is a valid claim status."""
    claim = Claim(**{**valid_claim_data, "status": "rejected"})
    assert claim.status == ClaimStatus.REJECTED


def test_status_paid_is_valid(valid_claim_data: dict) -> None:
    """'paid' is a valid claim status."""
    claim = Claim(**{**valid_claim_data, "status": "paid"})
    assert claim.status == ClaimStatus.PAID


def test_status_unknown_value_is_rejected(valid_claim_data: dict) -> None:
    """Status values outside the enum are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Claim(**{**valid_claim_data, "status": "denied"})
    assert "status" in str(exc_info.value)


# ─────────────────────────────────────────────────────────
# Decimal and amount validation
# ─────────────────────────────────────────────────────────


def test_total_amount_zero_is_rejected(valid_claim_data: dict) -> None:
    """Total amount must be strictly positive — zero is not a valid claim."""
    with pytest.raises(ValidationError) as exc_info:
        Claim(**{**valid_claim_data, "total_amount_kes": Decimal("0.00")})
    assert "total_amount_kes" in str(exc_info.value)


def test_total_amount_negative_is_rejected(valid_claim_data: dict) -> None:
    """Negative amounts are never valid."""
    with pytest.raises(ValidationError) as exc_info:
        Claim(**{**valid_claim_data, "total_amount_kes": Decimal("-100.00")})
    assert "total_amount_kes" in str(exc_info.value)


def test_paid_amount_zero_is_valid(valid_claim_data: dict) -> None:
    """Paid amount of zero is valid — represents a fully rejected claim."""
    claim = Claim(**valid_claim_data, paid_amount_kes=Decimal("0.00"))
    assert claim.paid_amount_kes == Decimal("0.00")


def test_paid_amount_negative_is_rejected(valid_claim_data: dict) -> None:
    """Negative paid amount is never valid."""
    with pytest.raises(ValidationError) as exc_info:
        Claim(**valid_claim_data, paid_amount_kes=Decimal("-50.00"))
    assert "paid_amount_kes" in str(exc_info.value)


def test_total_amount_as_string_is_coerced(valid_claim_data: dict) -> None:
    """Pydantic coerces numeric strings to Decimal (CSV ingestion path)."""
    claim = Claim(**{**valid_claim_data, "total_amount_kes": "7500.00"})
    assert claim.total_amount_kes == Decimal("7500.00")


# ─────────────────────────────────────────────────────────
# Submission date
# ─────────────────────────────────────────────────────────


def test_submission_today_is_valid(valid_claim_data: dict) -> None:
    """A claim submitted today is normal."""
    claim = Claim(**{**valid_claim_data, "submission_date": date.today()})
    assert claim.submission_date == date.today()


def test_submission_in_the_future_is_rejected(valid_claim_data: dict) -> None:
    """A claim cannot be submitted tomorrow."""
    tomorrow = date.today() + timedelta(days=1)
    with pytest.raises(ValidationError) as exc_info:
        Claim(**{**valid_claim_data, "submission_date": tomorrow})
    assert "submission_date" in str(exc_info.value)


# ─────────────────────────────────────────────────────────
# Rejection reason code format
# ─────────────────────────────────────────────────────────


def test_valid_rejection_reason_code_accepted(valid_claim_data: dict) -> None:
    """Standard format: uppercase letters, dash, digits."""
    claim = Claim(**valid_claim_data, rejection_reason_code="MED-12")
    assert claim.rejection_reason_code == "MED-12"


def test_rejection_reason_code_single_letter_is_valid(valid_claim_data: dict) -> None:
    """Single-letter prefix is valid (e.g., R-001)."""
    claim = Claim(**valid_claim_data, rejection_reason_code="R-001")
    assert claim.rejection_reason_code == "R-001"


def test_rejection_reason_code_lowercase_is_rejected(valid_claim_data: dict) -> None:
    """Lowercase letters in the code are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Claim(**valid_claim_data, rejection_reason_code="med-12")
    assert "rejection_reason_code" in str(exc_info.value)


def test_rejection_reason_code_no_dash_is_rejected(valid_claim_data: dict) -> None:
    """Codes without the dash separator are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Claim(**valid_claim_data, rejection_reason_code="MED12")
    assert "rejection_reason_code" in str(exc_info.value)


# ─────────────────────────────────────────────────────────
# Cross-field — paid cannot exceed total
# ─────────────────────────────────────────────────────────


def test_paid_less_than_total_is_valid(valid_claim_data: dict) -> None:
    """Partial payment — paid less than claimed."""
    claim = Claim(**valid_claim_data, paid_amount_kes=Decimal("3000.00"))
    assert claim.paid_amount_kes == Decimal("3000.00")


def test_paid_equal_to_total_is_valid(valid_claim_data: dict) -> None:
    """Full payment — paid exactly what was claimed."""
    claim = Claim(**valid_claim_data, paid_amount_kes=Decimal("5000.00"))
    assert claim.paid_amount_kes == Decimal("5000.00")


def test_paid_exceeds_total_is_rejected(valid_claim_data: dict) -> None:
    """Overpayment is a data error — payer cannot pay more than was claimed."""
    with pytest.raises(ValidationError) as exc_info:
        Claim(**valid_claim_data, paid_amount_kes=Decimal("6000.00"))
    error_text = str(exc_info.value)
    assert "paid_amount_kes" in error_text
    assert "total_amount_kes" in error_text


def test_paid_none_is_valid_for_unpaid_claim(valid_claim_data: dict) -> None:
    """A claim not yet paid has paid_amount_kes=None — must be valid."""
    claim = Claim(**valid_claim_data, paid_amount_kes=None)
    assert claim.paid_amount_kes is None
