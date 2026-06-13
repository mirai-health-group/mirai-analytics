"""Unit tests for the CSV loaders.

Strategy: generate a small dataset into a temporary directory (pytest's
tmp_path fixture), then load it back and assert the loaders return clean,
correctly-typed DataFrames. This also exercises the generator's CSV writing.
"""

from __future__ import annotations

import pandas as pd
import pytest

from mirai_analytics.analytics.loaders import (
    load_claims,
    load_encounters,
    load_patients,
)
from mirai_analytics.data.synthetic import generate_dataset


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Generate a small dataset once into a temp dir, return its path."""
    d = tmp_path_factory.mktemp("raw")
    generate_dataset(n_patients=50, seed=7, output_dir=str(d))
    return str(d)


def test_load_patients_returns_dataframe(data_dir: str) -> None:
    df = load_patients(data_dir)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 50
    assert "patient_id" in df.columns


def test_load_patients_dtypes(data_dir: str) -> None:
    df = load_patients(data_dir)
    assert df["patient_id"].dtype == "string"
    # date_of_birth parsed as datetime, not object
    assert "datetime" in str(df["date_of_birth"].dtype)


def test_load_encounters_returns_dataframe(data_dir: str) -> None:
    df = load_encounters(data_dir)
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    assert "encounter_id" in df.columns
    assert "datetime" in str(df["admission_date"].dtype)


def test_load_claims_returns_dataframe(data_dir: str) -> None:
    df = load_claims(data_dir)
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    assert "claim_id" in df.columns
    assert df["total_amount_kes"].dtype == "float64"


def test_loaders_reference_same_patients(data_dir: str) -> None:
    """Every encounter's patient_id should exist in patients."""
    patients = load_patients(data_dir)
    encounters = load_encounters(data_dir)
    patient_ids = set(patients["patient_id"])
    enc_patient_ids = set(encounters["patient_id"])
    assert enc_patient_ids.issubset(patient_ids)
