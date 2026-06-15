"""Load synthetic CSV data into the Postgres database.

Tables are loaded in dependency order (patients → encounters → claims)
so that foreign-key constraints are satisfied.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

# Container runs on host port 5433 (5432 is taken by a native Postgres)
DB_URL = "postgresql+psycopg://postgres:mirai_dev_pw@localhost:5433/mirai"

# (table name, csv file, date columns to parse) — in load order
TABLES = [
    ("patients", "patients.csv", ["date_of_birth"]),
    ("encounters", "encounters.csv", ["admission_date", "discharge_date"]),
    ("claims", "claims.csv", ["submission_date"]),
]


def load_all(data_dir: str = "data/raw") -> None:
    """Read the three CSVs and load them into Postgres, in FK order."""
    engine = create_engine(DB_URL)
    data_path = Path(data_dir)

    for table, filename, date_cols in TABLES:
        df = pd.read_csv(data_path / filename, parse_dates=date_cols)
        # append into the existing (schema-defined) tables; don't let
        # pandas recreate them, so our constraints stay intact
        df.to_sql(table, engine, if_exists="append", index=False)
        print(f"Loaded {len(df):,} rows into '{table}'")

    # Confirm row counts straight from the database
    with engine.connect() as conn:
        for table, _, _ in TABLES:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            print(f"  {table}: {count:,} rows in database")


if __name__ == "__main__":
    load_all()
