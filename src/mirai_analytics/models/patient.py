"""Patient model - the main entity in Mirai Analytics's data layer.
Every clinical encounter, claim, LabResult and prescription is tied to a patient.
This model defines what a valid Kenyan hospital looks like.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Sex(str, Enum):
    """Patient biological sex as recorded in hospital systems."""

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class Patient(BaseModel):
    """A patient record from a Kenyan hospital iformation system.
    Represents the minimum credible patient as captured by HMIS systems. All other entities reference patient via patient_id.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        frozen=True,
        extra="forbid",
    )

    patient_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=64,
            description="Internal hospital patient identifier. Unique per hospital.",
        ),
    ]
    national_id: Annotated[
        str | None,
        Field(
            default=None,
            description="Kenyan national ID, 7-8 digits if present. Optional for infants and foreigners.",
        ),
    ]

    @field_validator("national_id")
    @classmethod
    def validate_national_id_format(cls, v: str | None) -> str | None:
        """Kenyan IDs are 7-8 digits, no leading zero."""
        if v is None:
            return v
        if not re.fullmatch(r"[1-9][0-9]{6,7}", v):
            raise ValueError("national_id must be 7-8 digits with no leading zero")
        return v

    first_name: Annotated[
        str,
        Field(
            min_length=1,
            max_length=100,
            description="Patient's given name. Whitespace is auto-stripped.",
        ),
    ]
    last_name: Annotated[
        str,
        Field(
            min_length=1,
            max_length=100,
            description="Patient's family name. Whitespace is auto-stripped.",
        ),
    ]

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name_not_empty_after_strip(cls, v: str) -> str:
        """Reject names that are only whitespace.

        str_strip_whitespace in model_config trims leading/trailing whitespace, which can turn "  " into ''. Pydantic's min_length=1 then catches it, but this validator gives clearer error message.
        """

        if not v or v.isspace():
            raise ValueError("name must not be empty or whitespace-only")
        return v

    date_of_birth: Annotated[
        date,
        Field(description="Patient's date of birth. Must be in the past and within 120 years."),
    ]

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob_in_plausible_range(cls, v: date) -> date:
        """Date of birth must be in the past and within 120 years.
        -Future dates are rejected.
        -Dates older than 120 allmost certainly data erors.
        -Today's date is accepted.
        """
        today = date.today()
        if v > today:
            raise ValueError(f"date_of_birth must not be in the future (got {v}, today is {today})")
        oldest_plausible = today - timedelta(days=120 * 365)
        if v < oldest_plausible:
            raise ValueError(f"date_of_birth must be within the last 120 years (got{v})")
        return v

    sex: Annotated[
        Sex,
        Field(
            description="Patient sex : male, female, or other.",
        ),
    ]

    phone_number: Annotated[
        str | None,
        Field(
            default=None,
            description="Kenyan phone number in E.164 format (+254....), optional.",
        ),
    ]

    @field_validator("phone_number")
    @classmethod
    def validate_kenyam_phone(cls, v: str | None) -> str | None:
        """Kenyan numbers in E/164 format : +254 followed by 9 digits.
        Mobile numbers start with 7 or 1 after the country code.
        Examples of valid: +254799764467 or +254112233445
        """
        if v is None:
            return v
        if not re.fullmatch(r"\+254[71]\d{8}", v):
            raise ValueError(
                "phone number must be in Kenyan E/164 format: +254 followed by "
                "a 9-digit mobile number starting with 7 or 1"
            )
        return v
