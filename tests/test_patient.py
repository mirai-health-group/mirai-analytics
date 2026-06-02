"""Unit tests for the Patient Model
Covers: happy paths, boundary conditions, invalid input rejection, optional field handling and whitespace normalization
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from mirai_analytics.models.patient import Patient, Sex


@pytest.fixture
def valid_patient_data() -> dict:
    """ "A dictionary of valid Patient field values, usable as a baseline

    Tests can use this as-is for happy-path tests, or override single fields to test specific edge cases (e.g., to test an invalid date of birth, pass {**valid_patient_data, "date_of_birth": "bad"}).
    """
    return {
        "patient_id": "BEATA-WANJIRU",
        "first_name": "Beata",
        "last_name": "Kamuti",
        "date_of_birth": date(1990, 5, 15),
        "sex": "female",
    }


def test_valid_patient_constructs_successfully(valid_patient_data: dict) -> None:
    """ "The simplest possible success case: valid data produces a Patient."""
    patient = Patient(**valid_patient_data)

    assert patient.patient_id == "BEATA-WANJIRU"
    assert patient.first_name == "Beata"
    assert patient.last_name == "Kamuti"
    assert patient.date_of_birth == date(1990, 5, 15)
    assert patient.sex == Sex.FEMALE
    assert patient.national_id is None
    assert patient.phone_number is None


# ─────────────────────────────────────────────────────────
# National ID — boundary conditions and rejection
# ─────────────────────────────────────────────────────────


def test_national_id_with_seven_digits_is_valid(valid_patient_data: dict) -> None:
    """The minimum valid Kenyan ID length is 7 digits."""
    patient = Patient(**valid_patient_data, national_id="1234567")
    assert patient.national_id == "1234567"


def test_national_id_with_eight_digits_is_valid(valid_patient_data: dict) -> None:
    """The maximum valid Kenyan ID length is 8 digits."""
    patient = Patient(**valid_patient_data, national_id="12345678")
    assert patient.national_id == "12345678"


def test_national_id_with_six_digits_is_rejected(valid_patient_data: dict) -> None:
    """6-digit IDs are below the Kenyan minimum and must be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Patient(**valid_patient_data, national_id="123456")
    assert "national_id" in str(exc_info.value)


def test_national_id_with_leading_zero_is_rejected(valid_patient_data: dict) -> None:
    """Kenyan IDs never have a leading zero."""
    with pytest.raises(ValidationError) as exc_info:
        Patient(**valid_patient_data, national_id="01234567")
    assert "national_id" in str(exc_info.value)


def test_national_id_with_letters_is_rejected(valid_patient_data: dict) -> None:
    """Kenyan IDs are digits only — letters must be rejected."""
    with pytest.raises(ValidationError):
        Patient(**valid_patient_data, national_id="ABC1234")


# ─────────────────────────────────────────────────────────
# Date of birth — bounds checking
# ─────────────────────────────────────────────────────────


def test_dob_today_is_valid(valid_patient_data: dict) -> None:
    """A newborn recorded same-day is a real case."""
    patient = Patient(**{**valid_patient_data, "date_of_birth": date.today()})
    assert patient.date_of_birth == date.today()


def test_dob_in_the_future_is_rejected(valid_patient_data: dict) -> None:
    """You cannot be born tomorrow."""
    tomorrow = date.today() + timedelta(days=1)
    with pytest.raises(ValidationError) as exc_info:
        Patient(**{**valid_patient_data, "date_of_birth": tomorrow})
    assert "date_of_birth" in str(exc_info.value)


def test_dob_over_120_years_ago_is_rejected(valid_patient_data: dict) -> None:
    """No verified human has lived past 122; >120 years ago is a data entry error."""
    too_old = date.today() - timedelta(days=121 * 365)
    with pytest.raises(ValidationError) as exc_info:
        Patient(**{**valid_patient_data, "date_of_birth": too_old})
    assert "date_of_birth" in str(exc_info.value)


def test_dob_as_iso_string_is_coerced_to_date(valid_patient_data: dict) -> None:
    """Pydantic coerces ISO-format date strings to date objects automatically."""
    data = {**valid_patient_data, "date_of_birth": "1985-03-22"}
    patient = Patient(**data)
    assert patient.date_of_birth == date(1985, 3, 22)


# ─────────────────────────────────────────────────────────
# Sex — enum validation
# ─────────────────────────────────────────────────────────


def test_sex_male_is_valid(valid_patient_data: dict) -> None:
    """The string 'male' is accepted and converted to Sex.MALE."""
    patient = Patient(**{**valid_patient_data, "sex": "male"})
    assert patient.sex == Sex.MALE


def test_sex_other_is_valid(valid_patient_data: dict) -> None:
    """The 'other' category is supported for intersex and decline-to-state."""
    patient = Patient(**{**valid_patient_data, "sex": "other"})
    assert patient.sex == Sex.OTHER


def test_sex_unknown_value_is_rejected(valid_patient_data: dict) -> None:
    """Values outside the Sex enum must be rejected — no 'unknown', no 'M'."""
    with pytest.raises(ValidationError) as exc_info:
        Patient(**{**valid_patient_data, "sex": "unknown"})
    assert "sex" in str(exc_info.value)


# ─────────────────────────────────────────────────────────
# Names — whitespace normalization and rejection
# ─────────────────────────────────────────────────────────


def test_first_name_whitespace_is_stripped(valid_patient_data: dict) -> None:
    """Leading/trailing whitespace in names is auto-stripped (model_config)."""
    patient = Patient(**{**valid_patient_data, "first_name": "  Wanjiru  "})
    assert patient.first_name == "Wanjiru"


def test_empty_first_name_is_rejected(valid_patient_data: dict) -> None:
    """Empty strings are not valid names."""
    with pytest.raises(ValidationError):
        Patient(**{**valid_patient_data, "first_name": ""})


def test_whitespace_only_first_name_is_rejected(valid_patient_data: dict) -> None:
    """A name that's only whitespace is rejected (becomes empty after strip)."""
    with pytest.raises(ValidationError):
        Patient(**{**valid_patient_data, "first_name": "   "})


def test_last_name_whitespace_is_stripped(valid_patient_data: dict) -> None:
    """The same stripping applies to last_name."""
    patient = Patient(**{**valid_patient_data, "last_name": "  Kamau  "})
    assert patient.last_name == "Kamau"


# ─────────────────────────────────────────────────────────
# Phone number — optional + Kenyan format
# ─────────────────────────────────────────────────────────


def test_valid_kenyan_phone_number_is_accepted(valid_patient_data: dict) -> None:
    """E.164 Kenyan mobile (+254 followed by 7-prefix) is accepted."""
    patient = Patient(**valid_patient_data, phone_number="+254712345678")
    assert patient.phone_number == "+254712345678"


def test_phone_number_with_one_prefix_is_accepted(valid_patient_data: dict) -> None:
    """Newer Kenyan mobile numbers start with 1 instead of 7."""
    patient = Patient(**valid_patient_data, phone_number="+254101234567")
    assert patient.phone_number == "+254101234567"


def test_phone_number_without_country_code_is_rejected(valid_patient_data: dict) -> None:
    """Local format (0712...) is not E.164 — must be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Patient(**valid_patient_data, phone_number="0712345678")
    assert "phone_number" in str(exc_info.value)


def test_phone_number_with_wrong_country_code_is_rejected(valid_patient_data: dict) -> None:
    """A non-Kenyan number is rejected — we are intentionally Kenya-only."""
    with pytest.raises(ValidationError):
        Patient(**valid_patient_data, phone_number="+15551234567")
