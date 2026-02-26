# syntax=docker/dockerfile:1
# ─────────────────────────────────────────────────────────────────────────────
# MT Product Freshness & Ageing Tracker — Streamlit Dashboard
# ─────────────────────────────────────────────────────────────────────────────
# Build:   docker build -t mt-freshness-tracker .
# Run:     docker run -p 8501:8501 mt-freshness-tracker
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

# Keeps Python from generating .pyc files and enables unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system-level dependencies for openpyxl / Plotly kaleido (if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer cache-friendly)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Streamlit default port
EXPOSE 8501

# Run the dashboard
# --server.address=0.0.0.0  → listen on all interfaces inside the container
# --server.port=8501         → must match EXPOSE above
# --server.headless=true     → suppresses the "Open in browser" prompt
ENTRYPOINT ["streamlit", "run", "app.py", \
            "--server.port=8501", \
            "--server.address=0.0.0.0", \
            "--server.headless=true"]
