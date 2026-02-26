"""
MT Product Freshness & Ageing Tracker
=======================================
Main entry point — orchestrates the full analysis pipeline:
  1. Load Brazilian E-commerce (Olist) dataset
  2. Run freshness & ageing analysis
  3. Generate 5 interactive Plotly charts
  4. Export formatted multi-sheet Excel report
  5. Print summary to console

Dataset: Brazilian E-Commerce Public Dataset by Olist
       (https://www.kaggle.com/olistbr/brazilian-ecommerce)

Usage:
    python main.py                     # Use default data/ directory
    python main.py --data path/to/csv  # Custom data directory
"""

import argparse
import sys
import time
from pathlib import Path

# Ensure the project root is on the path
sys.path.insert(0, str(Path(__file__).parent))

from src.freshness_analyzer import FreshnessAnalyzer
from src.visualizer import Visualizer
from src.excel_reporter import ExcelReporter


def main():
    parser = argparse.ArgumentParser(
        description="MT Product Freshness & Ageing Tracker"
    )
    parser.add_argument(
        "--data", type=str, default="data",
        help="Path to directory containing Olist CSV files (default: data/)"
    )
    parser.add_argument(
        "--output", type=str, default="output",
        help="Path to output directory (default: output/)"
    )
    args = parser.parse_args()

    start_time = time.time()

    print()
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║    MT PRODUCT FRESHNESS & AGEING TRACKER                     ║")
    print("║    Brazilian E-Commerce Supply Chain Analysis                 ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print()

    # --- Step 1 & 2: Load & Analyze ---
    analyzer = FreshnessAnalyzer(data_dir=args.data)
    analyzer.load_data()
    analyzer.analyze()

    # --- Step 3: Generate Charts ---
    chart_dir = str(Path(args.output) / "charts")
    viz = Visualizer(analyzer, output_dir=chart_dir)
    viz.generate_all()

    # --- Step 4: Export Excel Report ---
    report_path = str(Path(args.output) / "freshness_report.xlsx")
    reporter = ExcelReporter(analyzer, output_path=report_path)
    reporter.generate()

    # --- Step 5: Print Summary ---
    analyzer.print_summary()

    elapsed = time.time() - start_time
    print(f"\n⏱️  Pipeline completed in {elapsed:.1f} seconds")
    print(f"📁 Output directory: {Path(args.output).resolve()}")
    print(f"   📊 Charts:  {Path(chart_dir).resolve()}")
    print(f"   📋 Report:  {Path(report_path).resolve()}")
    print()


if __name__ == "__main__":
    main()
