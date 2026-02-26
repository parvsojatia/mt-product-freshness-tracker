"""
Formatted Excel Report Exporter
=================================
Exports a multi-sheet, professionally formatted Excel workbook:
  Sheet 1 — Dashboard Summary (key metrics)
  Sheet 2 — Flagged Orders   (expired / critical / warning batches)
  Sheet 3 — Full Inventory   (complete order data with color-coded status)
  Sheet 4 — Category Analysis (pivot summary by product category)
  Sheet 5 — Seller State Analysis (performance by seller state / warehouse)

Uses xlsxwriter for rich formatting: conditional colors, headers, borders,
column widths, number formats, and freeze panes.
"""

import pandas as pd
from pathlib import Path


class ExcelReporter:
    """Generates a formatted, multi-sheet Excel report from analysis results."""

    # Status → background color mapping
    STATUS_COLORS = {
        "Fresh": "#C8E6C9",
        "Good": "#FFF9C4",
        "Caution": "#FFE0B2",
        "Warning": "#FFCDD2",
        "Critical": "#EF9A9A",
        "Expired": "#BDBDBD",
    }

    def __init__(self, analyzer, output_path: str = "output/freshness_report.xlsx"):
        self.analyzer = analyzer
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def generate(self):
        """Generate the complete Excel report."""
        print("[6/6] Exporting formatted Excel report...")

        with pd.ExcelWriter(str(self.output_path), engine="xlsxwriter") as writer:
            workbook = writer.book

            # ---- Shared Formats ----
            fmt_title = workbook.add_format({
                "bold": True, "font_size": 16, "font_color": "#1A237E",
                "bottom": 2, "bottom_color": "#1A237E",
            })
            fmt_header = workbook.add_format({
                "bold": True, "font_size": 11, "bg_color": "#1A237E",
                "font_color": "white", "border": 1, "text_wrap": True,
                "align": "center", "valign": "vcenter",
            })
            fmt_metric_label = workbook.add_format({
                "bold": True, "font_size": 12, "bg_color": "#E8EAF6",
                "border": 1, "indent": 1,
            })
            fmt_metric_value = workbook.add_format({
                "font_size": 12, "bg_color": "#F5F5F5",
                "border": 1, "align": "center", "num_format": "#,##0.0",
            })
            fmt_metric_int = workbook.add_format({
                "font_size": 12, "bg_color": "#F5F5F5",
                "border": 1, "align": "center", "num_format": "#,##0",
            })
            fmt_metric_pct = workbook.add_format({
                "font_size": 12, "bg_color": "#F5F5F5",
                "border": 1, "align": "center", "num_format": "0.0%",
            })
            fmt_number = workbook.add_format({
                "num_format": "#,##0.0", "border": 1, "align": "center",
            })
            fmt_int = workbook.add_format({
                "num_format": "#,##0", "border": 1, "align": "center",
            })
            fmt_date = workbook.add_format({
                "num_format": "yyyy-mm-dd", "border": 1, "align": "center",
            })
            fmt_text = workbook.add_format({
                "border": 1, "text_wrap": True, "valign": "vcenter",
            })
            fmt_section = workbook.add_format({
                "bold": True, "font_size": 13, "bg_color": "#C5CAE9",
                "bottom": 1, "top": 1,
            })

            # Status-colored formats
            status_fmts = {}
            for status, color in self.STATUS_COLORS.items():
                status_fmts[status] = workbook.add_format({
                    "bg_color": color, "border": 1, "align": "center",
                    "bold": True,
                })

            # ========================================
            # Sheet 1: Dashboard Summary
            # ========================================
            self._write_dashboard(writer, workbook, fmt_title, fmt_section,
                                  fmt_metric_label, fmt_metric_value,
                                  fmt_metric_int, fmt_metric_pct, status_fmts)

            # ========================================
            # Sheet 2: Flagged Orders
            # ========================================
            self._write_flagged_orders(writer, workbook, fmt_title, fmt_header,
                                       fmt_text, fmt_number, fmt_date, status_fmts)

            # ========================================
            # Sheet 3: Full Inventory
            # ========================================
            self._write_full_inventory(writer, workbook, fmt_title, fmt_header,
                                       fmt_text, fmt_number, fmt_date, status_fmts)

            # ========================================
            # Sheet 4: Category Analysis
            # ========================================
            self._write_category_analysis(writer, workbook, fmt_title, fmt_header,
                                          fmt_number, fmt_int, fmt_text)

            # ========================================
            # Sheet 5: Seller State Analysis
            # ========================================
            self._write_seller_analysis(writer, workbook, fmt_title, fmt_header,
                                        fmt_number, fmt_int, fmt_text)

            # ========================================
            # Sheet 6: Monthly Trend
            # ========================================
            self._write_monthly_trend(writer, workbook, fmt_title, fmt_header,
                                      fmt_number, fmt_int, fmt_text)

        print(f"   ✅ Report saved to: {self.output_path.resolve()}")

    def _write_dashboard(self, writer, workbook, fmt_title, fmt_section,
                         fmt_label, fmt_val, fmt_int, fmt_pct, status_fmts):
        """Write the Dashboard Summary sheet."""
        ws = workbook.add_worksheet("Dashboard Summary")
        writer.sheets["Dashboard Summary"] = ws
        ws.hide_gridlines(2)
        ws.set_column("A:A", 32)
        ws.set_column("B:B", 20)
        ws.set_tab_color("#1A237E")

        stats = self.analyzer.get_summary_stats()

        row = 0
        ws.write(row, 0, "MT PRODUCT FRESHNESS & AGEING TRACKER", fmt_title)
        ws.merge_range(row, 0, row, 1, "MT PRODUCT FRESHNESS & AGEING TRACKER", fmt_title)
        row += 2

        # Overview
        ws.write(row, 0, "📦 OVERVIEW", fmt_section)
        ws.write(row, 1, "", fmt_section)
        row += 1

        metrics = [
            ("Total Orders", stats["total_orders"], fmt_int),
            ("Total Order Items", stats["total_items"], fmt_int),
            ("Unique Products", stats["total_products"], fmt_int),
            ("Product Categories", stats["total_categories"], fmt_int),
            ("Total Sellers", stats["total_sellers"], fmt_int),
        ]
        for label, val, fmt in metrics:
            ws.write(row, 0, label, fmt_label)
            ws.write(row, 1, val, fmt)
            row += 1

        row += 1

        # Delivery Performance
        ws.write(row, 0, "🚚 DELIVERY PERFORMANCE", fmt_section)
        ws.write(row, 1, "", fmt_section)
        row += 1

        delivery_metrics = [
            ("Avg Delivery Time (days)", stats["avg_delivery_days"], fmt_val),
            ("Median Delivery Time (days)", stats["median_delivery_days"], fmt_val),
            ("Avg Processing Time (days)", stats["avg_processing_days"], fmt_val),
            ("Avg Shipping Time (days)", stats["avg_shipping_days"], fmt_val),
            ("On-Time Delivery Rate (%)", stats["on_time_pct"], fmt_val),
            ("Late Delivery Rate (%)", stats["late_delivery_pct"], fmt_val),
        ]
        for label, val, fmt in delivery_metrics:
            ws.write(row, 0, label, fmt_label)
            ws.write(row, 1, val, fmt)
            row += 1

        row += 1

        # Freshness distribution
        ws.write(row, 0, "🎯 FRESHNESS STATUS DISTRIBUTION", fmt_section)
        ws.write(row, 1, "", fmt_section)
        row += 1

        for status in ["Fresh", "Good", "Caution", "Warning", "Critical", "Expired"]:
            count = stats["freshness_distribution"].get(status, 0)
            ws.write(row, 0, status, fmt_label)
            fmt_s = status_fmts.get(status, fmt_int)
            ws.write(row, 1, count, fmt_s)
            row += 1

        row += 1

        # At-Risk summary
        ws.write(row, 0, "🚨 AT-RISK ORDERS", fmt_section)
        ws.write(row, 1, "", fmt_section)
        row += 1

        at_risk = [
            ("Critical Orders (>14 days late)", stats["critical_orders"], status_fmts["Critical"]),
            ("Warning Orders (7-14 days late)", stats["warning_orders"], status_fmts["Warning"]),
            ("Expired / Cancelled", stats["expired_orders"], status_fmts["Expired"]),
        ]
        for label, val, fmt in at_risk:
            ws.write(row, 0, label, fmt_label)
            ws.write(row, 1, val, fmt)
            row += 1

        row += 1

        # Revenue-at-Risk
        ws.write(row, 0, "💰 REVENUE IMPACT", fmt_section)
        ws.write(row, 1, "", fmt_section)
        row += 1

        revenue_metrics = [
            ("Total Revenue (R$)", stats["total_revenue"], fmt_val),
            ("Revenue at Risk (R$)", stats["revenue_at_risk"], fmt_val),
            ("Revenue at Risk (%)", stats["revenue_at_risk_pct"], fmt_val),
        ]
        for label, val, fmt in revenue_metrics:
            ws.write(row, 0, label, fmt_label)
            ws.write(row, 1, val, fmt)
            row += 1

    def _write_flagged_orders(self, writer, workbook, fmt_title, fmt_header,
                              fmt_text, fmt_number, fmt_date, status_fmts):
        """Write the Flagged Orders sheet."""
        flagged = self.analyzer.get_flagged_orders()

        ws = workbook.add_worksheet("Flagged Orders")
        writer.sheets["Flagged Orders"] = ws
        ws.set_tab_color("#D50000")

        # Title
        ws.merge_range(0, 0, 0, len(flagged.columns) - 1,
                       "⚠️ FLAGGED ORDERS — Expired, Critical & Warning", fmt_title)

        # Write header row
        for j, col in enumerate(flagged.columns):
            ws.write(1, j, col, fmt_header)

        # Write data
        for i, (_, row_data) in enumerate(flagged.head(5000).iterrows()):
            for j, col in enumerate(flagged.columns):
                val = row_data[col]
                if pd.isna(val):
                    ws.write(i + 2, j, "", fmt_text)
                elif col == "freshness_status":
                    fmt = status_fmts.get(str(val), fmt_text)
                    ws.write(i + 2, j, str(val), fmt)
                elif col in ("delivery_delay_days", "order_age_days", "freshness_score", "price"):
                    ws.write(i + 2, j, float(val), fmt_number)
                elif "timestamp" in col or "date" in col:
                    ws.write(i + 2, j, str(val)[:19], fmt_text)
                else:
                    ws.write(i + 2, j, str(val), fmt_text)

        # Auto-fit columns
        for j, col in enumerate(flagged.columns):
            ws.set_column(j, j, max(len(str(col)) + 4, 15))

        ws.freeze_panes(2, 0)
        ws.autofilter(1, 0, len(flagged) + 1, len(flagged.columns) - 1)

    def _write_full_inventory(self, writer, workbook, fmt_title, fmt_header,
                              fmt_text, fmt_number, fmt_date, status_fmts):
        """Write the Full Inventory sheet (sampled for performance)."""
        cols = [
            "order_id", "order_status", "category", "seller_state",
            "order_purchase_timestamp", "order_estimated_delivery_date",
            "order_delivered_customer_date",
            "order_age_days", "delivery_delay_days", "processing_time_days",
            "shipping_time_days", "shelf_life_pct", "freshness_status",
            "freshness_score", "price",
        ]
        available_cols = [c for c in cols if c in self.analyzer.merged.columns]
        full = self.analyzer.merged[available_cols].copy()

        # Sort by freshness score (worst first)
        full = full.sort_values("freshness_score", ascending=True).head(10000)

        ws = workbook.add_worksheet("Full Inventory")
        writer.sheets["Full Inventory"] = ws
        ws.set_tab_color("#1565C0")

        ws.merge_range(0, 0, 0, len(available_cols) - 1,
                       "📋 FULL ORDER INVENTORY (Top 10,000 by risk)", fmt_title)

        for j, col in enumerate(available_cols):
            ws.write(1, j, col, fmt_header)

        for i, (_, row_data) in enumerate(full.iterrows()):
            for j, col in enumerate(available_cols):
                val = row_data[col]
                if pd.isna(val):
                    ws.write(i + 2, j, "", fmt_text)
                elif col == "freshness_status":
                    fmt = status_fmts.get(str(val), fmt_text)
                    ws.write(i + 2, j, str(val), fmt)
                elif col in ("order_age_days", "delivery_delay_days", "processing_time_days",
                             "shipping_time_days", "shelf_life_pct", "freshness_score", "price"):
                    ws.write(i + 2, j, float(val), fmt_number)
                elif "timestamp" in col or "date" in col:
                    ws.write(i + 2, j, str(val)[:19], fmt_text)
                else:
                    ws.write(i + 2, j, str(val), fmt_text)

        for j, col in enumerate(available_cols):
            ws.set_column(j, j, max(len(str(col)) + 4, 15))

        ws.freeze_panes(2, 0)
        ws.autofilter(1, 0, min(len(full), 10000) + 1, len(available_cols) - 1)

    def _write_category_analysis(self, writer, workbook, fmt_title, fmt_header,
                                 fmt_number, fmt_int, fmt_text):
        """Write the Category Analysis sheet."""
        cat_summary = self.analyzer.get_category_summary()

        ws = workbook.add_worksheet("Category Analysis")
        writer.sheets["Category Analysis"] = ws
        ws.set_tab_color("#2E7D32")

        ws.merge_range(0, 0, 0, len(cat_summary.columns),
                       "📂 CATEGORY-WISE DELIVERY PERFORMANCE", fmt_title)

        # Header
        ws.write(1, 0, "Category", fmt_header)
        for j, col in enumerate(cat_summary.columns):
            ws.write(1, j + 1, col, fmt_header)

        # Data
        for i, (cat, row_data) in enumerate(cat_summary.iterrows()):
            ws.write(i + 2, 0, str(cat), fmt_text)
            for j, col in enumerate(cat_summary.columns):
                val = row_data[col]
                if col in ("total_orders",):
                    ws.write(i + 2, j + 1, int(val) if not pd.isna(val) else 0, fmt_int)
                elif col == "total_revenue":
                    ws.write(i + 2, j + 1, float(val) if not pd.isna(val) else 0, fmt_number)
                else:
                    ws.write(i + 2, j + 1, float(val) if not pd.isna(val) else 0, fmt_number)

        ws.set_column("A:A", 30)
        for j in range(len(cat_summary.columns)):
            ws.set_column(j + 1, j + 1, 18)

        ws.freeze_panes(2, 1)

    def _write_seller_analysis(self, writer, workbook, fmt_title, fmt_header,
                               fmt_number, fmt_int, fmt_text):
        """Write the Seller State Analysis sheet."""
        state_summary = self.analyzer.get_seller_state_summary()

        ws = workbook.add_worksheet("Seller State Analysis")
        writer.sheets["Seller State Analysis"] = ws
        ws.set_tab_color("#F57F17")

        ws.merge_range(0, 0, 0, len(state_summary.columns),
                       "🏪 SELLER STATE (WAREHOUSE) PERFORMANCE", fmt_title)

        ws.write(1, 0, "Seller State", fmt_header)
        for j, col in enumerate(state_summary.columns):
            ws.write(1, j + 1, col, fmt_header)

        for i, (state, row_data) in enumerate(state_summary.iterrows()):
            ws.write(i + 2, 0, str(state), fmt_text)
            for j, col in enumerate(state_summary.columns):
                val = row_data[col]
                if col in ("total_orders",):
                    ws.write(i + 2, j + 1, int(val) if not pd.isna(val) else 0, fmt_int)
                else:
                    ws.write(i + 2, j + 1, float(val) if not pd.isna(val) else 0, fmt_number)

        ws.set_column("A:A", 16)
        for j in range(len(state_summary.columns)):
            ws.set_column(j + 1, j + 1, 20)

        ws.freeze_panes(2, 1)

    def _write_monthly_trend(self, writer, workbook, fmt_title, fmt_header,
                              fmt_number, fmt_int, fmt_text):
        """Write the Monthly Trend sheet."""
        trend = self.analyzer.get_monthly_trend()

        ws = workbook.add_worksheet("Monthly Trend")
        writer.sheets["Monthly Trend"] = ws
        ws.set_tab_color("#6A1B9A")

        ws.merge_range(0, 0, 0, len(trend.columns),
                       "📆 MONTHLY DELIVERY PERFORMANCE TREND", fmt_title)

        ws.write(1, 0, "Month", fmt_header)
        for j, col in enumerate(trend.columns):
            ws.write(1, j + 1, col, fmt_header)

        for i, (month, row_data) in enumerate(trend.iterrows()):
            ws.write(i + 2, 0, str(month), fmt_text)
            for j, col in enumerate(trend.columns):
                val = row_data[col]
                if col in ("total_orders",):
                    ws.write(i + 2, j + 1, int(val) if not pd.isna(val) else 0, fmt_int)
                else:
                    ws.write(i + 2, j + 1, float(val) if not pd.isna(val) else 0, fmt_number)

        ws.set_column("A:A", 14)
        for j in range(len(trend.columns)):
            ws.set_column(j + 1, j + 1, 20)

        ws.freeze_panes(2, 1)
