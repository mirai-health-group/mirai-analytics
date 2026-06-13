"""Prescription model — a single medication order.

Route is a constrained enum (clean, finite); frequency is free text
because real dosing instructions are messy ("BD", "TDS", "PRN",
"every 6 hours"). Optional ATC code is the WHO drug-classification
equivalent of ICD-10 for diagnoses.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MedicationRoute(str, Enum):
    ORAL = "oral"
    IV = "iv"
    IM = "im"
    SUBCUTANEOUS = "subcutaneous"
    TOPICAL = "topical"
    INHALED = "inhaled"
    RECTAL = "rectal"
    OPHTHALMIC = "ophthalmic"
    OTHER = "other"


class PrescriptionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ON_HOLD = "on_hold"


class Prescription(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, frozen=True, extra="forbid")

    prescription_id: Annotated[str, Field(min_length=1, max_length=64)]
    encounter_id: Annotated[str, Field(min_length=1, max_length=64)]
    patient_id: Annotated[str, Field(min_length=1, max_length=64)]
    drug_name: Annotated[str, Field(min_length=1, max_length=200)]
    atc_code: Annotated[str | None, Field(default=None, max_length=8)]
    dose: Annotated[Decimal | None, Field(default=None, gt=0)]
    dose_unit: Annotated[str | None, Field(default=None, max_length=20)]
    route: Annotated[MedicationRoute | None, Field(default=None)]
    frequency: Annotated[str | None, Field(default=None, max_length=50)]
    duration_days: Annotated[int | None, Field(default=None, gt=0)]
    quantity: Annotated[Decimal | None, Field(default=None, gt=0)]
    prescribed_date: Annotated[date, Field()]
    prescriber_id: Annotated[str | None, Field(default=None, max_length=64)]
    status: Annotated[PrescriptionStatus, Field()]

    @field_validator("prescribed_date")
    @classmethod
    def validate_prescribed_not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("prescribed_date must not be in the future")
        return v

    @field_validator("atc_code")
    @classmethod
    def validate_atc(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not re.fullmatch(r"[A-Z]\d{2}[A-Z]{2}\d{2}", v):
            raise ValueError("atc_code must look like J01CA04")
        return v
