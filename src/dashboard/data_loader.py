"""
src/dashboard/data_loader.py
============================
Data ingestion and caching layer for the Streamlit dashboard.

Public API
----------
load_data() -> pd.DataFrame
    Load, analyze, and enrich the order DataFrame.
    Cached with @st.cache_data so Streamlit only runs it once per session.
    Falls back to a realistic synthetic dataset if the Olist CSV files are
    not found in the data/ directory.

get_summary_stats(df) -> dict
    Compute lightweight KPI metrics from the enriched DataFrame for use in
    the dashboard's top-row KPI cards.
"""

from __future__ import annotations

import sys
import os
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Path setup — allow importing src.freshness_analyzer when running via
# `streamlit run app.py` from the project root.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parents[2]  # supply/
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.freshness_analyzer import FreshnessAnalyzer  # noqa: E402


# ---------------------------------------------------------------------------
# Column aliases added by this module on top of FreshnessAnalyzer output
# ---------------------------------------------------------------------------
# freshness_tier   → friendlier alias for freshness_status
# delay_days       → alias for delivery_delay_days (shorter name for charts)
# revenue_at_risk  → per-row value: price of flagged items, else 0
# shelf_life_consumed_pct → alias for shelf_life_pct (explicit name for dashboard)

_FRESHNESS_STATUSES = ["Fresh", "Good", "Caution", "Warning", "Critical", "Expired"]
_AT_RISK_STATUSES   = {"Critical", "Warning", "Expired"}

_BR_STATES = [
    "SP", "RJ", "MG", "RS", "PR", "SC", "BA", "GO", "PE", "CE",
    "ES", "PA", "MT", "MS", "MA", "RN", "AL", "PB", "PI", "RO",
    "AM", "SE", "TO", "AC", "AP", "RR", "DF",
]

_CATEGORIES = [
    "bed_bath_table", "health_beauty", "sports_leisure", "furniture_decor",
    "computers_accessories", "housewares", "telephony", "watches_gifts",
    "auto", "toys", "garden_tools", "cool_stuff", "office_furniture",
    "stationery", "food_drink", "perfumery", "electronics",
    "fashion_bags_accessories", "books_technical", "musical_instruments",
]


# ===========================================================================
# Synthetic data generator
# ===========================================================================

def _make_synthetic_df(n: int = 600, seed: int = 42) -> pd.DataFrame:
    """
    Generate a realistic synthetic DataFrame that mirrors the exact schema
    produced by FreshnessAnalyzer.analyze() so the dashboard can be demoed
    without the Kaggle dataset.

    Parameters
    ----------
    n : int
        Number of rows to generate (≥ 500 as per spec).
    seed : int
        Random seed for reproducibility.
    """
    rng = np.random.default_rng(seed)

    # --- Date scaffolding ---
    purchase_dates = pd.to_datetime(
        rng.integers(
            pd.Timestamp("2017-01-01").value,
            pd.Timestamp("2018-09-01").value,
            n,
        )
    )

    # Estimated delivery window: 10–35 days after purchase
    est_window_days = rng.integers(10, 35, n).astype(float)
    estimated_delivery = purchase_dates + pd.to_timedelta(est_window_days, unit="D")

    # Actual delivery: estimated + delay (can be negative = early)
    # Use a right-skewed distribution weighted toward on-time / slightly late
    delay_days_raw = rng.normal(loc=1.5, scale=8.0, size=n)  # most near 0, some outliers
    delivery_delay_days = np.round(delay_days_raw, 1)

    delivered_date = estimated_delivery + pd.to_timedelta(delivery_delay_days, unit="D")

    # Order age (purchase → actual delivery)
    order_age_days = np.round(est_window_days + delivery_delay_days, 1).clip(1, None)

    # Processing & shipping breakdown
    processing_time_days = np.round(rng.uniform(1.0, 5.0, n), 1)
    shipping_time_days   = np.round(order_age_days - processing_time_days, 1).clip(1, None)

    # Shelf-life %
    shelf_life_pct = np.round(
        (order_age_days / est_window_days * 100).clip(0, 200), 1
    )

    # Approval time (purchase + 0–2 days)
    approved_at = purchase_dates + pd.to_timedelta(rng.uniform(0, 2, n), unit="D")
    carrier_date = purchase_dates + pd.to_timedelta(processing_time_days, unit="D")

    # --- Freshness status (mirrors FreshnessAnalyzer logic) ---
    # ~5% cancelled/unavailable → Expired
    order_status = np.where(
        rng.random(n) < 0.05,
        rng.choice(["canceled", "unavailable"], n),
        "delivered",
    )

    def _assign_freshness(status_arr, delay_arr):
        results = np.empty(len(status_arr), dtype=object)
        for i, (s, d) in enumerate(zip(status_arr, delay_arr)):
            if s in ("canceled", "unavailable"):
                results[i] = "Expired"
            elif d > 14:
                results[i] = "Critical"
            elif d > 7:
                results[i] = "Warning"
            elif d > 3:
                results[i] = "Caution"
            elif d > 0:
                results[i] = "Good"
            else:
                results[i] = "Fresh"
        return results

    freshness_status = _assign_freshness(order_status, delivery_delay_days)

    status_scores = {
        "Fresh": 100, "Good": 75, "Caution": 50,
        "Warning": 25, "Critical": 10, "Expired": 0,
    }
    freshness_score = np.array([status_scores[s] for s in freshness_status])

    # --- Other columns ---
    price = np.round(rng.uniform(10.0, 800.0, n), 2)
    revenue_at_risk = np.where(
        np.isin(freshness_status, list(_AT_RISK_STATUSES)), price, 0.0
    )

    order_ids   = [f"ORD{str(i).zfill(6)}" for i in range(n)]
    product_ids = [f"PROD{str(rng.integers(0, 800)):>05}" for _ in range(n)]
    seller_ids  = [f"SLR{str(rng.integers(0, 150)):>04}" for _ in range(n)]

    df = pd.DataFrame(
        {
            # IDs
            "order_id":                       order_ids,
            "product_id":                     product_ids,
            "seller_id":                      seller_ids,
            # Timestamps
            "order_purchase_timestamp":       purchase_dates,
            "order_approved_at":              approved_at,
            "order_delivered_carrier_date":   carrier_date,
            "order_delivered_customer_date":  delivered_date,
            "order_estimated_delivery_date":  estimated_delivery,
            # Status
            "order_status":                   order_status,
            # Metrics
            "order_age_days":                 order_age_days,
            "delivery_delay_days":            delivery_delay_days,
            "processing_time_days":           processing_time_days,
            "shipping_time_days":             shipping_time_days,
            "shelf_life_pct":                 shelf_life_pct,
            # Freshness
            "freshness_status":               freshness_status,
            "freshness_score":                freshness_score,
            # Commerce
            "price":                          price,
            "category":                       rng.choice(_CATEGORIES, n),
            "seller_state":                   rng.choice(_BR_STATES, n),
        }
    )

    return df


# ===========================================================================
# Column enrichment helpers (applied to both real and synthetic data)
# ===========================================================================

def _add_dashboard_aliases(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add convenient alias / derived columns used by dashboard components.
    Operates on a copy so the caller's DataFrame is never mutated.
    """
    df = df.copy()

    # Alias: freshness_tier mirrors freshness_status (expected by some charts)
    if "freshness_tier" not in df.columns:
        df["freshness_tier"] = df["freshness_status"]

    # Alias: delay_days (shorter name expected by filter/chart components)
    if "delay_days" not in df.columns:
        src = "delivery_delay_days" if "delivery_delay_days" in df.columns else None
        if src:
            df["delay_days"] = df[src]

    # Alias: shelf_life_consumed_pct (explicit name requested in spec)
    if "shelf_life_consumed_pct" not in df.columns:
        src = "shelf_life_pct" if "shelf_life_pct" in df.columns else None
        if src:
            df["shelf_life_consumed_pct"] = df[src]

    # Per-row revenue_at_risk: price for flagged orders, else 0
    if "revenue_at_risk" not in df.columns and "price" in df.columns:
        df["revenue_at_risk"] = np.where(
            df["freshness_status"].isin(_AT_RISK_STATUSES),
            df["price"],
            0.0,
        )

    return df


# ===========================================================================
# Public: load_data
# ===========================================================================

@st.cache_data(show_spinner="Loading freshness data…")
def load_data() -> pd.DataFrame:
    """
    Load, analyze, and return the enriched order DataFrame.

    Execution path
    --------------
    1. Try to run the full FreshnessAnalyzer pipeline against data/ CSVs.
    2. On FileNotFoundError (Kaggle dataset not downloaded yet), generate a
       realistic synthetic DataFrame with ≥ 500 rows and the same schema.
    3. Add dashboard-specific alias columns before returning.

    Returns
    -------
    pd.DataFrame
        Enriched DataFrame containing all freshness columns:
        freshness_status, freshness_tier, freshness_score, order_age_days,
        delivery_delay_days, delay_days, shelf_life_pct,
        shelf_life_consumed_pct, revenue_at_risk, price, category,
        seller_state, and all original timestamp columns.
    """
    data_dir = _PROJECT_ROOT / "data"

    try:
        analyzer = (
            FreshnessAnalyzer(data_dir=str(data_dir))
            .load_data()
            .analyze()
        )
        df = analyzer.merged.copy()
        is_synthetic = False

    except FileNotFoundError as exc:
        warnings.warn(
            f"[data_loader] Real data not found — using synthetic demo data.\n"
            f"  Reason: {exc}",
            stacklevel=2,
        )
        df = _make_synthetic_df(n=600)
        is_synthetic = True

    df = _add_dashboard_aliases(df)

    # Attach metadata as DataFrame attrs (accessible in dashboard components)
    df.attrs["is_synthetic"] = is_synthetic
    df.attrs["row_count"]    = len(df)

    return df


# ===========================================================================
# Public: get_summary_stats
# ===========================================================================

def get_summary_stats(df: pd.DataFrame) -> dict:
    """
    Compute lightweight KPI metrics from an enriched DataFrame.

    Designed for the dashboard's top-row KPI cards; delegates to the richer
    FreshnessAnalyzer.get_summary_stats() when real data is present, and
    computes equivalent metrics directly for synthetic data.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame returned by :func:`load_data`.

    Returns
    -------
    dict with keys:
        total_orders          – unique order count
        pct_fresh             – % of items with freshness_status "Fresh" or "Good"
        pct_critical          – % of items with freshness_status "Critical"
        pct_expired           – % of items with freshness_status "Expired"
        total_revenue_at_risk – sum of revenue_at_risk column (R$)
        avg_delay_days        – mean delivery_delay_days for delivered orders
    """
    n = max(len(df), 1)
    status = df["freshness_status"] if "freshness_status" in df.columns else pd.Series(dtype=str)

    # Unique order count (order_id may not exist in edge cases)
    total_orders = (
        int(df["order_id"].nunique())
        if "order_id" in df.columns
        else n
    )

    pct_fresh = round(
        status.isin(["Fresh", "Good"]).sum() / n * 100, 1
    )
    pct_critical = round(
        (status == "Critical").sum() / n * 100, 1
    )
    pct_expired = round(
        (status == "Expired").sum() / n * 100, 1
    )

    total_revenue_at_risk = round(
        float(df["revenue_at_risk"].sum()) if "revenue_at_risk" in df.columns else 0.0,
        2,
    )

    # avg_delay over delivered orders only (mirrors FreshnessAnalyzer behaviour)
    delivered = df[df.get("order_status", pd.Series(["delivered"] * n)) == "delivered"]
    delay_col = "delivery_delay_days" if "delivery_delay_days" in delivered.columns else "delay_days"
    avg_delay_days = round(
        float(delivered[delay_col].mean()) if delay_col in delivered.columns and len(delivered) > 0 else 0.0,
        1,
    )

    return {
        "total_orders":          total_orders,
        "pct_fresh":             pct_fresh,
        "pct_critical":          pct_critical,
        "pct_expired":           pct_expired,
        "total_revenue_at_risk": total_revenue_at_risk,
        "avg_delay_days":        avg_delay_days,
    }
