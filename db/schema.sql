-- Mirai Analytics — database schema
-- Three core tables mirroring the Pydantic models, with enforced
-- primary keys and foreign-key relationships.

DROP TABLE IF EXISTS claims;
DROP TABLE IF EXISTS encounters;
DROP TABLE IF EXISTS patients;

-- ── Patients ───────────────────────────────────────────────
CREATE TABLE patients (
    patient_id     TEXT PRIMARY KEY,
    national_id    TEXT,                       -- nullable: newborns/minors may lack one
    first_name     TEXT NOT NULL,
    last_name      TEXT NOT NULL,
    date_of_birth  DATE NOT NULL,
    sex            TEXT NOT NULL CHECK (sex IN ('male', 'female', 'other')),
    phone_number   TEXT
);

-- ── Encounters ─────────────────────────────────────────────
CREATE TABLE encounters (
    encounter_id            TEXT PRIMARY KEY,
    patient_id              TEXT NOT NULL REFERENCES patients (patient_id),
    encounter_type          TEXT NOT NULL CHECK (
                                encounter_type IN
                                ('outpatient', 'inpatient', 'day_case', 'emergency')
                            ),
    admission_date          TIMESTAMP NOT NULL,
    discharge_date          TIMESTAMP,          -- nullable: only admitted patients
    ward                    TEXT NOT NULL,
    attending_clinician_id  TEXT NOT NULL,
    primary_diagnosis_code  TEXT                -- nullable: ~8% missing-diagnosis signal
);

-- ── Claims ─────────────────────────────────────────────────
CREATE TABLE claims (
    claim_id              TEXT PRIMARY KEY,
    encounter_id          TEXT NOT NULL REFERENCES encounters (encounter_id),
    patient_id            TEXT NOT NULL REFERENCES patients (patient_id),
    payer                 TEXT NOT NULL CHECK (
                              payer IN ('SHA', 'Jubilee', 'AAR', 'Britam', 'CIC',
                                        'Madison', 'Old_Mutual', 'APA', 'Cash', 'Other')
                          ),
    total_amount_kes      NUMERIC(12, 2) NOT NULL,
    submission_date       DATE NOT NULL,
    status                TEXT NOT NULL CHECK (
                              status IN ('submitted', 'pending', 'approved',
                                         'partially_approved', 'paid', 'rejected')
                          ),
    rejection_reason_code TEXT,                  -- nullable: only rejected claims
    paid_amount_kes       NUMERIC(12, 2)         -- nullable: unpaid claims
);
