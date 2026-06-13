"""Unit tests for the Prescription model."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from mirai_analytics.models.prescription import (
    MedicationRoute,
    Prescription,
    PrescriptionStatus,
)


def make(**overrides: Any) -> Prescription:
    fields: dict[str, Any] = {
        "prescription_id": "RX1",
        "encounter_id": "E1",
        "patient_id": "P1",
        "drug_name": "Amoxicillin",
        "dose": Decimal("500"),
        "dose_unit": "mg",
        "route": "oral",
        "frequency": "TDS",
        "duration_days": 5,
        "prescribed_date": date(2025, 8, 1),
        "status": "active",
    }
    fields.update(overrides)
    return Prescription(**fields)


def test_valid() -> None:
    assert make().drug_name == "Amoxicillin"


def test_minimal() -> None:
    r = make(dose=None, dose_unit=None, route=None, frequency=None, duration_days=None)
    assert r.dose is None


def test_route_enum() -> None:
    assert make().route == MedicationRoute.ORAL


def test_status_enum() -> None:
    assert make().status == PrescriptionStatus.ACTIVE


def test_future_date_rejected() -> None:
    with pytest.raises(ValidationError):
        make(prescribed_date=date.today() + timedelta(days=2))


def test_zero_dose_rejected() -> None:
    with pytest.raises(ValidationError):
        make(dose=Decimal("0"))


def test_negative_duration_rejected() -> None:
    with pytest.raises(ValidationError):
        make(duration_days=-3)


def test_zero_duration_rejected() -> None:
    with pytest.raises(ValidationError):
        make(duration_days=0)


def test_bad_atc_rejected() -> None:
    with pytest.raises(ValidationError):
        make(atc_code="XYZ")


def test_good_atc_ok() -> None:
    assert make(atc_code="J01CA04").atc_code == "J01CA04"


def test_freetext_frequency() -> None:
    assert make(frequency="every 6 hours").frequency == "every 6 hours"


def test_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        make(foo="bar")


def test_frozen() -> None:
    r = make()
    with pytest.raises(ValidationError):
        r.drug_name = "x"
