"""Operational and clinical analytics for hospital leadership.

Where rejections.py answers the CFO's question (where is revenue leaking),
this module answers the Medical Director and CEO: how many patients, what
mix of services, what conditions, what revenue per service line, and who
are our patients demographically.

Distinctions made deliberately:
  - "patients" (unique people) vs "encounters" (visits) — different numbers,
    both meaningful.
  - "billed" (total_amount_kes) vs "collected" (paid_amount_kes) — the gap
    is the revenue leakage rejections explain.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

INPATIENT_TYPES = ["inpatient", "day_case"]
OUTPATIENT_TYPES = ["outpatient", "emergency"]


def volume_summary(encounters: pd.DataFrame) -> dict[str, float]:
    """Headline volumes: unique patients, total encounters, IP vs OP split."""
    is_ip = encounters["encounter_type"].isin(INPATIENT_TYPES)
    return {
        "unique_patients": float(encounters["patient_id"].nunique()),
        "total_encounters": float(len(encounters)),
        "inpatient_encounters": float(is_ip.sum()),
        "outpatient_encounters": float((~is_ip).sum()),
    }


def encounters_by_type(encounters: pd.DataFrame) -> pd.DataFrame:
    """Encounter count and unique patients per encounter type."""
    out = (
        encounters.groupby("encounter_type", observed=True)
        .agg(
            encounters=("encounter_id", "count"),
            unique_patients=("patient_id", "nunique"),
        )
        .sort_values("encounters", ascending=False)
        .reset_index()
    )
    return out


def encounters_by_clinic(encounters: pd.DataFrame) -> pd.DataFrame:
    """Volume by ward/clinic, busiest first.

    OPD and Casualty are the same physical clinic, so 'Casualty' is
    normalized to 'OPD' before grouping.
    """
    df = encounters.copy()
    df["ward"] = df["ward"].replace("Casualty", "OPD")
    out = (
        df.groupby("ward", observed=True)
        .agg(
            encounters=("encounter_id", "count"),
            unique_patients=("patient_id", "nunique"),
        )
        .sort_values("encounters", ascending=False)
        .reset_index()
    )
    return out


def revenue_by_category(claims: pd.DataFrame, encounters: pd.DataFrame) -> pd.DataFrame:
    """Billed vs collected revenue per encounter type.

    Joins claims to encounters to get each claim's service category, then
    sums billed (total_amount_kes) and collected (paid_amount_kes). The gap
    is revenue leakage.
    """
    merged = claims.merge(
        encounters[["encounter_id", "encounter_type"]],
        on="encounter_id",
        how="left",
    )
    out = merged.groupby("encounter_type", observed=True).agg(
        claims=("claim_id", "count"),
        billed_kes=("total_amount_kes", "sum"),
        collected_kes=("paid_amount_kes", "sum"),
    )
    out["shortfall_kes"] = out["billed_kes"] - out["collected_kes"]
    out["collection_rate"] = (out["collected_kes"] / out["billed_kes"]).round(4)
    out = out.sort_values("billed_kes", ascending=False).reset_index()
    for col in ["billed_kes", "collected_kes", "shortfall_kes"]:
        out[col] = out[col].round(2)
    return out


def _age_band(age: int) -> str:
    if age < 5:
        return "under_5"
    if age < 18:
        return "5_17"
    if age < 41:
        return "18_40"
    if age < 61:
        return "41_60"
    return "60_plus"


def patient_demographics(patients: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Sex distribution and age-band distribution of patients."""
    by_sex = patients["sex"].value_counts().rename_axis("sex").reset_index(name="patients")

    today = pd.Timestamp(date.today())
    ages = ((today - patients["date_of_birth"]).dt.days // 365).astype(int)
    bands = ages.map(_age_band)
    band_order = ["under_5", "5_17", "18_40", "41_60", "60_plus"]
    by_age = (
        bands.value_counts()
        .reindex(band_order, fill_value=0)
        .rename_axis("age_band")
        .reset_index(name="patients")
    )
    return {"by_sex": by_sex, "by_age": by_age}


def top_conditions(
    encounters: pd.DataFrame, setting: str = "outpatient", n: int = 10
) -> pd.DataFrame:
    """Top n diagnosis codes for a setting ('outpatient' or 'inpatient').

    'inpatient' covers inpatient + day_case; 'outpatient' covers
    outpatient + emergency. Encounters with no diagnosis are excluded
    and not counted (missing-diagnosis is itself a data-quality issue).
    """
    types = INPATIENT_TYPES if setting == "inpatient" else OUTPATIENT_TYPES
    subset = encounters[encounters["encounter_type"].isin(types)]
    coded = subset[subset["primary_diagnosis_code"].notna()]
    out = (
        coded["primary_diagnosis_code"]
        .value_counts()
        .head(n)
        .rename_axis("diagnosis_code")
        .reset_index(name="encounters")
    )
    return out
