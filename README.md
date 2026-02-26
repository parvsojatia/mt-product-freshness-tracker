# MT Product Freshness & Ageing Tracker

An automated Python pipeline that analyzes supply chain data to track product freshness, delivery ageing, and fulfilment health. Built for Modern Trade (MT) and FMCG supply chain analysis.

## Features

- **Freshness Analysis** — Classifies every order as Fresh / Good / Caution / Warning / Critical / Expired
- **Ageing Metrics** — Order age, delivery delay, processing time, shipping time, shelf-life consumption %
- **8 Interactive Plotly Charts** — Dark-themed, publication-ready HTML visualizations
- **Formatted Excel Report** — 6-sheet workbook with conditional formatting, freeze panes, and auto-filters
- **Revenue-at-Risk** — Quantifies the monetary impact of late/failed deliveries

## Dataset

Uses the [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/olistbr/brazilian-ecommerce) (99,441 orders, 9 CSV files).

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Download dataset (requires Kaggle account)
python -c "import kagglehub; kagglehub.dataset_download('olistbr/brazilian-ecommerce')"

# Run the full pipeline
python main.py
```

## Output

| Output | Location |
|--------|----------|
| 8 Interactive Charts | `output/charts/*.html` |
| Excel Report (6 sheets) | `output/freshness_report.xlsx` |
| Console Summary | stdout |

### Charts
1. Freshness by Category (stacked bar)
2. Ageing Heatmap (category × seller state)
3. Delivery Timeline (scatter)
4. Risk Pie Chart (donut)
5. Delay Distribution (histogram)
6. Monthly Trend (dual-axis line)
7. Worst Performers (horizontal bar)
8. Seller Performance Radar (spider)

### Excel Sheets
1. Dashboard Summary — KPIs, freshness distribution, revenue-at-risk
2. Flagged Orders — Expired, Critical & Warning orders
3. Full Inventory — Top 10,000 orders by risk
4. Category Analysis — Per-category delivery performance
5. Seller State Analysis — Per-state warehouse performance
6. Monthly Trend — Monthly delivery performance over time

## Project Structure

```
supply/
├── main.py                     # Pipeline entry point
├── requirements.txt            # Dependencies
├── data/                       # Olist CSV files
├── src/
│   ├── freshness_analyzer.py   # Core analysis engine
│   ├── visualizer.py           # Plotly chart generator (8 charts)
│   └── excel_reporter.py       # Excel report exporter (6 sheets)
└── output/                     # Generated reports & charts
```

## Tech Stack

- **pandas** — Data manipulation and analysis
- **Plotly** — Interactive visualizations
- **xlsxwriter** — Formatted Excel reports
- **kagglehub** — Dataset download
