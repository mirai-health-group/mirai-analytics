"""Synthetic data generator for Mirai Analytics.

Produces realistic CSV files shaped like a Kenyan hospital's HMIS export
(Afya Pro / Funsoft / Sanitas style): patients, encounters, and claims that
reference each other the way real hospital data does.

Design principles:
  - Output is CSV, not in-memory objects — mirrors the Stage 1 ingestion
    architecture where hospitals hand us file exports.
  - Every generated record is validated through its Pydantic model, so the
    generator and the models validate each other.
  - Deliberate, realistic signal is planted (payer-specific rejection rates,
    late-submission penalties) so downstream analytics surface real structure.
  - Seeded for reproducibility — same seed produces identical data.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from mirai_analytics.models.claim import Claim, ClaimStatus, Payer
from mirai_analytics.models.encounter import Encounter, EncounterType
from mirai_analytics.models.patient import Patient, Sex

# ─────────────────────────────────────────────────────────
# REFERENCE DATA — clinical knowledge encoded as weights
# ─────────────────────────────────────────────────────────

FIRST_NAMES_MALE = [
    "Brian",
    "Kevin",
    "Dennis",
    "Samuel",
    "Daniel",
    "Joseph",
    "Peter",
    "James",
    "John",
    "David",
    "Michael",
    "Anthony",
    "Stephen",
    "Patrick",
    "George",
    "Victor",
    "Collins",
    "Felix",
    "Eric",
    "Vincent",
    "Mwangi",
    "Otieno",
    "Kipchoge",
    "Wafula",
    "Mutua",
    "Omondi",
    "Kamau",
    "Njoroge",
    "Hassan",
    "Ali",
]
FIRST_NAMES_FEMALE = [
    "Mary",
    "Grace",
    "Faith",
    "Joyce",
    "Esther",
    "Ann",
    "Catherine",
    "Lucy",
    "Jane",
    "Susan",
    "Rose",
    "Mercy",
    "Caroline",
    "Beatrice",
    "Nancy",
    "Florence",
    "Wanjiru",
    "Akinyi",
    "Nyokabi",
    "Chebet",
    "Nafula",
    "Wanjiku",
    "Adhiambo",
    "Wairimu",
    "Khadija",
    "Amina",
    "Fatuma",
    "Halima",
    "Njeri",
    "Auma",
]
SURNAMES = [
    "Kamau",
    "Otieno",
    "Mwangi",
    "Njoroge",
    "Omondi",
    "Wafula",
    "Mutua",
    "Kiprop",
    "Cheruiyot",
    "Wanjala",
    "Maina",
    "Kariuki",
    "Ochieng",
    "Barasa",
    "Kipchoge",
    "Njuguna",
    "Onyango",
    "Mwaura",
    "Gitau",
    "Korir",
    "Wekesa",
    "Mutiso",
    "Hassan",
    "Abdi",
    "Mohamed",
    "Ndungu",
    "Karanja",
    "Owino",
    "Chebet",
    "Rotich",
]
WARDS_INPATIENT = [
    "Medical Ward A",
    "Medical Ward B",
    "Surgical Ward",
    "Maternity Ward",
    "Pediatric Ward",
    "ICU",
    "HDU",
]
WARDS_OUTPATIENT = ["OPD", "Casualty", "MCH Clinic", "CCC Clinic", "Diabetic Clinic"]

CLINICIAN_IDS = [f"CL-{i:03d}" for i in range(1, 26)]

# Your top diagnoses, ICD-10 coded, weighted by how often you actually see them
ICD10_WEIGHTED = [
    ("J06.9", 10),
    ("J18.9", 6),
    ("J02.9", 5),
    ("J03.9", 3),
    ("J04.0", 1),  # URTI ~25
    ("A09", 15),  # gastroenteritis
    ("Z34.9", 12),  # ANC
    ("B54", 12),  # malaria
    ("I10", 8),  # hypertension
    ("R51", 8),  # headache
    ("E11.9", 7),  # diabetes
    ("S72.0", 3),
    ("S06.9", 2),  # RTA trauma ~5
    ("B20", 5),  # HIV
    ("A15.9", 3),  # TB
]

# Your payer mix (AAR/Britam at 1% each so the data exercises every payer)
PAYER_WEIGHTED = [
    (Payer.SHA, 30.0),
    (Payer.JUBILEE, 10.0),
    (Payer.AAR, 1.0),
    (Payer.BRITAM, 1.0),
    (Payer.CIC, 5.0),
    (Payer.MADISON, 2.5),
    (Payer.OLD_MUTUAL, 2.5),
    (Payer.APA, 5.0),
    (Payer.CASH, 38.0),
    (Payer.OTHER, 5.0),
]

# Base rejection probability by insurer — SHA rejects most. Cash never rejects.
PAYER_BASE_REJECT = {
    Payer.SHA: 0.38,
    Payer.JUBILEE: 0.15,
    Payer.AAR: 0.16,
    Payer.BRITAM: 0.16,
    Payer.CIC: 0.18,
    Payer.MADISON: 0.19,
    Payer.OLD_MUTUAL: 0.14,
    Payer.APA: 0.18,
    Payer.OTHER: 0.22,
}

# Your encounter mix
ENCOUNTER_TYPES_WEIGHTED = [
    (EncounterType.OUTPATIENT, 80.0),
    (EncounterType.INPATIENT, 10.0),
    (EncounterType.DAY_CASE, 5.0),
    (EncounterType.EMERGENCY, 5.0),
]

# Typical claim amount (KES) by encounter type: (mean, sigma) for lognormal sampling
AMOUNT_BY_TYPE = {
    EncounterType.OUTPATIENT: (8.2, 0.6),  # median ~3,640
    EncounterType.INPATIENT: (11.0, 0.7),  # median ~59,874
    EncounterType.DAY_CASE: (10.0, 0.6),  # median ~22,026
    EncounterType.EMERGENCY: (9.5, 0.7),  # median ~13,360
}


def _weighted_choice(rng: np.random.Generator, items_weights: Any) -> Any:
    """Pick one item from a list of (item, weight) pairs, proportional to weight."""
    items = [iw[0] for iw in items_weights]
    weights = np.array([iw[1] for iw in items_weights], dtype=float)
    weights = weights / weights.sum()
    idx = rng.choice(len(items), p=weights)
    return items[idx]


# ─────────────────────────────────────────────────────────
# PATIENT GENERATOR
# ─────────────────────────────────────────────────────────

AGE_BANDS = [
    ((0, 5), 0.25),
    ((6, 17), 0.15),
    ((18, 40), 0.35),
    ((41, 60), 0.15),
    ((61, 90), 0.10),
]


def _random_dob(rng: np.random.Generator) -> tuple[date, int]:
    """Pick a birth date from the bimodal age distribution. Returns (dob, age)."""
    bands = [b[0] for b in AGE_BANDS]
    probs = np.array([b[1] for b in AGE_BANDS])
    probs = probs / probs.sum()
    band_idx = rng.choice(len(bands), p=probs)
    lo, hi = bands[band_idx]
    age = int(rng.integers(lo, hi + 1))
    today = date.today()
    days = age * 365 + int(rng.integers(0, 365))
    dob = today - timedelta(days=days)
    return dob, age


def _random_national_id(rng: np.random.Generator) -> str:
    """7 or 8 digits, no leading zero — matches Patient model regex."""
    length = int(rng.choice([7, 8], p=[0.4, 0.6]))
    first = str(int(rng.integers(1, 10)))
    rest = "".join(str(int(rng.integers(0, 10))) for _ in range(length - 1))
    return first + rest


def _random_phone(rng: np.random.Generator) -> str:
    """Kenyan E.164 mobile: +254 then 7 or 1 then 8 digits."""
    prefix = rng.choice(["7", "1"], p=[0.85, 0.15])
    rest = "".join(str(int(rng.integers(0, 10))) for _ in range(8))
    return f"+254{prefix}{rest}"


def generate_patients(n: int, rng: np.random.Generator) -> list[Patient]:
    """Generate n validated Patient objects with realistic distributions."""
    patients = []
    for i in range(n):
        sex = _weighted_choice(rng, [(Sex.FEMALE, 52.0), (Sex.MALE, 47.5), (Sex.OTHER, 0.5)])
        if sex == Sex.MALE:
            first = rng.choice(FIRST_NAMES_MALE)
        elif sex == Sex.FEMALE:
            first = rng.choice(FIRST_NAMES_FEMALE)
        else:
            first = rng.choice(FIRST_NAMES_MALE + FIRST_NAMES_FEMALE)
        last = rng.choice(SURNAMES)
        dob, age = _random_dob(rng)

        national_id = None
        if age >= 18 and rng.random() < 0.95:
            national_id = _random_national_id(rng)

        phone = None
        if age >= 18 and rng.random() < 0.80:
            phone = _random_phone(rng)

        patients.append(
            Patient(
                patient_id=f"MIRAI-P{i + 1:06d}",
                national_id=national_id,
                first_name=str(first),
                last_name=str(last),
                date_of_birth=dob,
                sex=sex,
                phone_number=phone,
            )
        )
    return patients


# ─────────────────────────────────────────────────────────
# ENCOUNTER GENERATOR
# ─────────────────────────────────────────────────────────


def generate_encounters(
    patients: list[Patient], rng: np.random.Generator, window_days: int = 365
) -> list[Encounter]:
    """For each patient, generate 1+ encounters with realistic types and dates."""
    encounters = []
    counter = 0
    today = date.today()
    for patient in patients:
        n_enc = 1 + int(rng.poisson(0.7))  # most have 1-2, some more
        for _ in range(n_enc):
            counter += 1
            etype = _weighted_choice(rng, ENCOUNTER_TYPES_WEIGHTED)
            days_ago = int(rng.integers(0, window_days))
            admission = today - timedelta(days=days_ago)

            discharge = None
            ward = None
            if etype in (EncounterType.INPATIENT, EncounterType.DAY_CASE):
                if etype == EncounterType.DAY_CASE:
                    los = 0
                else:
                    los = max(1, int(rng.lognormal(1.2, 0.6)))  # median ~3-4 days
                discharge = min(admission + timedelta(days=los), today)
                ward = str(rng.choice(WARDS_INPATIENT))
            else:
                ward = str(rng.choice(WARDS_OUTPATIENT))

            # ~8% missing diagnosis — deliberately, to drive rejections later
            dx = None
            if rng.random() > 0.08:
                dx = _weighted_choice(rng, ICD10_WEIGHTED)

            encounters.append(
                Encounter(
                    encounter_id=f"MIRAI-E{counter:07d}",
                    patient_id=patient.patient_id,
                    encounter_type=etype,
                    admission_date=admission,
                    discharge_date=discharge,
                    ward=ward,
                    attending_clinician_id=str(rng.choice(CLINICIAN_IDS)),
                    primary_diagnosis_code=dx,
                )
            )
    return encounters


# ─────────────────────────────────────────────────────────
# CLAIM GENERATOR
# ─────────────────────────────────────────────────────────

REASON_CODES = {
    "missing_docs": "MISSDOC-001",
    "missing_dx": "MISSDX-002",
    "late": "LATE-003",
    "etims": "ETIMS-004",
    "preauth": "PREAUTH-005",
}


def _money(amount: float) -> Decimal:
    """Round to 2 decimal places as a Decimal, floor at 1.00."""
    return Decimal(str(round(max(amount, 1.0), 2)))


def generate_claims(encounters: list[Encounter], rng: np.random.Generator) -> list[Claim]:
    """Generate claims with planted rejection signal tied to real causes."""
    claims = []
    counter = 0
    today = date.today()
    for enc in encounters:
        if rng.random() > 0.75:  # ~75% of encounters generate a claim
            continue
        counter += 1

        payer = _weighted_choice(rng, PAYER_WEIGHTED)
        mean, sigma = AMOUNT_BY_TYPE[enc.encounter_type]
        total = _money(float(rng.lognormal(mean, sigma)))

        lag = int(rng.integers(0, 50))
        submission = min(enc.admission_date + timedelta(days=lag), today)

        is_late = lag > 30
        missing_dx = enc.primary_diagnosis_code is None
        high_amount = total > Decimal("50000")

        rejection_reason = None
        paid = None

        if payer == Payer.CASH:
            if rng.random() < 0.85:
                status = ClaimStatus.PAID
                paid = total
            else:
                status = ClaimStatus.PENDING
                paid = None
        else:
            p_reject = PAYER_BASE_REJECT[payer]
            if is_late:
                p_reject += 0.15
            if missing_dx:
                p_reject += 0.20
            if high_amount:
                p_reject += 0.12
            p_reject = min(max(p_reject, 0.02), 0.95)

            if rng.random() < p_reject:
                status = ClaimStatus.REJECTED
                paid = Decimal("0.00")
                if missing_dx:
                    rejection_reason = REASON_CODES["missing_dx"]
                elif is_late:
                    rejection_reason = REASON_CODES["late"]
                elif high_amount:
                    rejection_reason = REASON_CODES["preauth"]
                else:
                    rejection_reason = rng.choice(
                        [
                            REASON_CODES["missing_docs"],
                            REASON_CODES["etims"],
                        ]
                    )
            else:
                roll = rng.random()
                if roll < 0.15:
                    status = ClaimStatus.PARTIALLY_APPROVED
                    paid = _money(float(total) * float(rng.uniform(0.4, 0.9)))
                elif roll < 0.55:
                    status = ClaimStatus.PAID
                    paid = total
                elif roll < 0.8:
                    status = ClaimStatus.APPROVED
                    paid = total
                else:
                    status = ClaimStatus.SUBMITTED
                    paid = None

        claims.append(
            Claim(
                claim_id=f"MIRAI-C{counter:07d}",
                encounter_id=enc.encounter_id,
                patient_id=enc.patient_id,
                payer=payer,
                total_amount_kes=total,
                submission_date=submission,
                status=status,
                rejection_reason_code=str(rejection_reason) if rejection_reason else None,
                paid_amount_kes=paid,
            )
        )
    return claims


# ─────────────────────────────────────────────────────────
# ORCHESTRATION
# ─────────────────────────────────────────────────────────


def generate_dataset(
    n_patients: int = 1000, seed: int = 42, output_dir: str = "data/raw"
) -> dict[str, object]:
    """Generate a full linked dataset and write patients/encounters/claims CSVs."""
    rng = np.random.default_rng(seed)

    patients = generate_patients(n_patients, rng)
    encounters = generate_encounters(patients, rng)
    claims = generate_claims(encounters, rng)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    pd.DataFrame([p.model_dump() for p in patients]).to_csv(out / "patients.csv", index=False)
    pd.DataFrame([e.model_dump() for e in encounters]).to_csv(out / "encounters.csv", index=False)
    pd.DataFrame([c.model_dump() for c in claims]).to_csv(out / "claims.csv", index=False)

    return {
        "patients": len(patients),
        "encounters": len(encounters),
        "claims": len(claims),
        "output_dir": str(out.resolve()),
    }


if __name__ == "__main__":
    counts = generate_dataset(n_patients=1000, seed=42)
    print("Generated:", counts)
