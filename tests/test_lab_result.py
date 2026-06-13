"""Unit tests for the LabResult model."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from mirai_analytics.models.lab_result import (
    LabResult,
    LabResultStatus,
    ResultFlag,
)


def make(**overrides: Any) -> LabResult:
    fields: dict[str, Any] = {
        "result_id": "L1",
        "encounter_id": "E1",
        "patient_id": "P1",
        "test_name": "Hemoglobin",
        "collected_date": date(2025, 8, 1),
        "status": "final",
        "value_numeric": Decimal("12.5"),
        "unit": "g/dL",
    }
    fields.update(overrides)
    return LabResult(**fields)


def test_numeric_result_ok() -> None:
    assert make().value_numeric == Decimal("12.5")


def test_qualitative_result_ok() -> None:
    r = make(test_name="Malaria RDT", value_numeric=None, value_text="Positive", unit=None)
    assert r.value_text == "Positive"


def test_final_without_value_rejected() -> None:
    with pytest.raises(ValidationError):
        make(value_numeric=None, value_text=None)


def test_pending_without_value_ok() -> None:
    r = make(status="pending", value_numeric=None, value_text=None, unit=None)
    assert r.status == LabResultStatus.PENDING


def test_future_collected_rejected() -> None:
    with pytest.raises(ValidationError):
        make(collected_date=date.today() + timedelta(days=2))


def test_result_before_collected_rejected() -> None:
    with pytest.raises(ValidationError):
        make(collected_date=date(2025, 8, 5), result_date=date(2025, 8, 1))


def test_result_after_collected_ok() -> None:
    r = make(collected_date=date(2025, 8, 1), result_date=date(2025, 8, 3))
    assert r.result_date == date(2025, 8, 3)


def test_bad_loinc_rejected() -> None:
    with pytest.raises(ValidationError):
        make(loinc_code="ABC")


def test_good_loinc_ok() -> None:
    assert make(loinc_code="718-7").loinc_code == "718-7"


def test_flag_enum() -> None:
    assert make(result_flag="high").result_flag == ResultFlag.HIGH


def test_extra_field_forbidden() -> None:
    with pytest.raises(ValidationError):
        make(foo="bar")


def test_frozen() -> None:
    r = make()
    with pytest.raises(ValidationError):
        r.test_name = "x"
