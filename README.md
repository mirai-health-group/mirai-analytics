# Mirai Analytics

A healthcare data activation platform for African Hospitals.

Mirai Analytics ingests data from hospital management information systems and surfaces analytics, predictions, and clinical NLP-driven insights. The platform sits between existing hospital systems and the people who need to act on the data.

## Status

Early development. v0.1.0 — foundations and data layer.

## Stack

- Python 3.11
- Pydantic for data validation
- Pandas and NumPy for analytics
- pytest for testing
- Ruff and Black for linting and formatting
- Mypy for type checking
- Pre-commit for automated quality checks

## Local development

```bash
git clone https://github.com/mirai-health-group/mirai-analytics.git
cd mirai-analytics
py -3.11 -m venv .venv
source .venv/Scripts/activate  # Windows Git Bash
pip install --upgrade pip
pip install -e ".[dev]"
pre-commit install
pytest
```

## Project structure

- `src/mirai_analytics/` — package source code
  - `models/` — Pydantic data models
  - `data/` — synthetic data generators and ingestion
- `tests/` — unit and integration tests
- `notebooks/` — Jupyter notebooks for exploration
- `sql/` — analyst SQL queries
- `docs/` — documentation

## License

Proprietary. All rights reserved.
