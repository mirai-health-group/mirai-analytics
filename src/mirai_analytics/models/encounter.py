"""Encounter model — a single patient interaction with the hospital.

Every Encounter belongs to one Patient (referenced by patient_id) and
represents one episode of care: outpatient consult, inpatient admission,
day case procedure, or emergency visit. Most analytics in Mirai Analytics
operate at the encounter level (rejection prediction, length-of-stay,
readmission risk all hang off Encounter).
"""

from __future__ import annotations

import re
from datetime import date
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EncounterType(str, Enum):
    """The four categories of patient encounter in Kenyan hospitals."""

    OUTPATIENT = "outpatient"
    INPATIENT = "inpatient"
    DAY_CASE = "day_case"
    EMERGENCY = "emergency"


class Encounter(BaseModel):
    """A single episode of patient care at a Kenyan hospital.

    Encounters link to Patient via patient_id. They are the unit at which
    most clinical and operational analytics operate — claim submission,
    length-of-stay, readmission, and discharge planning all hang off
    individual encounters.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        frozen=True,
        extra="forbid",
    )

    encounter_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=64,
            description="Internal hospital encounter identifier. Unique per hospital.",
        ),
    ]
    patient_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=64,
            description="Foreign key to Patient. Must match an existing Patient.patient_id.",
        ),
    ]
    encounter_type: Annotated[
        EncounterType,
        Field(
            description="The category of encounter: outpatient, inpatient, day case, or emergency.",
        ),
    ]
    admission_date: Annotated[
        date,
        Field(
            description="When the encounter started. Must not be in the future.",
        ),
    ]

    @field_validator("admission_date")
    @classmethod
    def validate_admission_not_in_future(cls, v: date) -> date:
        """Admission cannot be in the future."""
        if v > date.today():
            raise ValueError(
                f"admission_date must not be in the future (got {v}, today is {date.today()})"
            )
        return v

    discharge_date: Annotated[
        date | None,
        Field(
            default=None,
            description="When the encounter ended. None means the patient is still admitted.",
        ),
    ]

    @field_validator("discharge_date")
    @classmethod
    def validate_discharge_not_in_future(cls, v: date | None) -> date | None:
        """Discharge cannot be in the future. None is valid (still admitted)."""
        if v is None:
            return v
        if v > date.today():
            raise ValueError(
                f"discharge_date must not be in the future (got {v}, today is {date.today()})"
            )
        return v

    @model_validator(mode="after")
    def validate_discharge_after_admission(self) -> Encounter:
        """If discharge_date is set, it cannot be before admission_date.

        This is a cross-field validation — depends on both admission_date
        and discharge_date being set, so it runs at the model level after
        all field-level validation has passed.
        """
        if self.discharge_date is not None and self.discharge_date < self.admission_date:
            raise ValueError(
                f"discharge_date ({self.discharge_date}) must be on or after "
                f"admission_date ({self.admission_date})"
            )
        return self

    ward: Annotated[
        str | None,
        Field(
            default=None,
            max_length=100,
            description="Physical ward location (free-text for now, normalized later).",
        ),
    ]
    attending_clinician_id: Annotated[
        str | None,
        Field(
            default=None,
            max_length=64,
            description="Identifier for the clinician primarily responsible. Optional.",
        ),
    ]
    primary_diagnosis_code: Annotated[
        str | None,
        Field(
            default=None,
            description="Primary ICD-10 diagnosis code (e.g., J18.9, O80.0). Optional in v1.",
        ),
    ]

    @field_validator("primary_diagnosis_code")
    @classmethod
    def validate_icd10_format(cls, v: str | None) -> str | None:
        """ICD-10 format: one letter, two digits, optional dot and 1-4 more digits.

        Examples of valid: A09, J18.9, O80.0, Z34.91
        Does not check that the code exists in the ICD-10 catalog —
        that lives in a separate normalizer module (Month 2).
        """
        if v is None:
            return v
        if not re.fullmatch(r"[A-Z]\d{2}(\.\d{1,4})?", v):
            raise ValueError(
                "primary_diagnosis_code must be valid ICD-10 format: "
                "one uppercase letter, two digits, optional dot and 1-4 more digits "
                "(e.g., 'J18.9', 'A09', 'O80.0')"
            )
        return v
