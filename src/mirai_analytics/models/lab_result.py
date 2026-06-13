"""LabResult model — a single laboratory test result."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LabResultStatus(str, Enum):
    PENDING = "pending"
    FINAL = "final"
    CORRECTED = "corrected"
    CANCELLED = "cancelled"


class ResultFlag(str, Enum):
    NORMAL = "normal"
    LOW = "low"
    HIGH = "high"
    CRITICAL = "critical"
    ABNORMAL = "abnormal"


class LabResult(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, frozen=True, extra="forbid")

    result_id: Annotated[str, Field(min_length=1, max_length=64)]
    encounter_id: Annotated[str, Field(min_length=1, max_length=64)]
    patient_id: Annotated[str, Field(min_length=1, max_length=64)]
    test_name: Annotated[str, Field(min_length=1, max_length=200)]
    loinc_code: Annotated[str | None, Field(default=None, max_length=16)]
    specimen_type: Annotated[str | None, Field(default=None, max_length=100)]
    value_numeric: Annotated[Decimal | None, Field(default=None)]
    value_text: Annotated[str | None, Field(default=None, max_length=500)]
    unit: Annotated[str | None, Field(default=None, max_length=50)]
    reference_range: Annotated[str | None, Field(default=None, max_length=100)]
    result_flag: Annotated[ResultFlag | None, Field(default=None)]
    collected_date: Annotated[date, Field()]
    result_date: Annotated[date | None, Field(default=None)]
    status: Annotated[LabResultStatus, Field()]

    @field_validator("collected_date")
    @classmethod
    def validate_collected_not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("collected_date must not be in the future")
        return v

    @field_validator("result_date")
    @classmethod
    def validate_result_not_future(cls, v: date | None) -> date | None:
        if v is not None and v > date.today():
            raise ValueError("result_date must not be in the future")
        return v

    @field_validator("loinc_code")
    @classmethod
    def validate_loinc(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not re.fullmatch(r"\d{1,7}-\d", v):
            raise ValueError("loinc_code must look like 718-7")
        return v

    @model_validator(mode="after")
    def validate_dates_and_value(self) -> LabResult:
        if self.result_date is not None and self.result_date < self.collected_date:
            raise ValueError("result_date must be on or after collected_date")
        if self.status in (LabResultStatus.FINAL, LabResultStatus.CORRECTED):
            if self.value_numeric is None and self.value_text is None:
                raise ValueError("a final/corrected result needs a numeric or text value")
        return self
