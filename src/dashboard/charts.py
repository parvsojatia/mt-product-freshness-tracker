"""
src/dashboard/charts.py
=======================
All Plotly chart rendering functions for the MT Product Freshness dashboard.

Public API
----------
freshness_distribution_bar(df)  -> go.Figure
delivery_delay_histogram(df)    -> go.Figure
monthly_trend_line(df)          -> go.Figure
seller_state_heatmap(df)        -> go.Figure

Every function accepts a filtered pd.DataFrame (from data_loader.load_data)
and returns a Plotly Figure ready to be rendered with:
    st.plotly_chart(fig, use_container_width=True)
"""

from __future__ import annotations

import json
import urllib.request
import warnings
from functools import lru_cache

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_TEMPLATE   = "plotly_dark"
_HEIGHT     = 400
_MARGINS    = dict(l=10, r=10, t=40, b=10)

# Freshness tier color palette (spec-defined)
_TIER_COLORS: dict[str, str] = {
    "Fresh":    "#2ecc71",
    "Good":     "#27ae60",
    "Caution":  "#f39c12",
    "Warning":  "#e67e22",
    "Critical": "#e74c3c",
    "Expired":  "#8e44ad",
}

# Canonical rendering order (best → worst)
_TIER_ORDER = ["Fresh", "Good", "Caution", "Warning", "Critical", "Expired"]

# Brazil GeoJSON — tried in order, first reachable URL wins
_BRAZIL_GEOJSON_URLS = [
    "https://raw.githubusercontent.com/giuliano-macedo/geodata-br-states/main/geojson/br_states.geojson",
    "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson",
]

# Mapping of state abbreviation → GeoJSON feature property key value
# (different GeoJSON sources use different property names)
_STATE_PROP_CANDIDATES = ["sigla", "abbrev", "UF", "id", "code"]


# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------

def _tier_col(df: pd.DataFrame) -> str | None:
    for col in ("freshness_tier", "freshness_status"):
        if col in df.columns:
            return col
    return None


def _delay_col(df: pd.DataFrame) -> str | None:
    for col in ("delivery_delay_days", "delay_days"):
        if col in df.columns:
            return col
    return None


def _base_layout(title: str, **extra) -> dict:
    """Return a common layout dict to keep charts consistent.
    
    The *title* is kept as an invisible placeholder so Plotly still
    reserves the space, but the visible heading comes from
    ``st.subheader()`` in app.py to avoid double-title overlap.
    """
    return dict(
        title=dict(text=title, font=dict(size=1, color="rgba(0,0,0,0)")),
        template=_TEMPLATE,
        height=_HEIGHT,
        margin=dict(l=10, r=10, t=60, b=10),
        **extra,
    )


@lru_cache(maxsize=1)
def _fetch_brazil_geojson() -> dict | None:
    """
    Attempt to download the Brazil states GeoJSON from known public URLs.
    Returns the parsed dict, or None if every URL fails.
    Cached so the network call only happens once per process.
    """
    for url in _BRAZIL_GEOJSON_URLS:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            continue
    return None


def _detect_state_prop(geojson: dict) -> str | None:
    """
    Detect which property key in the GeoJSON features holds the state
    abbreviation (e.g. 'SP', 'RJ', …).
    """
    if not geojson or "features" not in geojson:
        return None
    sample_props = geojson["features"][0].get("properties", {})
    for key in _STATE_PROP_CANDIDATES:
        if key in sample_props:
            return key
    return None


# ===========================================================================
# 1. Freshness Distribution Stacked Horizontal Bar
# ===========================================================================

def freshness_distribution_bar(
    df: pd.DataFrame,
    selected_category: str | None = None,
    top_n: int = 10,
) -> go.Figure:
    """
    Stacked horizontal bar chart showing freshness tier breakdown per
    product category, sorted by % Critical + Expired descending.
    Filters to the top_n categories by volume.
    Dims non-selected categories if selected_category is provided.

    Parameters
    ----------
    df : pd.DataFrame
        Filtered enriched DataFrame.
    selected_category : str | None
        If provided, highlight this category and dim others.
    top_n : int
        Show only the top N categories by total order volume.

    Returns
    -------
    go.Figure
    """
    tier  = _tier_col(df)
    cat_c = "category" if "category" in df.columns else "product_category_name_english"

    if not tier or cat_c not in df.columns or df.empty:
        fig = go.Figure()
        fig.update_layout(**_base_layout("No data available for freshness distribution"))
        return fig

    # Count items per (category, tier)
    counts = (
        df.groupby([cat_c, tier], observed=True)
        .size()
        .reset_index(name="count")
    )
    
    # 1. Filter to Top N categories by absolute volume
    top_cats = counts.groupby(cat_c)["count"].sum().nlargest(top_n).index
    counts = counts[counts[cat_c].isin(top_cats)].copy()

    # Calculate percentage within those top categories
    totals = counts.groupby(cat_c)["count"].transform("sum")
    counts["pct"] = (counts["count"] / totals) * 100

    # Sort categories by % Critical + Expired (worst first → top of chart)
    at_risk = (
        counts[counts[tier].isin(["Critical", "Expired"])]
        .groupby(cat_c)["pct"]
        .sum()
    )
    # Reindex over all top_cats so 0-risk categories are included, then sort
    at_risk = at_risk.reindex(top_cats).fillna(0).sort_values(ascending=True)
    cat_order = at_risk.index.tolist()

    # Build one trace per tier
    fig = go.Figure()
    present_tiers = [t for t in _TIER_ORDER if t in counts[tier].values]

    for t in present_tiers:
        subset = counts[counts[tier] == t].set_index(cat_c).reindex(cat_order).fillna(0)
        
        marker_opts = dict(color=_TIER_COLORS.get(t, "#95a5a6"))
        if selected_category:
            opacities = [1.0 if cat == selected_category else 0.4 for cat in cat_order]
            line_colors = ["white" if cat == selected_category else "rgba(0,0,0,0)" for cat in cat_order]
            line_widths = [2 if cat == selected_category else 0 for cat in cat_order]
            marker_opts["opacity"] = opacities
            marker_opts["line"] = dict(color=line_colors, width=line_widths)
            
        fig.add_trace(
            go.Bar(
                name=t,
                y=cat_order,
                x=subset["pct"].values,
                orientation="h",
                marker=marker_opts,
                hovertemplate=(
                    f"<b>{t}</b><br>"
                    "Category: %{y}<br>"
                    "Share: %{x:.1f}%<br>"
                    "<extra></extra>"
                ),
            )
        )

    # Add Drill-down hint annotation
    fig.add_annotation(
        text="💡 Click a category to drill down",
        xref="paper", yref="paper",
        x=0, y=1.08,
        showarrow=False,
        font=dict(size=12, color="#95a5a6"),
        align="left"
    )

    fig.update_layout(
        **_base_layout("Freshness Tier Distribution by Category"),
        barmode="stack",
        xaxis=dict(title="Share (%)", ticksuffix="%", range=[0, 100]),
        yaxis=dict(title="", automargin=True),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="left",   x=0,
            traceorder="normal",
        ),
    )
    return fig


# ===========================================================================
# 2. Delivery Delay Histogram
# ===========================================================================

def delivery_delay_histogram(
    df: pd.DataFrame,
    selected_category: str | None = None,
    full_df: pd.DataFrame | None = None,
) -> go.Figure:
    """
    Histogram of delivery delay days coloured by freshness tier.
    Includes vertical lines at mean and median, plus an annotation showing
    the percentage of orders delayed > 7 days.

    When *selected_category* is set the title is suffixed and a white-outline
    background histogram of the full (unfiltered) dataset is drawn for
    comparison.

    Parameters
    ----------
    df : pd.DataFrame
        Filtered enriched DataFrame.
    selected_category : str | None
        Active drill-down category (used for title and annotation).
    full_df : pd.DataFrame | None
        The complete unfiltered DataFrame.  When supplied alongside
        *selected_category* an outline histogram of the overall
        distribution is rendered behind the category-specific bars.
    """
    delay = _delay_col(df)
    tier  = _tier_col(df)

    if not delay or df.empty:
        fig = go.Figure()
        fig.update_layout(**_base_layout("No delay data available"))
        return fig

    delay_data = df[delay].dropna()
    mean_val   = float(delay_data.mean())
    median_val = float(delay_data.median())
    pct_gt7    = float((delay_data > 7).sum() / max(len(delay_data), 1) * 100)

    # Shared bin edges for all tiers so bars stack consistently
    bin_min = max(delay_data.min(), -30)
    bin_max = min(delay_data.max(),  90)
    nbins   = min(60, int((bin_max - bin_min) / 1.5) + 1)
    bin_size = (bin_max - bin_min) / nbins

    fig = go.Figure()

    # --- Background: overall distribution (white outline) when drilling ---
    overall_pct_gt7: float | None = None
    if selected_category and full_df is not None and delay in full_df.columns:
        overall_delay = full_df[delay].dropna()
        if not overall_delay.empty:
            overall_pct_gt7 = float(
                (overall_delay > 7).sum() / max(len(overall_delay), 1) * 100
            )
            fig.add_trace(
                go.Histogram(
                    x=overall_delay,
                    name="Overall",
                    marker=dict(
                        color="rgba(255,255,255,0.05)",
                        line=dict(color="rgba(255,255,255,0.35)", width=1),
                    ),
                    xbins=dict(start=bin_min, end=bin_max, size=bin_size),
                    opacity=0.4,
                    hovertemplate=(
                        "<b>Overall</b><br>"
                        "Delay: %{x:.1f} d<br>"
                        "Count: %{y}<br>"
                        "<extra></extra>"
                    ),
                )
            )

    # --- Foreground: filtered data coloured by tier ---
    if tier and tier in df.columns:
        for t in _TIER_ORDER:
            mask   = df[tier] == t
            subset = df.loc[mask, delay].dropna()
            if subset.empty:
                continue
            fig.add_trace(
                go.Histogram(
                    x=subset,
                    name=t,
                    marker_color=_TIER_COLORS.get(t, "#95a5a6"),
                    xbins=dict(start=bin_min, end=bin_max, size=bin_size),
                    opacity=0.85,
                    hovertemplate=(
                        f"<b>{t}</b><br>"
                        "Delay: %{x:.1f} d<br>"
                        "Count: %{y}<br>"
                        "<extra></extra>"
                    ),
                )
            )
        fig.update_layout(barmode="stack")
    else:
        fig.add_trace(
            go.Histogram(
                x=delay_data,
                marker_color="#3498db",
                nbinsx=nbins,
            )
        )

    # Vertical lines: mean and median
    for val, label, color, dash in [
        (mean_val,   f"Mean {mean_val:.1f}d",   "#f1c40f", "dash"),
        (median_val, f"Median {median_val:.1f}d", "#1abc9c", "dot"),
    ]:
        fig.add_vline(
            x=val,
            line_dash=dash,
            line_color=color,
            line_width=2,
            annotation=dict(
                text=label,
                font=dict(color=color, size=11),
                yref="paper",
                y=0.97,
                showarrow=False,
                bgcolor="rgba(0,0,0,0.4)",
                borderpad=3,
            ),
        )

    # Annotation: % orders > 7 days late (category vs overall when drilling)
    if selected_category and overall_pct_gt7 is not None:
        annot_text = (
            f"<b>Category: {pct_gt7:.1f}%</b> vs "
            f"Overall: {overall_pct_gt7:.1f}%  delayed > 7 d"
        )
    else:
        annot_text = f"<b>{pct_gt7:.1f}%</b> of orders delayed > 7 days"

    fig.add_annotation(
        text=annot_text,
        xref="paper", yref="paper",
        x=0.99, y=0.97,
        showarrow=False,
        align="right",
        font=dict(color="#e74c3c", size=12),
        bgcolor="rgba(0,0,0,0.4)",
        borderpad=4,
    )

    title = "Delivery Delay Distribution"
    if selected_category:
        title += f" — {selected_category}"

    fig.update_layout(
        **_base_layout(title),
        xaxis=dict(title="Delay (days)", zeroline=True,
                   zerolinecolor="rgba(255,255,255,0.3)", zerolinewidth=1),
        yaxis=dict(title="Order Count"),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="left",   x=0,
        ),
        bargap=0.05,
    )
    return fig


# ===========================================================================
# 3. Monthly Trend Dual-Axis Line Chart
# ===========================================================================

def monthly_trend_line(
    df: pd.DataFrame,
    selected_category: str | None = None,
    full_df: pd.DataFrame | None = None,
) -> go.Figure:
    """
    Dual-axis line chart:
      - Left  Y-axis : average delivery delay days per month
      - Right Y-axis : total revenue at risk per month
    A 3-month rolling average line is overlaid on the delay series.

    When *selected_category* is set, the category trend is rendered as
    bold lines and the overall average is shown as a faded dashed line
    for comparison.  Months with fewer than 30 orders are marked with
    diamond markers and labelled in the legend.
    """
    date_col  = "order_purchase_timestamp"
    delay     = _delay_col(df)
    rar_col   = "revenue_at_risk"

    if date_col not in df.columns or df.empty:
        fig = go.Figure()
        fig.update_layout(**_base_layout("No date data for monthly trend"))
        return fig

    # ---------- helper to aggregate any df into monthly ----------
    def _monthly_agg(src: pd.DataFrame) -> pd.DataFrame:
        tmp = src.copy()
        tmp["_month"] = pd.to_datetime(tmp[date_col], errors="coerce").dt.to_period("M")
        tmp = tmp.dropna(subset=["_month"])
        agg: dict[str, tuple] = {}
        agg["order_count"] = (date_col, "size")
        if delay and delay in tmp.columns:
            agg["avg_delay"] = (delay, "mean")
        if rar_col in tmp.columns:
            agg["rar"] = (rar_col, "sum")
        m = tmp.groupby("_month").agg(**agg).reset_index().sort_values("_month")
        m["month_str"] = m["_month"].astype(str)
        if "avg_delay" in m.columns:
            m["delay_rolling3"] = m["avg_delay"].rolling(window=3, min_periods=1).mean()
        return m

    monthly = _monthly_agg(df)
    if monthly.empty:
        fig = go.Figure()
        fig.update_layout(**_base_layout("Monthly Trend (insufficient data)"))
        return fig

    fig = go.Figure()

    # --- Faded overall comparison when drill-down is active ---
    if selected_category and full_df is not None:
        overall = _monthly_agg(full_df)
        if "avg_delay" in overall.columns:
            fig.add_trace(
                go.Scatter(
                    x=overall["month_str"],
                    y=overall["avg_delay"].round(2),
                    name="Overall Avg Delay",
                    mode="lines",
                    line=dict(color="rgba(231,76,60,0.25)", width=2, dash="dash"),
                    yaxis="y1",
                    hovertemplate="Month: %{x}<br>Overall Avg: %{y:.1f} d<extra></extra>",
                )
            )

    # -- LEFT AXIS: avg delay (bold when drilling) --
    if "avg_delay" in monthly.columns:
        line_w = 3 if selected_category else 2

        # Separate low-data months (< 30 orders) for special marker
        low_mask = monthly["order_count"] < 30
        normal = monthly[~low_mask]
        low    = monthly[low_mask]

        fig.add_trace(
            go.Scatter(
                x=normal["month_str"],
                y=normal["avg_delay"].round(2),
                name="Avg Delay (days)",
                mode="lines+markers",
                line=dict(color="#e74c3c", width=line_w),
                marker=dict(size=5),
                yaxis="y1",
                hovertemplate="Month: %{x}<br>Avg Delay: %{y:.1f} d<extra></extra>",
            )
        )

        if not low.empty:
            fig.add_trace(
                go.Scatter(
                    x=low["month_str"],
                    y=low["avg_delay"].round(2),
                    name="Low data (<30 orders)",
                    mode="markers",
                    marker=dict(size=9, symbol="diamond", color="#e74c3c",
                                line=dict(color="white", width=1)),
                    yaxis="y1",
                    hovertemplate="Month: %{x}<br>Avg Delay: %{y:.1f} d<br>⚠ <30 orders<extra></extra>",
                )
            )

        fig.add_trace(
            go.Scatter(
                x=monthly["month_str"],
                y=monthly["delay_rolling3"].round(2),
                name="3-Month Rolling Avg (Delay)",
                mode="lines",
                line=dict(color="#e74c3c", width=line_w, dash="dot"),
                yaxis="y1",
                hovertemplate="Month: %{x}<br>Rolling Avg: %{y:.1f} d<extra></extra>",
            )
        )

    # -- RIGHT AXIS: revenue at risk --
    if "rar" in monthly.columns:
        fig.add_trace(
            go.Scatter(
                x=monthly["month_str"],
                y=monthly["rar"].round(2),
                name="Revenue at Risk (R$)",
                mode="lines+markers",
                line=dict(color="#f39c12", width=2, dash="dash"),
                marker=dict(size=5, symbol="diamond"),
                yaxis="y2",
                hovertemplate="Month: %{x}<br>Revenue at Risk: R$ %{y:,.0f}<extra></extra>",
            )
        )

    title = "Monthly Delivery Delay & Revenue at Risk Trend"
    if selected_category:
        title += f" — {selected_category}"

    fig.update_layout(
        **_base_layout(title),
        xaxis=dict(title="Month", tickangle=-30),
        yaxis=dict(
            title=dict(text="Avg Delay (days)", font=dict(color="#e74c3c")),
            tickfont=dict(color="#e74c3c"),
            zeroline=True,
            zerolinecolor="rgba(255,255,255,0.2)",
        ),
        yaxis2=dict(
            title=dict(text="Revenue at Risk (R$)", font=dict(color="#f39c12")),
            tickfont=dict(color="#f39c12"),
            overlaying="y",
            side="right",
            showgrid=False,
            tickprefix="R$ ",
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="left",   x=0,
        ),
    )
    return fig


# ===========================================================================
# 4. Seller State Heatmap (Choropleth or Fallback Bar)
# ===========================================================================

def seller_state_heatmap(
    df: pd.DataFrame,
    selected_category: str | None = None,
) -> go.Figure:
    """
    Visualise average delivery delay by Brazilian seller state.

    Primary:  Plotly Express choropleth_mapbox using a Brazil GeoJSON.
    Fallback: Sorted horizontal bar chart when GeoJSON is unavailable.

    When *selected_category* is set the title includes the category name
    and the top 3 worst-performing states are overlaid as labelled dots.
    """
    delay   = _delay_col(df)
    st_col  = "seller_state"

    if st_col not in df.columns or not delay or df.empty:
        fig = go.Figure()
        fig.update_layout(**_base_layout("No state / delay data available"))
        return fig

    # Aggregate per state
    state_df = (
        df.groupby(st_col, observed=True)[delay]
        .mean()
        .reset_index()
        .rename(columns={delay: "avg_delay_days"})
        .dropna()
    )
    state_df["avg_delay_days"] = state_df["avg_delay_days"].round(2)

    # Top 3 worst-performing states
    worst3 = state_df.nlargest(3, "avg_delay_days")

    # Dynamic title
    title = "Avg Delivery Delay by Seller State"
    if selected_category:
        title += f" — {selected_category}"

    # --- Try choropleth ---
    geojson = _fetch_brazil_geojson()
    prop    = _detect_state_prop(geojson) if geojson else None

    # Rough centroid lookup for Brazilian states (lat, lon)
    _STATE_COORDS: dict[str, tuple[float, float]] = {
        "AC": (-9.02, -70.81), "AL": (-9.57, -36.78), "AM": (-3.47, -65.10),
        "AP": (1.41, -51.77),  "BA": (-12.97, -41.24), "CE": (-5.20, -39.53),
        "DF": (-15.78, -47.93),"ES": (-19.18, -40.31), "GO": (-15.93, -49.88),
        "MA": (-4.96, -45.27), "MG": (-18.51, -44.55), "MS": (-20.77, -54.79),
        "MT": (-12.64, -55.42),"PA": (-3.79, -52.48),  "PB": (-7.24, -36.78),
        "PE": (-8.28, -37.86), "PI": (-7.72, -42.73),  "PR": (-24.89, -51.55),
        "RJ": (-22.91, -43.17),"RN": (-5.81, -36.59),  "RO": (-10.83, -63.34),
        "RR": (1.99, -61.33),  "RS": (-29.75, -53.17),  "SC": (-27.24, -50.22),
        "SE": (-10.57, -37.45),"SP": (-22.19, -48.79),  "TO": (-10.18, -48.33),
    }

    if geojson and prop:
        try:
            fig = px.choropleth_mapbox(
                state_df,
                geojson=geojson,
                locations=st_col,
                featureidkey=f"properties.{prop}",
                color="avg_delay_days",
                color_continuous_scale=[
                    [0.0,  "#2ecc71"],
                    [0.35, "#f39c12"],
                    [0.65, "#e67e22"],
                    [1.0,  "#e74c3c"],
                ],
                mapbox_style="carto-darkmatter",
                center=dict(lat=-14.24, lon=-51.93),
                zoom=3.0,
                height=_HEIGHT,
                title=f"{title} (days)",
                hover_data={st_col: True, "avg_delay_days": ":.1f"},
                labels={"avg_delay_days": "Avg Delay (d)", st_col: "State"},
            )

            # Overlay top-3 worst states as labelled dots
            if selected_category and not worst3.empty:
                w3_lats, w3_lons, w3_texts = [], [], []
                for _, row in worst3.iterrows():
                    coords = _STATE_COORDS.get(row[st_col])
                    if coords:
                        w3_lats.append(coords[0])
                        w3_lons.append(coords[1])
                        w3_texts.append(f"{row[st_col]}: {row['avg_delay_days']:.1f}d")
                if w3_lats:
                    fig.add_trace(
                        go.Scattermapbox(
                            lat=w3_lats, lon=w3_lons,
                            mode="markers+text",
                            marker=dict(size=14, color="#e74c3c",
                                        symbol="circle"),
                            text=w3_texts,
                            textposition="top center",
                            textfont=dict(color="white", size=11),
                            name="Top 3 Worst States",
                            hoverinfo="text",
                        )
                    )

            fig.update_layout(
                template=_TEMPLATE,
                margin=_MARGINS,
                coloraxis_colorbar=dict(
                    title="Days",
                    ticksuffix=" d",
                ),
            )
            return fig
        except Exception as exc:
            warnings.warn(
                f"[charts] Choropleth failed ({exc}); using fallback bar chart.",
                stacklevel=2,
            )

    # --- Fallback: sorted horizontal bar chart ---
    state_sorted = state_df.sort_values("avg_delay_days", ascending=True)

    def _bar_color(delay_val: float) -> str:
        if delay_val <= 0:
            return _TIER_COLORS["Fresh"]
        elif delay_val <= 3:
            return _TIER_COLORS["Good"]
        elif delay_val <= 7:
            return _TIER_COLORS["Caution"]
        elif delay_val <= 14:
            return _TIER_COLORS["Warning"]
        else:
            return _TIER_COLORS["Critical"]

    bar_colors = [_bar_color(v) for v in state_sorted["avg_delay_days"]]

    fig = go.Figure(
        go.Bar(
            x=state_sorted["avg_delay_days"],
            y=state_sorted[st_col],
            orientation="h",
            marker_color=bar_colors,
            hovertemplate=(
                "State: %{y}<br>"
                "Avg Delay: %{x:.1f} d<br>"
                "<extra></extra>"
            ),
        )
    )

    # Annotate top 3 worst in fallback bar chart too
    if selected_category and not worst3.empty:
        for _, row in worst3.iterrows():
            fig.add_annotation(
                x=row["avg_delay_days"], y=row[st_col],
                text=f"  {row['avg_delay_days']:.1f}d",
                showarrow=False,
                font=dict(color="white", size=11, family="monospace"),
                xanchor="left",
            )

    fig.update_layout(
        **_base_layout(title),
        xaxis=dict(
            title="Avg Delay (days)",
            zeroline=True,
            zerolinecolor="rgba(255,255,255,0.3)",
        ),
        yaxis=dict(title="Seller State", automargin=True),
    )
    return fig


# ---------------------------------------------------------------------------
# Orchestrator (called from app.py)
# ---------------------------------------------------------------------------

def render_charts(df: pd.DataFrame) -> None:
    """
    Lay out all four charts on the main dashboard canvas using Streamlit.
    Import streamlit inside the function so this module stays pure-Plotly
    when used outside of a Streamlit context.
    """
    import streamlit as st

    if df.empty:
        st.warning("No data matches the current filters — adjust the sidebar.")
        return

    # Row 1: Freshness distribution | Delay histogram
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(freshness_distribution_bar(df), use_container_width=True)
    with col2:
        st.plotly_chart(delivery_delay_histogram(df), use_container_width=True)

    st.divider()

    # Row 2: Monthly trend (full width)
    st.plotly_chart(monthly_trend_line(df), use_container_width=True)

    st.divider()

    # Row 3: State heatmap (full width)
    st.plotly_chart(seller_state_heatmap(df), use_container_width=True)
