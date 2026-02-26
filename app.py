"""
app.py
======
Streamlit entry point for the MT Product Freshness & Ageing Tracker dashboard.

Run with:
    streamlit run app.py
"""

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure src/ is importable regardless of where Streamlit is launched from
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
import pandas as pd
from datetime import datetime

# ---------------------------------------------------------------------------
# 1. Page config  ← must be the VERY FIRST Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="MT Freshness Tracker",
    page_icon="🥦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Dashboard module imports
# ---------------------------------------------------------------------------
from src.dashboard.data_loader import load_data
from src.dashboard.filters    import render_sidebar
from src.dashboard.kpi_cards  import render_kpi_row
from src.dashboard.charts     import (
    freshness_distribution_bar,
    delivery_delay_histogram,
    monthly_trend_line,
    seller_state_heatmap,
)

# ---------------------------------------------------------------------------
# 2. Header
# ---------------------------------------------------------------------------
col_title, col_refresh = st.columns([5, 1])

with col_title:
    st.title("🥦 MT Product Freshness & Ageing Tracker")
    st.caption(
        f"Last refreshed: **{datetime.now().strftime('%d %b %Y, %H:%M:%S')}**"
        + ("  |  🧪 *Synthetic demo data*" if st.session_state.get("_synthetic") else "")
    )

with col_refresh:
    st.markdown("<br>", unsafe_allow_html=True)   # vertical alignment nudge
    if st.button("🔄 Refresh Data", use_container_width=True):
        load_data.clear()
        st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Drill-down Interactivity: Session State Foundation
# ---------------------------------------------------------------------------
if "selected_category" not in st.session_state:
    st.session_state.selected_category = None
if "selected_state" not in st.session_state:
    st.session_state.selected_state = None
if "drill_down_active" not in st.session_state:
    st.session_state.drill_down_active = False

def reset_drill_down():
    """Reset drill-down filters to default values."""
    st.session_state.selected_category = None
    st.session_state.selected_state = None
    st.session_state.drill_down_active = False


# ---------------------------------------------------------------------------
# 3. Load data
# ---------------------------------------------------------------------------
df = load_data()

# Persist synthetic flag for the subtitle hint
st.session_state["_synthetic"] = df.attrs.get("is_synthetic", False)

if df.attrs.get("is_synthetic"):
    st.info(
        "📊 **Demo mode** — Kaggle Olist CSV files not found in `data/`. "
        "Showing 600 rows of realistic synthetic data. "
        "Download the dataset and place it in `data/` for live analysis.",
        icon="ℹ️",
    )

# ---------------------------------------------------------------------------
# 4. Sidebar filters → filtered DataFrame
# ---------------------------------------------------------------------------
filtered_df = render_sidebar(df)

# ---------------------------------------------------------------------------
# 4b. Drill-down Breadcrumbs & Application
# ---------------------------------------------------------------------------
def apply_drill_filters(df_in: pd.DataFrame) -> pd.DataFrame:
    """Further filter the DataFrame based on active drill-down selections."""
    out = df_in.copy()
    if st.session_state.drill_down_active:
        cat = st.session_state.selected_category
        state = st.session_state.selected_state
        cat_col = "category" if "category" in out.columns else "product_category_name_english"
        
        if cat and cat_col in out.columns:
            out = out[out[cat_col] == cat]
        if state and "seller_state" in out.columns:
            out = out[out["seller_state"] == state]
    return out

filtered_df = apply_drill_filters(filtered_df)

if st.session_state.drill_down_active:
    cat_str = st.session_state.selected_category or "All"
    state_str = st.session_state.selected_state or "All"
    
    col_crumb, col_btn = st.columns([5, 1])
    with col_crumb:
        st.info(f"📍 **Filtered by:** {cat_str} × {state_str}")
    with col_btn:
        st.button("✕ Clear filters", on_click=reset_drill_down, use_container_width=True)

# ---------------------------------------------------------------------------
# 5. KPI row
# ---------------------------------------------------------------------------
render_kpi_row(filtered_df)

st.divider()

# ---------------------------------------------------------------------------
# 6. Chart Control Bar
# ---------------------------------------------------------------------------
if "top_n" not in st.session_state:
    st.session_state.top_n = 10
if "time_period" not in st.session_state:
    st.session_state.time_period = "All Time"

ctrl1, ctrl2, ctrl3, ctrl4 = st.columns([2, 2, 1, 1])

with ctrl1:
    top_n_options = [5, 10, 15, 20, "All"]
    top_n_idx = top_n_options.index(st.session_state.top_n) if st.session_state.top_n in top_n_options else 1
    selected_top_n = st.selectbox(
        "📊 Show Top N Categories",
        options=top_n_options,
        index=top_n_idx,
        key="_top_n_select",
    )
    st.session_state.top_n = selected_top_n

with ctrl2:
    time_options = ["All Time", "Last 6 Months", "Last 12 Months", "2018 Only"]
    tp_idx = time_options.index(st.session_state.time_period) if st.session_state.time_period in time_options else 0
    selected_tp = st.selectbox(
        "🗓️ Time Period",
        options=time_options,
        index=tp_idx,
        key="_time_period_select",
    )
    st.session_state.time_period = selected_tp

# Apply time-period filter for charting
chart_df = filtered_df.copy()
date_col_name = "order_purchase_timestamp"
if date_col_name in chart_df.columns:
    chart_df[date_col_name] = pd.to_datetime(chart_df[date_col_name], errors="coerce")
    if selected_tp == "Last 6 Months":
        cutoff = chart_df[date_col_name].max() - pd.DateOffset(months=6)
        chart_df = chart_df[chart_df[date_col_name] >= cutoff]
    elif selected_tp == "Last 12 Months":
        cutoff = chart_df[date_col_name].max() - pd.DateOffset(months=12)
        chart_df = chart_df[chart_df[date_col_name] >= cutoff]
    elif selected_tp == "2018 Only":
        chart_df = chart_df[chart_df[date_col_name].dt.year == 2018]

with ctrl3:
    st.metric("📦 Filtered Orders", f"{len(chart_df):,}")

with ctrl4:
    rar_col = "revenue_at_risk"
    rar_total = chart_df[rar_col].sum() if rar_col in chart_df.columns else 0
    st.metric("💰 Revenue at Risk", f"R$ {rar_total:,.0f}")

# Resolve top_n for chart call
effective_top_n = len(chart_df) if selected_top_n == "All" else int(selected_top_n)
sel_cat = st.session_state.selected_category

# ---------------------------------------------------------------------------
# 7. Charts — 2×2 grid (border when drill-down is active)
# ---------------------------------------------------------------------------
chart_container = st.container(border=st.session_state.drill_down_active)

with chart_container:
    # Row 1
    row1_left, row1_right = st.columns(2)

    with row1_left:
        st.subheader("Freshness Distribution by Category")

        # Fallback selectbox for category filtering
        cat_col = "category" if "category" in chart_df.columns else "product_category_name_english"
        cat_options = ["All Categories"]
        if cat_col in chart_df.columns:
            cat_options.extend(sorted(chart_df[cat_col].dropna().unique().tolist()))

        sel_idx = 0
        if st.session_state.selected_category in cat_options:
            sel_idx = cat_options.index(st.session_state.selected_category)

        def _cat_select_cb():
            val = st.session_state["_cat_fallback_select"]
            if val == "All Categories":
                st.session_state.selected_category = None
                if not st.session_state.selected_state:
                    st.session_state.drill_down_active = False
            else:
                st.session_state.selected_category = val
                st.session_state.drill_down_active = True

        st.selectbox(
            "Filter by category",
            options=cat_options,
            index=sel_idx,
            key="_cat_fallback_select",
            on_change=_cat_select_cb,
        )

        fig_bar = freshness_distribution_bar(
            chart_df,
            selected_category=sel_cat,
            top_n=effective_top_n,
        )

        st.plotly_chart(
            fig_bar,
            use_container_width=True,
            key="freshness_bar",
            on_select="rerun",
            selection_mode="points",
            config={"displayModeBar": False},
        )

        # Handle click event
        event = st.session_state.get("freshness_bar")
        if event:
            pts = event.get("selection", {}).get("points", [])
            if not pts and "points" in event:
                pts = event["points"]
            if pts:
                clicked_category = pts[0].get("y")
                if clicked_category and clicked_category != st.session_state.selected_category:
                    st.session_state.selected_category = clicked_category
                    st.session_state.drill_down_active = True
                    st.rerun()

    with row1_right:
        st.subheader("Delivery Delay Histogram")
        st.plotly_chart(
            delivery_delay_histogram(
                chart_df,
                selected_category=sel_cat,
                full_df=filtered_df if sel_cat else None,
            ),
            use_container_width=True,
        )

    # Row 2
    row2_left, row2_right = st.columns(2)

    with row2_left:
        st.subheader("Monthly Delay & Revenue at Risk Trend")
        st.plotly_chart(
            monthly_trend_line(
                chart_df,
                selected_category=sel_cat,
                full_df=filtered_df if sel_cat else None,
            ),
            use_container_width=True,
        )

    with row2_right:
        st.subheader("Avg Delay by Seller State")
        st.plotly_chart(
            seller_state_heatmap(
                chart_df,
                selected_category=sel_cat,
            ),
            use_container_width=True,
        )

st.divider()

# ---------------------------------------------------------------------------
# 9. Flagged Orders expander
# ---------------------------------------------------------------------------
_FLAGGED_STATUSES = {"Critical", "Expired"}

tier_col  = "freshness_tier"  if "freshness_tier"  in filtered_df.columns else "freshness_status"
delay_col = "delay_days"      if "delay_days"       in filtered_df.columns else "delivery_delay_days"

flagged = filtered_df[filtered_df[tier_col].isin(_FLAGGED_STATUSES)].copy()

_DISPLAY_COLS = [c for c in [
    "order_id",
    "category",
    "seller_state",
    delay_col,
    tier_col,
    "revenue_at_risk",
] if c in flagged.columns]

_COL_LABELS = {
    delay_col:  "delay_days",
    tier_col:   "freshness_tier",
}

flagged_title = f"📋 Flagged Orders — {len(flagged):,} Critical/Expired orders"
if st.session_state.drill_down_active:
    flagged_title += " (filtered)"

with st.expander(flagged_title, expanded=False):
    if flagged.empty:
        st.success("🎉 No Critical or Expired orders in the current selection.")
    else:
        display = (
            flagged[_DISPLAY_COLS]
            .rename(columns=_COL_LABELS)
            .sort_values("delay_days", ascending=False)
            .reset_index(drop=True)
        )

        _TIER_BG: dict[str, str] = {
            "Critical": "background-color: rgba(231,76,60,0.25);  color: #e74c3c;",
            "Expired":  "background-color: rgba(142,68,173,0.25); color: #8e44ad;",
        }

        def _highlight_tier(val: str) -> str:
            return _TIER_BG.get(val, "")

        styled = display.style.applymap(
            _highlight_tier,
            subset=["freshness_tier"] if "freshness_tier" in display.columns else [],
        )

        if "delay_days" in display.columns:
            styled = styled.format({"delay_days": "{:.1f} d"})
        if "revenue_at_risk" in display.columns:
            styled = styled.format({"revenue_at_risk": "R$ {:,.2f}"})

        st.dataframe(
            styled,
            use_container_width=True,
            height=min(400, 38 + len(display) * 35),
        )

        csv_bytes = display.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Download Flagged Orders CSV",
            data=csv_bytes,
            file_name=f"flagged_orders_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=False,
        )

st.divider()

# ---------------------------------------------------------------------------
# 10. Footer
# ---------------------------------------------------------------------------
st.caption(
    "Built with [Streamlit](https://streamlit.io) · "
    "Data: [Olist Brazilian E-Commerce](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)"
)
