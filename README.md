# MT Product Freshness & Ageing Tracker

An automated Python pipeline that analyzes supply chain data to track product freshness, delivery ageing, and fulfilment health. Built for Modern Trade (MT) and FMCG supply chain analysis.

## Features

- **Freshness Analysis** — Classifies every order as Fresh / Good / Caution / Warning / Critical / Expired
- **Ageing Metrics** — Order age, delivery delay, processing time, shipping time, shelf-life consumption %
- **Streamlit Dashboard** — Interactive dark-mode dashboard with live filters, KPI cards, and 4 Plotly charts
- **8 Static Plotly Charts** — Dark-themed, publication-ready HTML visualizations
- **Formatted Excel Report** — 6-sheet workbook with conditional formatting, freeze panes, and auto-filters
- **Revenue-at-Risk** — Quantifies the monetary impact of late/failed deliveries
- **Docker & Streamlit Cloud ready** — One-command deployment, synthetic demo data for offline use

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
├── app.py                          # Streamlit dashboard entry point
├── main.py                         # CLI pipeline entry point
├── requirements.txt                # Production dependencies
├── requirements-dev.txt            # Dev dependencies (pytest, black, ruff)
├── Dockerfile                      # Container deployment
├── .streamlit/
│   └── config.toml                 # Dark theme & server config
├── data/                           # Olist CSV files (not committed)
├── src/
│   ├── freshness_analyzer.py       # Core analysis engine
│   ├── visualizer.py               # Plotly chart generator (8 charts)
│   ├── excel_reporter.py           # Excel report exporter (6 sheets)
│   └── dashboard/
│       ├── data_loader.py          # Data ingestion & caching
│       ├── filters.py              # Sidebar filter widgets
│       ├── kpi_cards.py            # KPI metric cards
│       └── charts.py               # Plotly chart functions
└── output/                         # Generated reports & charts
```

## Tech Stack

| Tool | Purpose |
|---|---|
| **Streamlit** | Interactive dashboard UI |
| **Plotly** | Interactive charts (dashboard + static exports) |
| **pandas** | Data manipulation and analysis |
| **openpyxl / xlsxwriter** | Formatted Excel reports |
| **kagglehub** | Dataset download |
| **Docker** | Container deployment |

---

## 🚀 Running the Dashboard

### Local (recommended for development)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. (Optional) Download the Olist dataset for live data
python -c "import kagglehub; kagglehub.dataset_download('olistbr/brazilian-ecommerce')"
# Then move the CSV files into the data/ folder.
# Without this step the dashboard runs on 600-row synthetic demo data.

# 3. Launch the dashboard
streamlit run app.py
# Opens: http://localhost:8501
```

### Docker

```bash
# Build the image
docker build -t mt-freshness-tracker .

# Run (dashboard available at http://localhost:8501)
docker run -p 8501:8501 mt-freshness-tracker

# With your local data/ folder mounted (for live data)
docker run -p 8501:8501 -v "$(pwd)/data:/app/data" mt-freshness-tracker
```

### Streamlit Community Cloud

1. Push this repository to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in.
3. Click **New app** → select your repo → set **Main file path** to `app.py`.
4. Click **Deploy**.

> **Note:** The Kaggle dataset is not committed to the repo. The deployed app will
> automatically fall back to realistic synthetic demo data (600 rows). To use live
> data, add your CSVs to a private [Streamlit Secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)
> or connect a cloud storage bucket.

### Development setup

```bash
# Install dev tools (pytest, black, ruff, mypy)
pip install -r requirements-dev.txt

# Format code
black .

# Run linter
ruff check .

# Run tests
pytest
```
