from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rq import get_current_job

from .queueing import now_iso


def run_pipeline_job(review_path: str, config_path: str, outdir: str) -> dict[str, Any]:
    from run_multi_agent_workflow import (
        build_failure_summary,
        build_success_summary,
        copy_outputs,
        run_pipeline,
        write_artifact_indexes,
        write_json,
    )

    job = get_current_job()
    if job is None:
        raise RuntimeError("RQ current job is unavailable")

    review_file = Path(review_path)
    active_config = Path(config_path)
    outdir_path = Path(outdir)
    outdir_path.mkdir(parents=True, exist_ok=True)

    def set_meta(**changes: Any) -> None:
        job.meta.update(changes)
        job.meta["updated_at"] = now_iso()
        job.save_meta()

    def on_progress(payload: dict[str, Any]) -> None:
        set_meta(
            status="running",
            progress_pct=int(payload.get("progress_pct", job.meta.get("progress_pct", 0))),
            current_stage=str(payload.get("stage", "")),
            status_detail=str(payload.get("message", "")),
            chunk_index=payload.get("chunk_index"),
            chunk_total=payload.get("chunk_total"),
            step=payload.get("step"),
            outdir=str(outdir_path),
        )

    set_meta(
        status="running",
        current_stage="queued",
        status_detail="Waiting for worker execution.",
        progress_pct=1,
        outdir=str(outdir_path),
    )
    try:
        raw_outputs = run_pipeline(str(review_file), str(active_config), progress_callback=on_progress)
        outputs = copy_outputs(raw_outputs, outdir_path)
        summary = build_success_summary(review_file, active_config, outdir_path, outputs)
        write_artifact_indexes(outdir_path, outputs, summary)
        set_meta(
            status="completed",
            progress_pct=100,
            current_stage="completed",
            status_detail="Analysis complete.",
            summary=summary,
            artifacts=summary.get("artifacts", {}),
            chunk_index=job.meta.get("chunk_total"),
        )
        return summary
    except BaseException as exc:  # noqa: BLE001
        summary = build_failure_summary(review_file, active_config, outdir_path, exc)
        write_json(outdir_path / "workflow_summary.json", summary)
        set_meta(
            status="failed",
            current_stage="failed",
            status_detail=str(exc),
            error=str(exc),
            summary=summary,
        )
        raise


def load_summary(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
