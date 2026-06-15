#!/usr/bin/env python3
"""
Run the full Amazon Review Insight pipeline from:
- a review file
- a runtime config file
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable
from llm_analysis import run_analysis
from preprocess import preprocess


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def run_pipeline(
    review_file: str,
    config_file: str,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, str]:
    def emit(**payload: Any) -> None:
        if progress_callback:
            progress_callback(payload)

    config = load_config(config_file)
    analysis_cfg = config.get("analysis", {})
    chunk_size = int(analysis_cfg.get("chunk_size", 150))
    max_chunks = int(analysis_cfg.get("max_chunks", 500))
    max_reviews = int(analysis_cfg.get("max_reviews", chunk_size * max_chunks))

    print("[PIPELINE] Preprocessing review file...", flush=True)
    emit(stage="preprocess", message="Cleaning and validating review data.", progress_pct=8)
    preprocessed = preprocess(review_file, max_reviews=max_reviews, chunk_size=chunk_size)

    print("[PIPELINE] Running LLM analysis...", flush=True)
    emit(stage="analysis", message="Generating insights from review content.", progress_pct=15)
    analysis_outputs = run_analysis(
        preprocessed["selected_csv"],
        config_path=config_file,
        progress_callback=progress_callback,
    )

    print("[PIPELINE] Generating HTML report...", flush=True)
    emit(stage="report", message="Building the final HTML report.", progress_pct=97)
    analysis_json = analysis_outputs["analysis_json"]
    base_name = Path(analysis_json).stem[:-len("-analysis")] if Path(analysis_json).stem.endswith("-analysis") else Path(analysis_json).stem
    subprocess.check_call(
        [
            sys.executable,
            str(Path(__file__).resolve().parent / "generate_report.py"),
            analysis_json,
        ]
    )
    report_path = str(Path(analysis_json).with_name(f"{base_name}-report.html"))
    emit(stage="completed", message="Analysis complete.", progress_pct=100)
    return {
        "selected_csv": preprocessed["selected_csv"],
        "cleaned_xlsx": preprocessed["cleaned_xlsx"],
        "metadata_json": preprocessed["metadata_json"],
        "analysis_json": analysis_json,
        "summary_md": analysis_outputs["summary_md"],
        "report_html": report_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full Amazon Review Insight pipeline")
    parser.add_argument("review_file", help="Path to the Amazon review CSV/Excel file")
    parser.add_argument("config_file", help="Path to the runtime config JSON file")
    args = parser.parse_args()
    outputs = run_pipeline(args.review_file, args.config_file)
    print("[PIPELINE] Completed.")
    for name, path in outputs.items():
        print(f"[OK] {name} -> {path}")


if __name__ == "__main__":
    main()
