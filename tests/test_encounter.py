"""Unit tests for the Encounter model.

Covers: happy paths, required-field enforcement, enum validation,
date bounds (single-field and cross-field), optional field handling,
and ICD-10 format validation.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from mirai_analytics.models.encounter import Encounter, EncounterType

# ─────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────


@pytest.fixture
def valid_encounter_data() -> dict:
    """A dictionary of valid Encounter field values, usable as a baseline.

    Includes only required fields; optional fields are omitted so tests
    can confirm they default to None.
    """
    return {
        "encounter_id": "ENC-001",
        "patient_id": "MIRAI-001",
        "encounter_type": "outpatient",
        "admission_date": date(2026, 5, 15),
    }


# ─────────────────────────────────────────────────────────
# Happy path — valid input produces valid Encounter
# ─────────────────────────────────────────────────────────


def test_valid_encounter_constructs_successfully(valid_encounter_data: dict) -> None:
    """Required fields produce a valid Encounter; optional fields default to None."""
    encounter = Encounter(**valid_encounter_data)

    assert encounter.encounter_id == "ENC-001"
    assert encounter.patient_id == "MIRAI-001"
    assert encounter.encounter_type == EncounterType.OUTPATIENT
    assert encounter.admission_date == date(2026, 5, 15)
    assert encounter.discharge_date is None
    assert encounter.ward is None
    assert encounter.attending_clinician_id is None
    assert encounter.primary_diagnosis_code is None


# ─────────────────────────────────────────────────────────
# Required fields — missing data is rejected
# ─────────────────────────────────────────────────────────


def test_missing_encounter_id_is_rejected(valid_encounter_data: dict) -> None:
    """encounter_id is required."""
    data = {k: v for k, v in valid_encounter_data.items() if k != "encounter_id"}
    with pytest.raises(ValidationError) as exc_info:
        Encounter(**data)
    assert "encounter_id" in str(exc_info.value)


def test_missing_patient_id_is_rejected(valid_encounter_data: dict) -> None:
    """patient_id is required — Encounter cannot exist without a patient."""
    data = {k: v for k, v in valid_encounter_data.items() if k != "patient_id"}
    with pytest.raises(ValidationError) as exc_info:
        Encounter(**data)
    assert "patient_id" in str(exc_info.value)


def test_missing_encounter_type_is_rejected(valid_encounter_data: dict) -> None:
    """encounter_type is required."""
    data = {k: v for k, v in valid_encounter_data.items() if k != "encounter_type"}
    with pytest.raises(ValidationError) as exc_info:
        Encounter(**data)
    assert "encounter_type" in str(exc_info.value)


def test_missing_admission_date_is_rejected(valid_encounter_data: dict) -> None:
    """admission_date is required."""
    data = {k: v for k, v in valid_encounter_data.items() if k != "admission_date"}
    with pytest.raises(ValidationError) as exc_info:
        Encounter(**data)
    assert "admission_date" in str(exc_info.value)


# ─────────────────────────────────────────────────────────
# EncounterType enum — valid values accepted, invalid rejected
# ─────────────────────────────────────────────────────────


def test_inpatient_encounter_type_is_valid(valid_encounter_data: dict) -> None:
    """'inpatient' is a valid encounter type."""
    encounter = Encounter(**{**valid_encounter_data, "encounter_type": "inpatient"})
    assert encounter.encounter_type == EncounterType.INPATIENT


def test_day_case_encounter_type_is_valid(valid_encounter_data: dict) -> None:
    """'day_case' is a valid encounter type."""
    encounter = Encounter(**{**valid_encounter_data, "encounter_type": "day_case"})
    assert encounter.encounter_type == EncounterType.DAY_CASE


def test_emergency_encounter_type_is_valid(valid_encounter_data: dict) -> None:
    """'emergency' is a valid encounter type."""
    encounter = Encounter(**{**valid_encounter_data, "encounter_type": "emergency"})
    assert encounter.encounter_type == EncounterType.EMERGENCY


def test_unknown_encounter_type_is_rejected(valid_encounter_data: dict) -> None:
    """Values outside the EncounterType enum are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Encounter(**{**valid_encounter_data, "encounter_type": "consultation"})
    assert "encounter_type" in str(exc_info.value)


# ─────────────────────────────────────────────────────────
# Date validation — admission and discharge bounds
# ─────────────────────────────────────────────────────────


def test_admission_today_is_valid(valid_encounter_data: dict) -> None:
    """Today's admission is normal — patients are admitted same-day all the time."""
    encounter = Encounter(**{**valid_encounter_data, "admission_date": date.today()})
    assert encounter.admission_date == date.today()


def test_admission_in_the_future_is_rejected(valid_encounter_data: dict) -> None:
    """You cannot be admitted tomorrow."""
    tomorrow = date.today() + timedelta(days=1)
    with pytest.raises(ValidationError) as exc_info:
        Encounter(**{**valid_encounter_data, "admission_date": tomorrow})
    assert "admission_date" in str(exc_info.value)


def test_admission_as_iso_string_is_coerced_to_date(valid_encounter_data: dict) -> None:
    """ISO-format date strings are coerced to date objects (CSV ingestion path)."""
    encounter = Encounter(**{**valid_encounter_data, "admission_date": "2025-12-25"})
    assert encounter.admission_date == date(2025, 12, 25)


def test_discharge_in_the_future_is_rejected(valid_encounter_data: dict) -> None:
    """Discharge cannot be in the future."""
    tomorrow = date.today() + timedelta(days=1)
    with pytest.raises(ValidationError) as exc_info:
        Encounter(**{**valid_encounter_data, "discharge_date": tomorrow})
    assert "discharge_date" in str(exc_info.value)


# ─────────────────────────────────────────────────────────
# Cross-field validation — discharge must be on/after admission
# ─────────────────────────────────────────────────────────


def test_discharge_after_admission_is_valid(valid_encounter_data: dict) -> None:
    """Discharge 5 days after admission is a normal inpatient stay."""
    encounter = Encounter(
        **valid_encounter_data,
        discharge_date=date(2026, 5, 20),  # 5 days after admission
    )
    assert encounter.discharge_date == date(2026, 5, 20)


def test_discharge_same_day_as_admission_is_valid(valid_encounter_data: dict) -> None:
    """Same-day discharge is valid — day cases and quick outpatient visits."""
    encounter = Encounter(
        **valid_encounter_data,
        discharge_date=date(2026, 5, 15),  # same day as admission
    )
    assert encounter.discharge_date == date(2026, 5, 15)


def test_discharge_before_admission_is_rejected(valid_encounter_data: dict) -> None:
    """A discharge before admission is a data error — must be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Encounter(
            **valid_encounter_data,
            discharge_date=date(2026, 5, 10),  # 5 days BEFORE admission
        )
    error_text = str(exc_info.value)
    assert "discharge_date" in error_text
    assert "admission_date" in error_text


def test_discharge_none_is_valid_for_active_admission(valid_encounter_data: dict) -> None:
    """A patient currently admitted has discharge_date=None — must be valid."""
    encounter = Encounter(**valid_encounter_data, discharge_date=None)
    assert encounter.discharge_date is None


# ─────────────────────────────────────────────────────────
# Optional fields — work when omitted and when explicitly set
# ─────────────────────────────────────────────────────────


def test_ward_can_be_provided(valid_encounter_data: dict) -> None:
    """Ward is optional but accepted as free-text when present."""
    encounter = Encounter(**valid_encounter_data, ward="Maternity A")
    assert encounter.ward == "Maternity A"


def test_attending_clinician_id_can_be_provided(valid_encounter_data: dict) -> None:
    """Attending clinician ID is optional but accepted when present."""
    encounter = Encounter(**valid_encounter_data, attending_clinician_id="CL-042")
    assert encounter.attending_clinician_id == "CL-042"


# ─────────────────────────────────────────────────────────
# ICD-10 format validation
# ─────────────────────────────────────────────────────────


def test_icd10_three_character_code_is_valid(valid_encounter_data: dict) -> None:
    """Codes without a subcategory (e.g., A09) are valid ICD-10."""
    encounter = Encounter(**valid_encounter_data, primary_diagnosis_code="A09")
    assert encounter.primary_diagnosis_code == "A09"


def test_icd10_code_with_subcategory_is_valid(valid_encounter_data: dict) -> None:
    """Codes with subcategory (e.g., J18.9) are valid ICD-10."""
    encounter = Encounter(**valid_encounter_data, primary_diagnosis_code="J18.9")
    assert encounter.primary_diagnosis_code == "J18.9"


def test_icd10_code_with_four_digit_subcategory_is_valid(valid_encounter_data: dict) -> None:
    """Codes with longer subcategories (e.g., Z34.91) are valid ICD-10."""
    encounter = Encounter(**valid_encounter_data, primary_diagnosis_code="Z34.91")
    assert encounter.primary_diagnosis_code == "Z34.91"


def test_icd10_lowercase_letter_is_rejected(valid_encounter_data: dict) -> None:
    """ICD-10 chapter letter must be uppercase."""
    with pytest.raises(ValidationError) as exc_info:
        Encounter(**valid_encounter_data, primary_diagnosis_code="j18.9")
    assert "primary_diagnosis_code" in str(exc_info.value)


def test_icd10_missing_letter_is_rejected(valid_encounter_data: dict) -> None:
    """ICD-10 codes must start with a letter."""
    with pytest.raises(ValidationError) as exc_info:
        Encounter(**valid_encounter_data, primary_diagnosis_code="123")
    assert "primary_diagnosis_code" in str(exc_info.value)


def test_icd10_wrong_digit_count_is_rejected(valid_encounter_data: dict) -> None:
    """ICD-10 needs exactly two digits after the letter."""
    with pytest.raises(ValidationError) as exc_info:
        Encounter(**valid_encounter_data, primary_diagnosis_code="A9")
    assert "primary_diagnosis_code" in str(exc_info.value)
