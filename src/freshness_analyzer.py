"""
Freshness & Ageing Analyzer
============================
Analyzes the Brazilian E-commerce (Olist) dataset to compute order ageing,
delivery freshness, fulfilment pipeline health, and flags at-risk orders.

Key Metrics:
- Order Ageing: How long an order has been in the pipeline
- Delivery Delay: Actual vs estimated delivery difference
- Fulfilment Freshness: Speed of processing from purchase to delivery
- Shelf-Life Consumption: % of estimated delivery window consumed
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime


class FreshnessAnalyzer:
    """Analyzes order freshness, ageing, and delivery performance."""

    # Freshness status thresholds (in days of delay)
    STATUS_THRESHOLDS = {
        "Expired": float("inf"),      # Cancelled / unavailable
        "Critical": 14,               # Delivered >14 days late
        "Warning": 7,                 # Delivered 7-14 days late
        "Caution": 3,                 # Delivered 3-7 days late
        "Good": 0,                    # Delivered 0-3 days late
        "Fresh": float("-inf"),       # Delivered early or on time
    }

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.orders = None
        self.items = None
        self.products = None
        self.categories = None
        self.sellers = None
        self.merged = None

    def load_data(self):
        """Load all required CSV files from the data directory."""
        print("[1/6] Loading datasets...")

        required_files = {
            "orders": "olist_orders_dataset.csv",
            "items": "olist_order_items_dataset.csv",
            "products": "olist_products_dataset.csv",
            "categories": "product_category_name_translation.csv",
            "sellers": "olist_sellers_dataset.csv",
        }

        missing = [f for f in required_files.values()
                   if not (self.data_dir / f).exists()]
        if missing:
            raise FileNotFoundError(
                f"Missing required CSV files in '{self.data_dir}': {missing}\n"
                f"Please ensure all Olist dataset files are in the data directory."
            )

        self.orders = pd.read_csv(self.data_dir / required_files["orders"])
        self.items = pd.read_csv(self.data_dir / required_files["items"])
        self.products = pd.read_csv(self.data_dir / required_files["products"])
        self.categories = pd.read_csv(self.data_dir / required_files["categories"])
        self.sellers = pd.read_csv(self.data_dir / required_files["sellers"])

        print(f"   Loaded {len(self.orders):,} orders, {len(self.items):,} order items, "
              f"{len(self.products):,} products")

        return self

    def _parse_dates(self):
        """Convert all timestamp columns to datetime."""
        date_cols = [
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ]
        for col in date_cols:
            if col in self.orders.columns:
                self.orders[col] = pd.to_datetime(self.orders[col], errors="coerce")

    def _merge_datasets(self):
        """Merge orders with items, products, categories, and sellers."""
        # Merge orders + items
        df = self.orders.merge(self.items, on="order_id", how="left")

        # Merge with products
        df = df.merge(self.products[["product_id", "product_category_name"]],
                      on="product_id", how="left")

        # Merge with English category names
        df = df.merge(self.categories, on="product_category_name", how="left")
        df["category"] = df["product_category_name_english"].fillna(df["product_category_name"])

        # Merge with sellers for location info
        df = df.merge(self.sellers[["seller_id", "seller_city", "seller_state"]],
                      on="seller_id", how="left")

        self.merged = df

    def _compute_ageing_metrics(self):
        """Compute all freshness and ageing columns."""
        df = self.merged.copy()

        # ---- Order Ageing (days from purchase to delivery or to today) ----
        df["order_age_days"] = (
            df["order_delivered_customer_date"] - df["order_purchase_timestamp"]
        ).dt.total_seconds() / 86400

        # For undelivered orders, measure age from purchase to now
        now = pd.Timestamp.now()
        undelivered = df["order_delivered_customer_date"].isna()
        df.loc[undelivered, "order_age_days"] = (
            now - df.loc[undelivered, "order_purchase_timestamp"]
        ).dt.total_seconds() / 86400

        # ---- Delivery Delay (actual - estimated, positive = late) ----
        df["delivery_delay_days"] = (
            df["order_delivered_customer_date"] - df["order_estimated_delivery_date"]
        ).dt.total_seconds() / 86400

        # ---- Processing Time (purchase to carrier handoff) ----
        df["processing_time_days"] = (
            df["order_delivered_carrier_date"] - df["order_purchase_timestamp"]
        ).dt.total_seconds() / 86400

        # ---- Shipping Time (carrier to customer) ----
        df["shipping_time_days"] = (
            df["order_delivered_customer_date"] - df["order_delivered_carrier_date"]
        ).dt.total_seconds() / 86400

        # ---- Shelf-Life Consumption % ----
        estimated_window = (
            df["order_estimated_delivery_date"] - df["order_purchase_timestamp"]
        ).dt.total_seconds() / 86400

        df["shelf_life_pct"] = np.where(
            estimated_window > 0,
            (df["order_age_days"] / estimated_window * 100).clip(0, 200),
            0
        )

        # ---- Freshness Status ----
        conditions = [
            df["order_status"].isin(["canceled", "unavailable"]),
            df["delivery_delay_days"] > 14,
            df["delivery_delay_days"] > 7,
            df["delivery_delay_days"] > 3,
            df["delivery_delay_days"] > 0,
            df["delivery_delay_days"] <= 0,
        ]
        choices = ["Expired", "Critical", "Warning", "Caution", "Good", "Fresh"]
        df["freshness_status"] = np.select(conditions, choices, default="Unknown")

        # For undelivered orders that aren't cancelled — fix with proper indexing
        pending_mask = (
            df["order_delivered_customer_date"].isna() &
            ~df["order_status"].isin(["canceled", "unavailable"])
        )
        past_estimate = pending_mask & (now > df["order_estimated_delivery_date"])

        # Compute days overdue as a column aligned with the DataFrame index
        df["_days_overdue"] = np.nan
        df.loc[past_estimate, "_days_overdue"] = (
            now - df.loc[past_estimate, "order_estimated_delivery_date"]
        ).dt.total_seconds() / 86400

        df.loc[past_estimate & (df["_days_overdue"] > 14), "freshness_status"] = "Critical"
        df.loc[past_estimate & (df["_days_overdue"] > 7) & (df["_days_overdue"] <= 14), "freshness_status"] = "Warning"
        df.loc[past_estimate & (df["_days_overdue"] > 3) & (df["_days_overdue"] <= 7), "freshness_status"] = "Caution"
        df.loc[past_estimate & (df["_days_overdue"] <= 3), "freshness_status"] = "Good"
        df.loc[pending_mask & ~past_estimate, "freshness_status"] = "Fresh"

        # Clean up temp column
        df.drop(columns=["_days_overdue"], inplace=True)

        # ---- Freshness Score (0-100, higher = fresher) ----
        status_scores = {"Fresh": 100, "Good": 75, "Caution": 50, "Warning": 25, "Critical": 10, "Expired": 0, "Unknown": 0}
        df["freshness_score"] = df["freshness_status"].map(status_scores)

        self.merged = df

    def analyze(self):
        """Run the complete analysis pipeline."""
        print("[2/6] Parsing dates...")
        self._parse_dates()

        print("[3/6] Merging datasets...")
        self._merge_datasets()

        print("[4/6] Computing ageing metrics...")
        self._compute_ageing_metrics()

        print(f"   Analysis complete: {len(self.merged):,} records processed")
        return self

    def get_summary_stats(self) -> dict:
        """Return a dictionary of high-level summary statistics."""
        df = self.merged
        delivered = df[df["order_status"] == "delivered"]
        n_delivered = max(len(delivered), 1)  # Guard against ZeroDivisionError

        # Revenue-at-risk: total price of flagged orders
        flagged_mask = df["freshness_status"].isin(["Critical", "Warning", "Expired"])
        revenue_at_risk = float(df.loc[flagged_mask, "price"].sum()) if "price" in df.columns else 0.0
        total_revenue = float(df["price"].sum()) if "price" in df.columns else 0.0

        stats = {
            "total_orders": df["order_id"].nunique(),
            "total_items": len(df),
            "total_products": df["product_id"].nunique(),
            "total_categories": df["category"].nunique(),
            "total_sellers": df["seller_id"].nunique(),

            # Delivery performance
            "avg_delivery_days": round(delivered["order_age_days"].mean(), 1) if n_delivered > 1 else 0.0,
            "median_delivery_days": round(delivered["order_age_days"].median(), 1) if n_delivered > 1 else 0.0,
            "avg_delay_days": round(delivered["delivery_delay_days"].mean(), 1) if n_delivered > 1 else 0.0,
            "on_time_pct": round(
                (delivered["delivery_delay_days"] <= 0).sum() / n_delivered * 100, 1
            ),
            "late_delivery_pct": round(
                (delivered["delivery_delay_days"] > 0).sum() / n_delivered * 100, 1
            ),

            # Processing
            "avg_processing_days": round(delivered["processing_time_days"].mean(), 1) if n_delivered > 1 else 0.0,
            "avg_shipping_days": round(delivered["shipping_time_days"].mean(), 1) if n_delivered > 1 else 0.0,

            # Freshness distribution
            "freshness_distribution": df["freshness_status"].value_counts().to_dict(),

            # At-risk orders
            "critical_orders": int((df["freshness_status"] == "Critical").sum()),
            "warning_orders": int((df["freshness_status"] == "Warning").sum()),
            "expired_orders": int((df["freshness_status"] == "Expired").sum()),

            # Revenue impact
            "revenue_at_risk": round(revenue_at_risk, 2),
            "total_revenue": round(total_revenue, 2),
            "revenue_at_risk_pct": round(
                revenue_at_risk / max(total_revenue, 1) * 100, 1
            ),
        }
        return stats

    def get_flagged_orders(self) -> pd.DataFrame:
        """Return orders flagged as Expired, Critical, or Warning."""
        flagged = self.merged[
            self.merged["freshness_status"].isin(["Expired", "Critical", "Warning"])
        ].copy()

        cols = [
            "order_id", "order_status", "category", "seller_state",
            "order_purchase_timestamp", "order_estimated_delivery_date",
            "order_delivered_customer_date",
            "order_age_days", "delivery_delay_days", "freshness_status",
            "freshness_score", "price",
        ]
        available_cols = [c for c in cols if c in flagged.columns]
        return flagged[available_cols].sort_values("delivery_delay_days", ascending=False)

    def get_category_summary(self) -> pd.DataFrame:
        """Return summary statistics grouped by product category."""
        df = self.merged[self.merged["order_status"] == "delivered"].copy()
        summary = df.groupby("category").agg(
            total_orders=("order_id", "nunique"),
            avg_delivery_days=("order_age_days", "mean"),
            avg_delay_days=("delivery_delay_days", "mean"),
            on_time_rate=("delivery_delay_days", lambda x: (x <= 0).mean() * 100),
            avg_freshness_score=("freshness_score", "mean"),
            total_revenue=("price", "sum"),
        ).round(1).sort_values("total_orders", ascending=False)

        return summary

    def get_seller_state_summary(self) -> pd.DataFrame:
        """Return summary statistics grouped by seller state (warehouse proxy)."""
        df = self.merged[self.merged["order_status"] == "delivered"].copy()
        summary = df.groupby("seller_state").agg(
            total_orders=("order_id", "nunique"),
            avg_delivery_days=("order_age_days", "mean"),
            avg_delay_days=("delivery_delay_days", "mean"),
            avg_processing_days=("processing_time_days", "mean"),
            avg_shipping_days=("shipping_time_days", "mean"),
            on_time_rate=("delivery_delay_days", lambda x: (x <= 0).mean() * 100),
            avg_freshness_score=("freshness_score", "mean"),
        ).round(1).sort_values("total_orders", ascending=False)

        return summary

    def get_monthly_trend(self) -> pd.DataFrame:
        """Return monthly trend of delivery performance."""
        df = self.merged[self.merged["order_status"] == "delivered"].copy()
        df["month"] = df["order_purchase_timestamp"].dt.to_period("M")

        trend = df.groupby("month").agg(
            total_orders=("order_id", "nunique"),
            avg_delivery_days=("order_age_days", "mean"),
            avg_delay_days=("delivery_delay_days", "mean"),
            on_time_rate=("delivery_delay_days", lambda x: (x <= 0).mean() * 100),
            avg_freshness_score=("freshness_score", "mean"),
        ).round(1)

        trend.index = trend.index.astype(str)
        return trend

    def print_summary(self):
        """Print a formatted summary to the console."""
        stats = self.get_summary_stats()

        print("\n" + "=" * 65)
        print("  MT PRODUCT FRESHNESS & AGEING TRACKER — SUMMARY REPORT")
        print("=" * 65)
        print(f"  📦 Total Orders:     {stats['total_orders']:,}")
        print(f"  📋 Total Items:      {stats['total_items']:,}")
        print(f"  🏷️  Total Products:   {stats['total_products']:,}")
        print(f"  📂 Categories:       {stats['total_categories']}")
        print(f"  🏪 Sellers:          {stats['total_sellers']:,}")
        print("-" * 65)
        print("  DELIVERY PERFORMANCE")
        print("-" * 65)
        print(f"  📊 Avg Delivery:     {stats['avg_delivery_days']} days")
        print(f"  📊 Median Delivery:  {stats['median_delivery_days']} days")
        print(f"  ⏱️  Avg Processing:   {stats['avg_processing_days']} days")
        print(f"  🚚 Avg Shipping:     {stats['avg_shipping_days']} days")
        print(f"  ✅ On-Time Rate:     {stats['on_time_pct']}%")
        print(f"  ⚠️  Late Deliveries:  {stats['late_delivery_pct']}%")
        print("-" * 65)
        print("  FRESHNESS STATUS DISTRIBUTION")
        print("-" * 65)
        for status, count in sorted(stats["freshness_distribution"].items()):
            icon = {"Fresh": "🟢", "Good": "🟡", "Caution": "🟠",
                    "Warning": "🔴", "Critical": "🔥", "Expired": "❌"}.get(status, "⚪")
            print(f"  {icon} {status:12s}: {count:,}")
        print("-" * 65)
        print(f"  🚨 Flagged At-Risk:  {stats['critical_orders'] + stats['warning_orders'] + stats['expired_orders']:,}")
        print("-" * 65)
        print("  REVENUE IMPACT")
        print("-" * 65)
        print(f"  💰 Total Revenue:    R$ {stats['total_revenue']:,.2f}")
        print(f"  ⚠️  Revenue at Risk:  R$ {stats['revenue_at_risk']:,.2f} ({stats['revenue_at_risk_pct']}%)")
        print("=" * 65)
