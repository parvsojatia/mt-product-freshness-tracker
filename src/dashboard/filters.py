"""
src/dashboard/filters.py
========================
Sidebar filter components for the Streamlit dashboard.

Public API
----------
render_sidebar(df) -> pd.DataFrame
    Render all sidebar filter widgets and return a filtered copy of df.
"""

from __future__ import annotations

import datetime
import pandas as pd
import streamlit as st


# ---------------------------------------------------------------------------
# Freshness tier ordering and emoji color hints
# ---------------------------------------------------------------------------
_TIER_EMOJI = {
    "Fresh":    "🟢",
    "Good":     "🟡",
    "Caution":  "🟠",
    "Warning":  "🔴",
    "Critical": "🔥",
    "Expired":  "❌",
}

# Canonical display order (best → worst)
_TIER_ORDER = ["Fresh", "Good", "Caution", "Warning", "Critical", "Expired"]


def _label(tier: str) -> str:
    """Return an emoji-prefixed label for a freshness tier."""
    return f"{_TIER_EMOJI.get(tier, '⚪')} {tier}"


def _strip_label(label: str) -> str:
    """Strip the emoji prefix added by _label() to recover the raw tier name."""
    return label.split(" ", 1)[-1] if " " in label else label


# ---------------------------------------------------------------------------
# Public: render_sidebar
# ---------------------------------------------------------------------------

def render_sidebar(df: pd.DataFrame) -> pd.DataFrame:
    """
    Render the dashboard sidebar with all filter controls and return a
    filtered copy of *df* reflecting every selected filter.

    Filters applied (all are AND-combined):
    1. Product category multi-select
    2. Seller state multi-select
    3. Freshness tier multi-select (with emoji color hints)
    4. Purchase date range slider
    5. Revenue-at-risk threshold (minimum, exclusive lower-bound filter
       applied to the *revenue_at_risk* column)

    A small "Showing X of Y orders" metric is shown at the bottom of the
    sidebar for instant feedback.

    Parameters
    ----------
    df : pd.DataFrame
        The full enriched DataFrame from :func:`~src.dashboard.data_loader.load_data`.

    Returns
    -------
    pd.DataFrame
        A filtered copy of *df*.  The original DataFrame is never mutated.
    """
    with st.sidebar:
        st.title("🔍 Filters")
        st.markdown("---")

        filtered = df.copy()

        # ------------------------------------------------------------------ #
        # 1. Product Category
        # ------------------------------------------------------------------ #
        cat_col = (
            "category"
            if "category" in df.columns
            else "product_category_name_english"
            if "product_category_name_english" in df.columns
            else None
        )

        if cat_col:
            all_categories = sorted(df[cat_col].dropna().unique().tolist())
            selected_categories = st.multiselect(
                "📦 Product Category",
                options=all_categories,
                default=[],
                placeholder="All categories",
            )
            if selected_categories:
                filtered = filtered[filtered[cat_col].isin(selected_categories)]
        else:
            st.caption("⚠️ Category column not found.")

        # ------------------------------------------------------------------ #
        # 2. Seller State
        # ------------------------------------------------------------------ #
        if "seller_state" in df.columns:
            all_states = sorted(df["seller_state"].dropna().unique().tolist())
            selected_states = st.multiselect(
                "📍 Seller State",
                options=all_states,
                default=[],
                placeholder="All states",
            )
            if selected_states:
                filtered = filtered[filtered["seller_state"].isin(selected_states)]

        # ------------------------------------------------------------------ #
        # 3. Freshness Tier  (with emoji color hints)
        # ------------------------------------------------------------------ #
        tier_col = (
            "freshness_tier"
            if "freshness_tier" in df.columns
            else "freshness_status"
            if "freshness_status" in df.columns
            else None
        )

        if tier_col:
            present_tiers = [t for t in _TIER_ORDER if t in df[tier_col].values]
            tier_labels   = [_label(t) for t in present_tiers]

            selected_labels = st.multiselect(
                "🏷️ Freshness Tier",
                options=tier_labels,
                default=[],
                placeholder="All tiers",
                help="🟢 Fresh/Good = on-time  |  🔥 Critical = >14d late  |  ❌ Expired = cancelled",
            )
            if selected_labels:
                selected_tiers = [_strip_label(lbl) for lbl in selected_labels]
                filtered = filtered[filtered[tier_col].isin(selected_tiers)]

        # ------------------------------------------------------------------ #
        # 4. Purchase Date Range
        # ------------------------------------------------------------------ #
        date_col = "order_purchase_timestamp"
        if date_col in df.columns:
            ts = pd.to_datetime(df[date_col], errors="coerce").dropna()
            if not ts.empty:
                min_date = ts.min().date()
                max_date = ts.max().date()

                st.markdown("📅 **Purchase Date Range**")
                date_range = st.slider(
                    "Purchase Date Range",
                    min_value=min_date,
                    max_value=max_date,
                    value=(min_date, max_date),
                    format="MMM YYYY",
                    label_visibility="collapsed",
                )
                start_date, end_date = date_range
                mask = (
                    pd.to_datetime(filtered[date_col], errors="coerce").dt.date
                    .between(start_date, end_date)
                )
                filtered = filtered[mask]

        # ------------------------------------------------------------------ #
        # 5. Revenue at Risk Threshold
        # ------------------------------------------------------------------ #
        if "revenue_at_risk" in df.columns:
            st.markdown("💰 **Min Revenue at Risk (R$)**")
            rar_max   = float(df["revenue_at_risk"].max()) if len(df) else 1000.0
            rar_threshold = st.number_input(
                "Min Revenue at Risk (R$)",
                min_value=0.0,
                max_value=rar_max,
                value=0.0,
                step=50.0,
                format="%.2f",
                label_visibility="collapsed",
                help="Only show orders whose per-order Revenue at Risk is ≥ this value. "
                     "Set to 0 to include all orders.",
            )
            if rar_threshold > 0:
                filtered = filtered[filtered["revenue_at_risk"] >= rar_threshold]

        # ------------------------------------------------------------------ #
        # Summary metric
        # ------------------------------------------------------------------ #
        st.markdown("---")
        total   = len(df)
        showing = len(filtered)

        if showing == total:
            st.success(f"Showing **all {showing:,}** orders")
        elif showing == 0:
            st.error("⚠️ No orders match the current filters.")
        else:
            pct = showing / total * 100
            st.info(f"Showing **{showing:,}** of **{total:,}** orders ({pct:.1f}%)")

    return filtered


# ---------------------------------------------------------------------------
# Backward-compatible alias requested in the original skeleton
# ---------------------------------------------------------------------------
def render_sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Alias for :func:`render_sidebar`."""
    return render_sidebar(df)


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """
    Apply a pre-computed filter dict to *df* programmatically (e.g. for tests).

    Expected keys (all optional):
        categories  : list[str]
        states      : list[str]
        tiers       : list[str]
        date_range  : tuple[datetime.date, datetime.date]
        rar_min     : float
    """
    filtered = df.copy()

    cat_col  = "category" if "category" in df.columns else "product_category_name_english"
    tier_col = "freshness_tier" if "freshness_tier" in df.columns else "freshness_status"

    if filters.get("categories"):
        filtered = filtered[filtered[cat_col].isin(filters["categories"])]

    if filters.get("states"):
        filtered = filtered[filtered["seller_state"].isin(filters["states"])]

    if filters.get("tiers"):
        filtered = filtered[filtered[tier_col].isin(filters["tiers"])]

    if filters.get("date_range"):
        start, end = filters["date_range"]
        ts = pd.to_datetime(filtered["order_purchase_timestamp"], errors="coerce").dt.date
        filtered = filtered[ts.between(start, end)]

    rar_min = filters.get("rar_min", 0.0)
    if rar_min and rar_min > 0 and "revenue_at_risk" in filtered.columns:
        filtered = filtered[filtered["revenue_at_risk"] >= rar_min]

    return filtered
