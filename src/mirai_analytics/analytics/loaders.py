"""Load hospital CSV exports into pandas DataFrames for analysis.

This is the bridge between the data layer (CSV files shaped like an HMIS
export) and the analytics layer. Loading is deliberately separate from
analysis so the same DataFrames can feed many different analyses.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_claims(data_dir: str = "data/raw") -> pd.DataFrame:
    """Load claims.csv into a DataFrame with correct dtypes.

    Parses dates as datetime and amounts as numeric so downstream
    analysis can do date math and aggregation without surprises.
    """
    path = Path(data_dir) / "claims.csv"
    df = pd.read_csv(
        path,
        parse_dates=["submission_date"],
        dtype={
            "claim_id": "string",
            "encounter_id": "string",
            "patient_id": "string",
            "payer": "string",
            "status": "string",
            "rejection_reason_code": "string",
        },
    )
    return df


def load_encounters(data_dir: str = "data/raw") -> pd.DataFrame:
    """Load encounters.csv with admission/discharge parsed as dates."""
    path = Path(data_dir) / "encounters.csv"
    df = pd.read_csv(
        path,
        parse_dates=["admission_date", "discharge_date"],
        dtype={
            "encounter_id": "string",
            "patient_id": "string",
            "encounter_type": "string",
            "ward": "string",
            "attending_clinician_id": "string",
            "primary_diagnosis_code": "string",
        },
    )
    return df


def load_patients(data_dir: str = "data/raw") -> pd.DataFrame:
    """Load patients.csv with date_of_birth parsed as a date."""
    path = Path(data_dir) / "patients.csv"
    df = pd.read_csv(
        path,
        parse_dates=["date_of_birth"],
        dtype={
            "patient_id": "string",
            "national_id": "string",
            "first_name": "string",
            "last_name": "string",
            "sex": "string",
            "phone_number": "string",
        },
    )
    return df
