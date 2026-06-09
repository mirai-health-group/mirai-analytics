"""Claims rejection analysis — Mirai's wedge product.

Each function takes a claims DataFrame and returns a computed result.
Pure functions: same input, same output, no side effects. Easy to test,
easy to reuse, easy to wire into a dashboard.

Note on scope: cash claims are self-pay and are never "rejected" by an
insurer, so rejection analysis is computed over insurer claims only
(payer != "Cash"). This matches how hospitals actually report rejection
rates.
"""

from __future__ import annotations

import pandas as pd

REJECTED_STATUS = "rejected"
CASH_PAYER = "Cash"


def insurer_claims(claims: pd.DataFrame) -> pd.DataFrame:
    """Filter to insurer claims only (exclude self-pay cash)."""
    return claims[claims["payer"] != CASH_PAYER].copy()


def rejection_summary(claims: pd.DataFrame) -> dict[str, float]:
    """Headline numbers: total insurer claims, rejected count, rate, value at risk."""
    ins = insurer_claims(claims)
    total = len(ins)
    rejected = ins[ins["status"] == REJECTED_STATUS]
    n_rejected = len(rejected)
    rate = (n_rejected / total) if total else 0.0
    value_at_risk = float(rejected["total_amount_kes"].sum())
    return {
        "total_insurer_claims": float(total),
        "rejected_claims": float(n_rejected),
        "rejection_rate": round(rate, 4),
        "value_at_risk_kes": round(value_at_risk, 2),
    }


def rejection_rate_by_payer(claims: pd.DataFrame) -> pd.DataFrame:
    """Rejection rate and value at risk per payer, worst first."""
    ins = insurer_claims(claims)
    grouped = ins.groupby("payer", observed=True).agg(
        total_claims=("claim_id", "count"),
        rejected_claims=("status", lambda s: (s == REJECTED_STATUS).sum()),
        total_value_kes=("total_amount_kes", "sum"),
    )
    grouped["rejection_rate"] = grouped["rejected_claims"] / grouped["total_claims"]
    # value at risk = value of rejected claims for that payer
    rejected_value = (
        ins[ins["status"] == REJECTED_STATUS]
        .groupby("payer", observed=True)["total_amount_kes"]
        .sum()
    )
    grouped["value_at_risk_kes"] = rejected_value
    grouped["value_at_risk_kes"] = grouped["value_at_risk_kes"].fillna(0.0)
    grouped = grouped.sort_values("rejection_rate", ascending=False)
    return grouped.reset_index()


def top_rejection_reasons(claims: pd.DataFrame) -> pd.DataFrame:
    """Count and share of each rejection reason code, most common first."""
    ins = insurer_claims(claims)
    rejected = ins[ins["status"] == REJECTED_STATUS]
    counts = (
        rejected["rejection_reason_code"]
        .value_counts()
        .rename_axis("rejection_reason_code")
        .reset_index(name="count")
    )
    total = counts["count"].sum()
    counts["share"] = (counts["count"] / total).round(4) if total else 0.0
    return counts


def revenue_at_risk_by_payer(claims: pd.DataFrame) -> pd.DataFrame:
    """Total KES tied up in rejected claims, by payer, largest first."""
    ins = insurer_claims(claims)
    rejected = ins[ins["status"] == REJECTED_STATUS]
    out = (
        rejected.groupby("payer", observed=True)["total_amount_kes"]
        .agg(["sum", "count"])
        .rename(columns={"sum": "value_at_risk_kes", "count": "rejected_claims"})
        .sort_values("value_at_risk_kes", ascending=False)
        .reset_index()
    )
    out["value_at_risk_kes"] = out["value_at_risk_kes"].round(2)
    return out
