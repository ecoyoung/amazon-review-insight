#!/usr/bin/env python3
"""Unified runner for amazon-review-insight."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from run_pipeline import run_pipeline


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_config() -> Path:
    return project_root() / "config" / "runtime_config.default.json"


def slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned or "reviews"


def timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def copy_outputs(outputs: dict[str, str], outdir: Path) -> dict[str, str]:
    outdir.mkdir(parents=True, exist_ok=True)
    copied: dict[str, str] = {}
    for name, source in outputs.items():
        source_path = Path(source)
        if not source_path.exists():
            copied[name] = str(source_path)
            continue
        target = outdir / source_path.name
        if source_path.resolve() != target.resolve():
            shutil.copy2(source_path, target)
        copied[name] = str(target)
    return copied


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def build_success_summary(review_file: Path, config_file: Path, outdir: Path, outputs: dict[str, str]) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "project_name": "amazon-review-insight",
        "status": "completed",
        "generated_at": now,
        "review_file": str(review_file),
        "config_file": str(config_file),
        "outdir": str(outdir),
        "artifacts": outputs,
        "failure_stage": None,
        "error": None,
        "node_executions": [
            {"stage": "preprocess", "status": "completed"},
            {"stage": "analysis", "status": "completed"},
            {"stage": "report", "status": "completed"},
        ],
    }


def build_failure_summary(
    review_file: Path,
    config_file: Path,
    outdir: Path,
    exc: BaseException,
) -> dict[str, Any]:
    return {
        "project_name": "amazon-review-insight",
        "status": "failed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "review_file": str(review_file),
        "config_file": str(config_file),
        "outdir": str(outdir),
        "artifacts": {},
        "failure_stage": "pipeline",
        "error": {
            "error_code": type(exc).__name__,
            "error_message": str(exc),
            "traceback": traceback.format_exc(),
        },
        "node_executions": [
            {"stage": "pipeline", "status": "failed", "error": str(exc)},
        ],
    }


def write_artifact_indexes(outdir: Path, outputs: dict[str, str], summary: dict[str, Any]) -> None:
    preprocess = {
        "selected_csv": outputs.get("selected_csv"),
        "cleaned_xlsx": outputs.get("cleaned_xlsx"),
        "metadata_json": outputs.get("metadata_json"),
        "quality_report_json": outputs.get("quality_report_json"),
    }
    analysis = {
        "analysis_json": outputs.get("analysis_json"),
        "summary_md": outputs.get("summary_md"),
    }
    report = {
        "report_html": outputs.get("report_html"),
    }
    intake = {
        "review_file": summary.get("review_file"),
        "config_file": summary.get("config_file"),
        "outdir": summary.get("outdir"),
    }
    write_json(outdir / "preprocess_outputs.json", preprocess)
    write_json(outdir / "analysis_outputs.json", analysis)
    write_json(outdir / "report_outputs.json", report)
    write_json(outdir / "intake_outputs.json", intake)
    write_json(outdir / "workflow_summary.json", summary)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the amazon-review-insight workflow")
    parser.add_argument("review_file", help="Path to the Amazon review CSV/Excel file")
    parser.add_argument("config_file", nargs="?", help="Optional path to the runtime config JSON file")
    parser.add_argument("--outdir", help="Output directory. Defaults to <project>/runs/<input>-<timestamp>")
    parser.add_argument("--resume", action="store_true", help="Accepted for compatibility; not used by the runner")
    parser.add_argument("--max-retries", type=int, default=1, help="Accepted for compatibility; retries are handled per LLM call")
    args = parser.parse_args()

    review_file = Path(args.review_file).expanduser().resolve()
    config_file = Path(args.config_file).expanduser().resolve() if args.config_file else default_config()
    outdir = (
        Path(args.outdir).expanduser().resolve()
        if args.outdir
        else project_root() / "runs" / f"{slugify(review_file.stem)}-{timestamp()}"
    )

    try:
        if not review_file.exists():
            raise FileNotFoundError(f"Review file not found: {review_file}")
        if not config_file.exists():
            raise FileNotFoundError(f"Runtime config not found: {config_file}")
        raw_outputs = run_pipeline(str(review_file), str(config_file))
        outputs = copy_outputs(raw_outputs, outdir)
        summary = build_success_summary(review_file, config_file, outdir, outputs)
        write_artifact_indexes(outdir, outputs, summary)
        print(outdir)
        return 0
    except BaseException as exc:  # noqa: BLE001
        outdir.mkdir(parents=True, exist_ok=True)
        summary = build_failure_summary(review_file, config_file, outdir, exc)
        write_json(outdir / "workflow_summary.json", summary)
        print(outdir)
        print(f"[ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
