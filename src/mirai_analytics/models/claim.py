"""Claim model — an insurance claim submitted for a single encounter.

Every Claim references one Encounter (the service being billed) and one
Patient (denormalized for analytics convenience). The claim lifecycle —
submission, approval/rejection, payment — is tracked via the status field
and is the core subject of Mirai Analytics' rejection-prediction model.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Payer(str, Enum):
    """Major Kenyan healthcare payers, plus Cash and Other catch-alls."""

    SHA = "SHA"
    JUBILEE = "Jubilee"
    AAR = "AAR"
    BRITAM = "Britam"
    CIC = "CIC"
    MADISON = "Madison"
    OLD_MUTUAL = "Old_Mutual"
    APA = "APA"
    CASH = "Cash"
    OTHER = "Other"


class ClaimStatus(str, Enum):
    """The lifecycle states a claim moves through."""

    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    PARTIALLY_APPROVED = "partially_approved"
    PAID = "paid"
    PENDING = "pending"


class Claim(BaseModel):
    """An insurance claim submitted by a hospital for one encounter.

    Claims are the unit at which most financial analytics operate —
    rejection rates, payment delays, per-payer performance, revenue
    leakage all hang off the Claim model.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        frozen=True,
        extra="forbid",
    )

    claim_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=64,
            description="Internal hospital claim identifier. Unique per hospital.",
        ),
    ]
    encounter_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=64,
            description="Foreign key to Encounter — the service being claimed.",
        ),
    ]
    patient_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=64,
            description="Foreign key to Patient. Denormalized for analytics convenience.",
        ),
    ]
    payer: Annotated[
        Payer,
        Field(
            description="The insurer or payer being billed.",
        ),
    ]
    total_amount_kes: Annotated[
        Decimal,
        Field(
            gt=0,
            decimal_places=2,
            description="Total amount being claimed, in Kenyan shillings. Must be positive.",
        ),
    ]
    submission_date: Annotated[
        date,
        Field(
            description="When the claim was submitted to the payer. Must not be in the future.",
        ),
    ]
    status: Annotated[
        ClaimStatus,
        Field(
            description="Current lifecycle state of the claim.",
        ),
    ]
    rejection_reason_code: Annotated[
        str | None,
        Field(
            default=None,
            max_length=32,
            description="Standardized rejection code, if status is rejected or partially_approved.",
        ),
    ]
    paid_amount_kes: Annotated[
        Decimal | None,
        Field(
            default=None,
            ge=0,
            decimal_places=2,
            description="Amount actually paid by the payer. None if not yet paid.",
        ),
    ]

    @field_validator("submission_date")
    @classmethod
    def validate_submission_not_in_future(cls, v: date) -> date:
        """Submission cannot be in the future."""
        if v > date.today():
            raise ValueError(
                f"submission_date must not be in the future (got {v}, today is {date.today()})"
            )
        return v

    @field_validator("rejection_reason_code")
    @classmethod
    def validate_rejection_reason_code_format(cls, v: str | None) -> str | None:
        """Rejection reason codes follow a LETTER(S)-DIGITS pattern (e.g., 'R-001', 'MED-12').

        Format-only validation — does not check that the code is a known
        rejection reason. Catalog lookup lives in the ingestion layer.
        """
        if v is None:
            return v
        if not re.fullmatch(r"[A-Z]+-\d+", v):
            raise ValueError(
                "rejection_reason_code must be uppercase letters, a dash, then digits "
                "(e.g., 'R-001', 'MED-12')"
            )
        return v

    @model_validator(mode="after")
    def validate_paid_does_not_exceed_total(self) -> Claim:
        """paid_amount_kes cannot exceed total_amount_kes.

        Cross-field rule — depends on both fields being set. None for
        paid_amount_kes means 'not yet paid' and is always valid.
        """
        if self.paid_amount_kes is not None and self.paid_amount_kes > self.total_amount_kes:
            raise ValueError(
                f"paid_amount_kes ({self.paid_amount_kes}) cannot exceed "
                f"total_amount_kes ({self.total_amount_kes})"
            )
        return self
