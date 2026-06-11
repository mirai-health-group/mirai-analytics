"""Mirai Analytics — hospital insights dashboard.

A thin visual layer over the tested analytics functions. Contains no
analytics logic itself — it loads data, calls functions from the analytics
package, and renders the results.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import plotly.express as px
import streamlit as st

from mirai_analytics.analytics import operations as ops
from mirai_analytics.analytics import rejections as rej
from mirai_analytics.analytics.loaders import (
    load_claims,
    load_encounters,
    load_patients,
)

# ─────────────────────────────────────────────────────────
# Brand palette
# ─────────────────────────────────────────────────────────
GREEN = "#29AB87"
GREEN_LIGHT = "#A7D9C6"
GREEN_PALE = "#5FC9A6"
TEXT = "#E8F3EE"
GREENS_SEQ = ["#29AB87", "#5FC9A6", "#8FDCC2", "#1F8868", "#155F49", "#A7D9C6"]

st.set_page_config(page_title="Mirai Analytics", page_icon="🌿", layout="wide")


# ─────────────────────────────────────────────────────────
# Chart styling helper — makes plotly figures sit on dark green
# ─────────────────────────────────────────────────────────
def style_fig(fig: Any, height: int = 360) -> Any:
    """Transparent background, light text, brand-consistent layout."""
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": TEXT, "family": "sans-serif", "size": 13},
        margin={"l": 10, "r": 10, "t": 30, "b": 10},
        legend={"bgcolor": "rgba(0,0,0,0)"},
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.08)", zeroline=False)
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.08)", zeroline=False)
    return fig


# ─────────────────────────────────────────────────────────
# Custom CSS — tighten spacing, style metric tiles
# ─────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    [data-testid="stMetric"] {
        background-color: #13362B;
        border: 1px solid #1F8868;
        border-radius: 12px;
        padding: 16px 18px;
    }
    [data-testid="stMetricLabel"] { color: #A7D9C6; }
    [data-testid="stMetricValue"] { color: #FFFFFF; }
    h1, h2, h3 { letter-spacing: 0.3px; }
    .block-container { padding-top: 2rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────
# Data loading (cached)
# ─────────────────────────────────────────────────────────
@st.cache_data
def get_data():
    """Load all three datasets, generating them first if missing.

    On a fresh deploy the gitignored CSVs don't exist, so we generate
    them once from a fixed seed. Reproducible, and keeps generated data
    out of the repo.
    """
    if not Path("data/raw/claims.csv").exists():
        from mirai_analytics.data.synthetic import generate_dataset

        generate_dataset(n_patients=1000, seed=42, output_dir="data/raw")
    return load_claims(), load_encounters(), load_patients()


claims, encounters, patients = get_data()

# ─────────────────────────────────────────────────────────
# Header — logo + title
# ─────────────────────────────────────────────────────────
logo_col, title_col = st.columns([1, 5], vertical_alignment="center")
with logo_col:
    logo_path = Path("assets/mirai_logo.png")
    if logo_path.exists():
        st.image(str(logo_path), use_container_width=True)
with title_col:
    st.title("Mirai Analytics")
    st.caption("Hospital data activation platform — demonstration on synthetic data")

st.info(
    "This dashboard runs on **synthetic data** that mirrors a Kenyan "
    "hospital's HMIS export. No real patient records are used.",
    icon="ℹ️",
)

# ─────────────────────────────────────────────────────────
# Headline metrics
# ─────────────────────────────────────────────────────────
st.header("At a glance")

summary = rej.rejection_summary(claims)
volumes = ops.volume_summary(encounters)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Unique patients", f"{int(volumes['unique_patients']):,}")
col2.metric("Total encounters", f"{int(volumes['total_encounters']):,}")
col3.metric("Insurer rejection rate", f"{summary['rejection_rate']:.1%}")
col4.metric("Revenue at risk", f"KES {summary['value_at_risk_kes']:,.0f}")

# ─────────────────────────────────────────────────────────
# Rejection analysis
# ─────────────────────────────────────────────────────────
st.header("Where claims are rejected")
st.caption("Insurer claims only — cash is self-pay and not subject to rejection.")

by_payer = rej.rejection_rate_by_payer(claims)

left, right = st.columns([3, 2])
with left:
    st.subheader("Rejection rate by payer")
    fig = px.bar(
        by_payer,
        x="payer",
        y="rejection_rate",
        labels={"payer": "", "rejection_rate": "Rejection rate"},
        color="rejection_rate",
        color_continuous_scale=["#155F49", "#29AB87", "#8FDCC2"],
    )
    fig.update_layout(yaxis_tickformat=".0%", coloraxis_showscale=False)
    st.plotly_chart(style_fig(fig), use_container_width=True)

with right:
    st.subheader("Top rejection reasons")
    reasons = rej.top_rejection_reasons(claims)
    st.dataframe(
        reasons,
        use_container_width=True,
        hide_index=True,
        column_config={
            "rejection_reason_code": "Reason code",
            "count": "Count",
            "share": st.column_config.NumberColumn("Share", format="%.1f%%"),
        },
    )

st.subheader("Revenue at risk by payer")
revenue_risk = rej.revenue_at_risk_by_payer(claims)
st.dataframe(
    revenue_risk,
    use_container_width=True,
    hide_index=True,
    column_config={
        "payer": "Payer",
        "value_at_risk_kes": st.column_config.NumberColumn("Value at risk (KES)", format="%.0f"),
        "rejected_claims": "Rejected claims",
    },
)

# ─────────────────────────────────────────────────────────
# Operational analysis
# ─────────────────────────────────────────────────────────
st.header("Hospital operations")

op_left, op_right = st.columns(2)
with op_left:
    st.subheader("Encounters by clinic")
    by_clinic = ops.encounters_by_clinic(encounters)
    fig_clinic = px.bar(
        by_clinic,
        x="encounters",
        y="ward",
        orientation="h",
        labels={"encounters": "Encounters", "ward": ""},
        color_discrete_sequence=[GREEN],
    )
    fig_clinic.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(style_fig(fig_clinic), use_container_width=True)

with op_right:
    st.subheader("Encounters by type")
    by_type = ops.encounters_by_type(encounters)
    fig_type = px.pie(
        by_type,
        names="encounter_type",
        values="encounters",
        color_discrete_sequence=GREENS_SEQ,
        hole=0.45,
    )
    fig_type.update_traces(textposition="outside", textinfo="percent+label")
    st.plotly_chart(style_fig(fig_type), use_container_width=True)

st.subheader("Revenue by service line — billed vs collected")
revenue = ops.revenue_by_category(claims, encounters)
fig_rev = px.bar(
    revenue,
    x="encounter_type",
    y=["billed_kes", "collected_kes"],
    barmode="group",
    labels={"encounter_type": "", "value": "KES", "variable": ""},
    color_discrete_map={"billed_kes": GREEN_LIGHT, "collected_kes": GREEN},
)
st.plotly_chart(style_fig(fig_rev), use_container_width=True)

st.dataframe(
    revenue,
    use_container_width=True,
    hide_index=True,
    column_config={
        "encounter_type": "Service line",
        "claims": "Claims",
        "billed_kes": st.column_config.NumberColumn("Billed (KES)", format="%.0f"),
        "collected_kes": st.column_config.NumberColumn("Collected (KES)", format="%.0f"),
        "shortfall_kes": st.column_config.NumberColumn("Shortfall (KES)", format="%.0f"),
        "collection_rate": st.column_config.NumberColumn("Collection rate", format="%.1f%%"),
    },
)

# ─────────────────────────────────────────────────────────
# Demographics and clinical profile
# ─────────────────────────────────────────────────────────
st.header("Patients and conditions")

demo = ops.patient_demographics(patients)

demo_left, demo_right = st.columns(2)
with demo_left:
    st.subheader("Patients by sex")
    fig_sex = px.pie(
        demo["by_sex"],
        names="sex",
        values="patients",
        color_discrete_sequence=GREENS_SEQ,
        hole=0.45,
    )
    fig_sex.update_traces(textposition="outside", textinfo="percent+label")
    st.plotly_chart(style_fig(fig_sex), use_container_width=True)

with demo_right:
    st.subheader("Patients by age band")
    fig_age = px.bar(
        demo["by_age"],
        x="age_band",
        y="patients",
        labels={"age_band": "", "patients": "Patients"},
        color_discrete_sequence=[GREEN],
    )
    st.plotly_chart(style_fig(fig_age), use_container_width=True)

st.subheader("Top 10 conditions")
cond_left, cond_right = st.columns(2)
with cond_left:
    st.markdown("**Outpatient**")
    st.dataframe(
        ops.top_conditions(encounters, setting="outpatient", n=10),
        use_container_width=True,
        hide_index=True,
        column_config={"diagnosis_code": "ICD-10", "encounters": "Encounters"},
    )
with cond_right:
    st.markdown("**Inpatient**")
    st.dataframe(
        ops.top_conditions(encounters, setting="inpatient", n=10),
        use_container_width=True,
        hide_index=True,
        column_config={"diagnosis_code": "ICD-10", "encounters": "Encounters"},
    )

st.divider()
st.caption("Mirai Analytics · demonstration dashboard on synthetic data · built by Dr Jeremy Ngugi")
