"""
src/dashboard/kpi_cards.py
==========================
Top-row KPI metric cards and supply chain health progress bar.

Public API
----------
render_kpi_row(df) -> None
    Render a single row of 5 st.metric cards followed by a health-score
    progress bar.  Uses only native Streamlit components.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _month_period(ts: pd.Series) -> pd.Series:
    """Return a Period[M] series from a datetime series."""
    return pd.to_datetime(ts, errors="coerce").dt.to_period("M")


def _prev_month_count(df: pd.DataFrame) -> int | None:
    """
    Return the order count for the calendar month immediately before the
    latest month in the DataFrame.  Returns None if the timestamp column
    is absent or if there is no prior-month data.
    """
    date_col = "order_purchase_timestamp"
    if date_col not in df.columns:
        return None

    periods = _month_period(df[date_col]).dropna()
    if periods.empty:
        return None

    latest_month = periods.max()
    prev_month   = latest_month - 1

    prev_count = (periods == prev_month).sum()
    return int(prev_count) if prev_count > 0 else None


def _health_score(df: pd.DataFrame) -> float:
    """
    Compute the supply chain health score (0–100).

    Defined as: (Fresh + Good orders) / total orders × 100
    """
    n = len(df)
    if n == 0:
        return 0.0

    tier_col = (
        "freshness_tier"
        if "freshness_tier" in df.columns
        else "freshness_status"
        if "freshness_status" in df.columns
        else None
    )

    if tier_col is None:
        return 0.0

    healthy = df[tier_col].isin(["Fresh", "Good"]).sum()
    return round(healthy / n * 100, 1)


def _fmt_currency(value: float) -> str:
    """Format a float as a Brazilian Real currency string."""
    return f"R$ {value:,.2f}"


# ---------------------------------------------------------------------------
# Public: render_kpi_row
# ---------------------------------------------------------------------------

def render_kpi_row(df: pd.DataFrame) -> None:
    """
    Render a single row of 5 KPI metric cards plus a health-score progress bar.

    Cards (left → right)
    --------------------
    1. Total Orders          — with Δ vs previous calendar month
    2. % Fresh               — percentage of Fresh + Good items
    3. % Critical + Expired  — percentage of at-risk items
    4. Revenue at Risk (R$)  — sum of revenue_at_risk column
    5. Avg Delivery Delay    — mean delivery_delay_days for delivered orders

    Below the cards
    ---------------
    A labeled ``st.progress`` bar shows the health score:
    ``(Fresh + Good) / total × 100``

    Parameters
    ----------
    df : pd.DataFrame
        Filtered enriched DataFrame from
        :func:`~src.dashboard.data_loader.load_data`.
    """
    n = len(df)

    # ------------------------------------------------------------------ #
    # Pre-compute all values before rendering
    # ------------------------------------------------------------------ #

    # -- Card 1: Total Orders + delta --
    total_orders  = n
    prev_month_n  = _prev_month_count(df)
    orders_delta  = None
    if prev_month_n is not None:
        # Count current-month orders
        periods       = _month_period(df.get("order_purchase_timestamp", pd.Series(dtype="datetime64[ns]"))).dropna()
        if not periods.empty:
            current_month  = periods.max()
            current_n      = int((periods == current_month).sum())
            orders_delta   = current_n - prev_month_n

    # -- Card 2: % Fresh --
    tier_col = (
        "freshness_tier"
        if "freshness_tier" in df.columns
        else "freshness_status"
        if "freshness_status" in df.columns
        else None
    )

    pct_fresh    = 0.0
    pct_atrisk   = 0.0
    if tier_col and n > 0:
        pct_fresh  = round(df[tier_col].isin(["Fresh", "Good"]).sum() / n * 100, 1)
        pct_atrisk = round(df[tier_col].isin(["Critical", "Expired"]).sum() / n * 100, 1)

    # -- Card 4: Revenue at Risk --
    revenue_at_risk = 0.0
    if "revenue_at_risk" in df.columns:
        revenue_at_risk = float(df["revenue_at_risk"].sum())

    # -- Card 5: Avg Delivery Delay --
    avg_delay = 0.0
    delay_col = (
        "delivery_delay_days"
        if "delivery_delay_days" in df.columns
        else "delay_days"
        if "delay_days" in df.columns
        else None
    )
    if delay_col:
        status_col = "order_status" if "order_status" in df.columns else None
        if status_col:
            delivered = df[df[status_col] == "delivered"]
        else:
            delivered = df
        if len(delivered) > 0:
            avg_delay = round(float(delivered[delay_col].mean()), 1)

    # ------------------------------------------------------------------ #
    # Render KPI cards
    # ------------------------------------------------------------------ #
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        delta_str = f"{orders_delta:+,}" if orders_delta is not None else None
        st.metric(
            label="📦 Total Orders",
            value=f"{total_orders:,}",
            delta=delta_str,
            delta_color="normal",   # up = green, down = red (standard)
            help="Total number of orders in the current filter selection. "
                 "Delta shows current-month vs previous-month.",
        )

    with col2:
        st.metric(
            label="🟢 % Fresh",
            value=f"{pct_fresh}%",
            delta=None,
            help="Percentage of orders with freshness tier Fresh or Good (on-time or early delivery).",
        )

    with col3:
        # Higher at-risk % is bad → invert delta colour convention
        at_risk_delta = f"{pct_atrisk:.1f}%" if pct_atrisk > 0 else None
        st.metric(
            label="🔥 % Critical + Expired",
            value=f"{pct_atrisk}%",
            delta=at_risk_delta,
            delta_color="inverse",   # positive value shown in red (bad)
            help="Percentage of orders flagged as Critical (>14d late) or Expired (cancelled).",
        )

    with col4:
        st.metric(
            label="💰 Revenue at Risk",
            value=_fmt_currency(revenue_at_risk),
            delta=None,
            help="Sum of order value (price) for all Critical, Warning, and Expired orders.",
        )

    with col5:
        # Positive avg_delay = late = bad → use inverse colouring
        delay_delta = f"{avg_delay:+.1f} d" if avg_delay != 0 else None
        st.metric(
            label="⏱️ Avg Delivery Delay",
            value=f"{avg_delay} d",
            delta=delay_delta,
            delta_color="inverse",   # positive delay shown in red
            help="Mean delivery delay in days for delivered orders. "
                 "Negative = delivered early on average.",
        )

    # ------------------------------------------------------------------ #
    # Health score progress bar
    # ------------------------------------------------------------------ #
    st.markdown("")   # small breathing room

    score = _health_score(df)
    score_int = int(score)     # st.progress expects 0–100 int

    # Colour label based on score bands
    if score >= 75:
        level_label = "🟢 Good"
    elif score >= 50:
        level_label = "🟡 Moderate"
    elif score >= 25:
        level_label = "🟠 Poor"
    else:
        level_label = "🔴 Critical"

    col_label, col_score = st.columns([4, 1])
    with col_label:
        st.caption(f"**Supply Chain Health Score** — {level_label}")
    with col_score:
        st.caption(f"**{score:.1f}%**")

    st.progress(score_int)
