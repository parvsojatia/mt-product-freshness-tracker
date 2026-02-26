"""
Plotly Interactive Visualizer
==============================
Creates 8 interactive HTML charts from the analysed order data:
  1. Freshness Status by Category (stacked bar)
  2. Ageing Heatmap (avg delivery delay × category × seller state)
  3. Delivery Timeline (scatter of delivery dates with delay coloring)
  4. Stock-at-Risk Pie Chart (freshness status proportions)
  5. Delivery Delay Distribution (histogram)
  6. Monthly Trend (dual-axis: order volume + on-time rate)
  7. Worst Performers (horizontal bar: bottom 10 categories by on-time rate)
  8. Seller Performance Radar (spider chart: top 6 states across 5 KPIs)
"""

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from pathlib import Path


# Consistent color palette for freshness statuses
STATUS_COLORS = {
    "Fresh": "#00C853",
    "Good": "#FFD600",
    "Caution": "#FF9100",
    "Warning": "#FF3D00",
    "Critical": "#D50000",
    "Expired": "#424242",
    "Unknown": "#9E9E9E",
}

STATUS_ORDER = ["Fresh", "Good", "Caution", "Warning", "Critical", "Expired"]


class Visualizer:
    """Generates interactive Plotly charts and saves them as HTML."""

    def __init__(self, analyzer, output_dir: str = "output/charts"):
        self.analyzer = analyzer
        self.df = analyzer.merged.copy()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _save(self, fig, name: str):
        """Save a Plotly figure as an interactive HTML file."""
        path = self.output_dir / f"{name}.html"
        fig.write_html(str(path), include_plotlyjs="cdn")
        print(f"   ✅ Saved: {path}")

    def chart_freshness_by_category(self):
        """Stacked bar chart: Freshness status counts by product category."""
        top_cats = self.df["category"].value_counts().head(15).index.tolist()
        filtered = self.df[self.df["category"].isin(top_cats)]

        ct = pd.crosstab(filtered["category"], filtered["freshness_status"])
        ct = ct[[c for c in STATUS_ORDER if c in ct.columns]]

        fig = go.Figure()
        for status in ct.columns:
            fig.add_trace(go.Bar(
                name=status,
                x=ct.index,
                y=ct[status],
                marker_color=STATUS_COLORS.get(status, "#9E9E9E"),
            ))

        fig.update_layout(
            barmode="stack",
            title="📊 Freshness Status Distribution by Product Category (Top 15)",
            xaxis_title="Product Category",
            yaxis_title="Number of Orders",
            template="plotly_dark",
            font=dict(family="Inter, sans-serif", size=13),
            legend_title="Freshness Status",
            height=600,
            margin=dict(b=140),
        )
        fig.update_xaxes(tickangle=-45)
        self._save(fig, "01_freshness_by_category")

    def chart_ageing_heatmap(self):
        """Heatmap: Average delivery delay by category × seller state."""
        delivered = self.df[self.df["order_status"] == "delivered"].copy()
        top_cats = delivered["category"].value_counts().head(12).index.tolist()
        top_states = delivered["seller_state"].value_counts().head(10).index.tolist()

        filtered = delivered[
            delivered["category"].isin(top_cats) &
            delivered["seller_state"].isin(top_states)
        ]

        pivot = filtered.pivot_table(
            values="delivery_delay_days",
            index="category",
            columns="seller_state",
            aggfunc="mean",
        ).round(1)

        fig = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            colorscale=[
                [0, "#00C853"],
                [0.3, "#FFD600"],
                [0.5, "#FF9100"],
                [0.7, "#FF3D00"],
                [1.0, "#D50000"],
            ],
            colorbar_title="Avg Delay (days)",
            text=pivot.values,
            texttemplate="%{text:.1f}",
            textfont={"size": 11},
            hoverongaps=False,
        ))

        fig.update_layout(
            title="🗺️ Ageing Heatmap — Avg Delivery Delay (Category × Seller State)",
            xaxis_title="Seller State",
            yaxis_title="Product Category",
            template="plotly_dark",
            font=dict(family="Inter, sans-serif", size=13),
            height=600,
        )
        self._save(fig, "02_ageing_heatmap")

    def chart_delivery_timeline(self):
        """Scatter plot: Delivery timeline with delay-based coloring."""
        delivered = self.df[
            (self.df["order_status"] == "delivered") &
            self.df["order_delivered_customer_date"].notna()
        ].copy()

        if len(delivered) > 3000:
            delivered = delivered.sample(3000, random_state=42)

        fig = px.scatter(
            delivered,
            x="order_purchase_timestamp",
            y="order_age_days",
            color="freshness_status",
            color_discrete_map=STATUS_COLORS,
            category_orders={"freshness_status": STATUS_ORDER},
            hover_data=["order_id", "category", "delivery_delay_days", "seller_state"],
            opacity=0.6,
            title="📅 Order Delivery Timeline — Purchase Date vs Delivery Time",
        )

        fig.update_layout(
            template="plotly_dark",
            font=dict(family="Inter, sans-serif", size=13),
            xaxis_title="Purchase Date",
            yaxis_title="Total Delivery Time (days)",
            legend_title="Freshness Status",
            height=600,
        )
        self._save(fig, "03_delivery_timeline")

    def chart_risk_pie(self):
        """Pie chart: Proportion of orders by freshness status."""
        status_counts = self.df["freshness_status"].value_counts()

        fig = go.Figure(data=[go.Pie(
            labels=status_counts.index.tolist(),
            values=status_counts.values.tolist(),
            marker_colors=[STATUS_COLORS.get(s, "#9E9E9E") for s in status_counts.index],
            textinfo="label+percent",
            textfont_size=13,
            hole=0.4,
            pull=[0.05 if s in ("Critical", "Expired") else 0 for s in status_counts.index],
        )])

        fig.update_layout(
            title="🎯 Stock-at-Risk — Order Freshness Distribution",
            template="plotly_dark",
            font=dict(family="Inter, sans-serif", size=13),
            height=550,
            annotations=[dict(
                text="Freshness",
                x=0.5, y=0.5,
                font_size=16,
                showarrow=False,
                font_color="white",
            )],
        )
        self._save(fig, "04_risk_pie_chart")

    def chart_delay_histogram(self):
        """Histogram: Distribution of delivery delays."""
        delivered = self.df[
            (self.df["order_status"] == "delivered") &
            self.df["delivery_delay_days"].notna()
        ].copy()

        delivered["delay_clipped"] = delivered["delivery_delay_days"].clip(-30, 60)

        fig = go.Figure()

        on_time = delivered[delivered["delivery_delay_days"] <= 0]
        fig.add_trace(go.Histogram(
            x=on_time["delay_clipped"],
            name="On Time / Early",
            marker_color="#00C853",
            opacity=0.8,
            nbinsx=40,
        ))

        late = delivered[delivered["delivery_delay_days"] > 0]
        fig.add_trace(go.Histogram(
            x=late["delay_clipped"],
            name="Late Delivery",
            marker_color="#FF3D00",
            opacity=0.8,
            nbinsx=40,
        ))

        fig.update_layout(
            barmode="overlay",
            title="📈 Delivery Delay Distribution (Days Early ← 0 → Days Late)",
            xaxis_title="Delivery Delay (days), negative = early",
            yaxis_title="Number of Orders",
            template="plotly_dark",
            font=dict(family="Inter, sans-serif", size=13),
            height=550,
            shapes=[dict(
                type="line", x0=0, x1=0,
                y0=0, y1=1, yref="paper",
                line=dict(color="white", width=2, dash="dash"),
            )],
        )
        self._save(fig, "05_delay_histogram")

    def chart_monthly_trend(self):
        """Dual-axis line chart: Monthly order volume and on-time rate over time."""
        trend = self.analyzer.get_monthly_trend()

        fig = go.Figure()

        # Bar: order volume
        fig.add_trace(go.Bar(
            x=trend.index.tolist(),
            y=trend["total_orders"],
            name="Order Volume",
            marker_color="rgba(99, 110, 250, 0.6)",
            yaxis="y",
        ))

        # Line: on-time rate
        fig.add_trace(go.Scatter(
            x=trend.index.tolist(),
            y=trend["on_time_rate"],
            name="On-Time Rate (%)",
            mode="lines+markers",
            line=dict(color="#00C853", width=3),
            marker=dict(size=7),
            yaxis="y2",
        ))

        # Line: avg freshness score
        fig.add_trace(go.Scatter(
            x=trend.index.tolist(),
            y=trend["avg_freshness_score"],
            name="Avg Freshness Score",
            mode="lines+markers",
            line=dict(color="#FFD600", width=2, dash="dot"),
            marker=dict(size=5),
            yaxis="y2",
        ))

        fig.update_layout(
            title="📆 Monthly Trend — Order Volume vs Delivery Performance",
            template="plotly_dark",
            font=dict(family="Inter, sans-serif", size=13),
            height=550,
            xaxis_title="Month",
            yaxis=dict(
                title="Order Volume",
                side="left",
                showgrid=False,
            ),
            yaxis2=dict(
                title="Rate / Score (%)",
                side="right",
                overlaying="y",
                range=[0, 105],
                showgrid=True,
                gridcolor="rgba(255,255,255,0.1)",
            ),
            legend=dict(x=0.01, y=0.99, bgcolor="rgba(0,0,0,0.5)"),
            margin=dict(b=80),
        )
        fig.update_xaxes(tickangle=-45)
        self._save(fig, "06_monthly_trend")

    def chart_worst_categories(self):
        """Horizontal bar chart: Bottom 10 categories by on-time delivery rate."""
        cat_summary = self.analyzer.get_category_summary()

        # Filter to categories with ≥50 orders for statistical significance
        significant = cat_summary[cat_summary["total_orders"] >= 50]
        worst_10 = significant.nsmallest(10, "on_time_rate")

        colors = []
        for rate in worst_10["on_time_rate"]:
            if rate < 60:
                colors.append("#D50000")
            elif rate < 70:
                colors.append("#FF3D00")
            elif rate < 80:
                colors.append("#FF9100")
            else:
                colors.append("#FFD600")

        fig = go.Figure(go.Bar(
            x=worst_10["on_time_rate"].values,
            y=worst_10.index.tolist(),
            orientation="h",
            marker_color=colors,
            text=[f"{v:.1f}%" for v in worst_10["on_time_rate"]],
            textposition="outside",
            textfont=dict(size=12),
        ))

        fig.update_layout(
            title="🚨 Top 10 Worst Performing Categories (by On-Time Rate)",
            xaxis_title="On-Time Delivery Rate (%)",
            yaxis_title="",
            template="plotly_dark",
            font=dict(family="Inter, sans-serif", size=13),
            height=500,
            xaxis=dict(range=[0, 105]),
            yaxis=dict(autorange="reversed"),
            shapes=[dict(
                type="line", x0=80, x1=80,
                y0=-0.5, y1=9.5,
                line=dict(color="white", width=1.5, dash="dash"),
            )],
            annotations=[dict(
                x=82, y=0, text="80% target",
                showarrow=False, font=dict(color="white", size=10),
            )],
        )
        self._save(fig, "07_worst_categories")

    def chart_seller_radar(self):
        """Radar chart: Top 6 seller states compared across 5 KPIs."""
        state_summary = self.analyzer.get_seller_state_summary()
        top_6 = state_summary.head(6)

        # Normalize metrics to 0-100 scale for radar comparability
        kpis = {
            "On-Time Rate": top_6["on_time_rate"],
            "Freshness Score": top_6["avg_freshness_score"],
            "Processing Speed": (1 / top_6["avg_processing_days"].clip(0.1) * 10).clip(0, 100),
            "Shipping Speed": (1 / top_6["avg_shipping_days"].clip(0.1) * 30).clip(0, 100),
            "Delivery Speed": (1 / top_6["avg_delivery_days"].clip(0.1) * 100).clip(0, 100),
        }

        categories = list(kpis.keys())
        palette = ["#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A", "#19D3F3"]

        fig = go.Figure()

        for i, (state, _) in enumerate(top_6.iterrows()):
            values = [kpis[kpi].loc[state] for kpi in categories]
            values.append(values[0])  # Close the polygon

            fig.add_trace(go.Scatterpolar(
                r=values,
                theta=categories + [categories[0]],
                fill="toself",
                fillcolor=f"rgba({int(palette[i][1:3], 16)},{int(palette[i][3:5], 16)},{int(palette[i][5:7], 16)},0.15)",
                line=dict(color=palette[i], width=2),
                name=f"{state} ({int(top_6.loc[state, 'total_orders']):,} orders)",
            ))

        fig.update_layout(
            title="🕸️ Seller State Performance Radar (Top 6 by Volume)",
            template="plotly_dark",
            font=dict(family="Inter, sans-serif", size=13),
            height=600,
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 100],
                    gridcolor="rgba(255,255,255,0.15)",
                ),
                angularaxis=dict(gridcolor="rgba(255,255,255,0.15)"),
                bgcolor="rgba(0,0,0,0)",
            ),
            legend=dict(x=1.05, y=1),
        )
        self._save(fig, "08_seller_radar")

    def generate_all(self):
        """Generate all 8 charts."""
        print("[5/6] Generating interactive Plotly charts...")

        self.chart_freshness_by_category()
        self.chart_ageing_heatmap()
        self.chart_delivery_timeline()
        self.chart_risk_pie()
        self.chart_delay_histogram()
        self.chart_monthly_trend()
        self.chart_worst_categories()
        self.chart_seller_radar()

        print(f"   All charts saved to: {self.output_dir.resolve()}")
