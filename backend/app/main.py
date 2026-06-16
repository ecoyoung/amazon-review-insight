from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from rq.job import Job

from .queueing import QUEUE_NAME, get_queue, get_redis, list_job_ids, now_iso, register_job
from .worker_tasks import run_pipeline_job
from .polls import router as polls_router
# Package __init__ already puts scripts/ on sys.path, so these resolve cleanly.
from check_env import DEPENDENCIES, module_status, provider_status
from provider_registry import load_runtime_config, ordered_providers


ROOT_DIR = Path(__file__).resolve().parents[2]
RUNS_DIR = ROOT_DIR / "runs"
UPLOADS_DIR = RUNS_DIR / "uploads"
DEFAULT_CONFIG = ROOT_DIR / "config" / "runtime_config.default.json"


class ArtifactLink(BaseModel):
    name: str
    filename: str
    download_url: str
    preview_url: str | None = None


class JobPayload(BaseModel):
    job_id: str
    status: str
    created_at: str
    updated_at: str
    input_filename: str
    outdir: str | None = None
    error: str | None = None
    summary: dict[str, Any] | None = None
    artifacts: list[ArtifactLink] = Field(default_factory=list)
    progress_pct: int = 0
    current_stage: str | None = None
    status_detail: str | None = None
    chunk_index: int | None = None
    chunk_total: int | None = None


class HealthPayload(BaseModel):
    service: str
    status: str
    timestamp: str
    dependencies: list[dict[str, str | bool]]
    providers: list[dict[str, str | bool]]


RUNS_DIR.mkdir(parents=True, exist_ok=True)
app = FastAPI(
    title="Amazon Review Insight API",
    version="1.0.0",
    description="Web API wrapper for the Amazon review analysis workflow.",
)
app.include_router(polls_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/files", StaticFiles(directory=str(RUNS_DIR)), name="files")

# Live poll mobile page (QR code target during training).
_POLLS_HTML_DIR = ROOT_DIR / "polls"
if _POLLS_HTML_DIR.exists():
    app.mount("/p", StaticFiles(directory=str(_POLLS_HTML_DIR), html=True), name="polls")


def runtime_config() -> dict[str, Any]:
    return load_runtime_config(str(DEFAULT_CONFIG))


def dependency_snapshot() -> list[dict[str, str | bool]]:
    return [{"name": name, "installed": module_status(name)[0], "detail": module_status(name)[1]} for name in DEPENDENCIES]


def provider_snapshot() -> list[dict[str, str | bool]]:
    config = runtime_config()
    providers: list[dict[str, str | bool]] = []
    for name in ordered_providers(config):
        status = provider_status(name, config)
        providers.append(
            {
                "name": name,
                "configured": bool(status["configured"]),
                "model": str(status["model"]),
                "base_url": str(status["base_url"]),
                "api_key_env": str(status["api_key_env"]),
            }
        )
    return providers


def artifact_url_for(path: Path) -> str:
    return f"/api/files/{path.relative_to(ROOT_DIR).as_posix()}"


def preview_url_for(path: Path) -> str | None:
    if path.suffix.lower() == ".html":
        return f"/files/{path.relative_to(RUNS_DIR).as_posix()}"
    return None


def normalize_status(raw_status: str) -> str:
    mapping = {
        "queued": "queued",
        "started": "running",
        "finished": "completed",
        "failed": "failed",
        "deferred": "queued",
    }
    return mapping.get(raw_status, raw_status)


def build_artifacts(meta: dict[str, Any], summary: dict[str, Any] | None) -> list[ArtifactLink]:
    artifact_map = meta.get("artifacts") or (summary or {}).get("artifacts") or {}
    links: list[ArtifactLink] = []
    for name, raw_path in artifact_map.items():
        path = Path(raw_path)
        if not path.exists():
            continue
        links.append(
            ArtifactLink(
                name=name,
                filename=path.name,
                download_url=artifact_url_for(path),
                preview_url=preview_url_for(path),
            )
        )
    return links


def load_summary_from_outdir(outdir: str | None) -> dict[str, Any] | None:
    if not outdir:
        return None
    summary_path = Path(outdir) / "workflow_summary.json"
    if not summary_path.exists():
        return None
    import json

    return json.loads(summary_path.read_text(encoding="utf-8"))


def build_payload(job: Job) -> JobPayload:
    meta = job.meta or {}
    summary = meta.get("summary") or load_summary_from_outdir(meta.get("outdir"))
    return JobPayload(
        job_id=job.id,
        status=normalize_status(job.get_status(refresh=True)),
        created_at=str(meta.get("created_at") or now_iso()),
        updated_at=str(meta.get("updated_at") or meta.get("created_at") or now_iso()),
        input_filename=str(meta.get("input_filename") or job.id),
        outdir=meta.get("outdir"),
        error=meta.get("error"),
        summary=summary,
        artifacts=build_artifacts(meta, summary),
        progress_pct=int(meta.get("progress_pct") or (100 if job.get_status(refresh=False) == "finished" else 0)),
        current_stage=meta.get("current_stage"),
        status_detail=meta.get("status_detail"),
        chunk_index=meta.get("chunk_index"),
        chunk_total=meta.get("chunk_total"),
    )


def fetch_job(job_id: str) -> Job:
    try:
        return Job.fetch(job_id, connection=get_redis())
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail="Job not found") from exc


@app.get("/api/health", response_model=HealthPayload)
def health() -> HealthPayload:
    return HealthPayload(
        service="amazon-review-insight",
        status="ok",
        timestamp=now_iso(),
        dependencies=dependency_snapshot(),
        providers=provider_snapshot(),
    )


@app.get("/api/jobs", response_model=list[JobPayload])
def list_jobs() -> list[JobPayload]:
    payloads: list[JobPayload] = []
    for job_id in list_job_ids():
        try:
            payloads.append(build_payload(fetch_job(job_id)))
        except HTTPException:
            continue
    return payloads


@app.get("/api/jobs/{job_id}", response_model=JobPayload)
def get_job(job_id: str) -> JobPayload:
    return build_payload(fetch_job(job_id))


@app.post("/api/jobs", response_model=JobPayload)
async def create_job(review_file: UploadFile = File(...)) -> JobPayload:
    if not review_file.filename:
        raise HTTPException(status_code=400, detail="Missing review file name")
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    job_id = uuid.uuid4().hex[:12]
    review_path = UPLOADS_DIR / f"{job_id}-{Path(review_file.filename).name}"
    with review_path.open("wb") as handle:
        shutil.copyfileobj(review_file.file, handle)
    outdir = RUNS_DIR / job_id
    outdir.mkdir(parents=True, exist_ok=True)

    queue = get_queue()
    job = queue.enqueue(
        run_pipeline_job,
        str(review_path),
        str(DEFAULT_CONFIG),
        str(outdir),
        job_id=job_id,
        result_ttl=60 * 60 * 24,
        failure_ttl=60 * 60 * 24 * 7,
    )
    job.meta.update(
        {
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "input_filename": review_file.filename,
            "outdir": str(outdir),
            "status": "queued",
            "current_stage": "queued",
            "status_detail": "Queued for analysis.",
            "progress_pct": 1,
        }
    )
    job.save_meta()
    register_job(job_id)
    return build_payload(job)


@app.get("/api/jobs/{job_id}/download")
def download_job_bundle(job_id: str) -> FileResponse:
    payload = build_payload(fetch_job(job_id))
    if payload.status != "completed" or not payload.outdir:
        raise HTTPException(status_code=409, detail="Job outputs are not ready yet")
    outdir = Path(payload.outdir)
    temp_root = Path(tempfile.mkdtemp(prefix=f"{job_id}-bundle-"))
    archive_base = temp_root / f"{payload.input_filename.rsplit('.', 1)[0] or job_id}-outputs"
    archive_path = shutil.make_archive(str(archive_base), "zip", root_dir=str(outdir))
    return FileResponse(archive_path, media_type="application/zip", filename=Path(archive_path).name)


@app.get("/api/files/{relative_path:path}")
def get_file(relative_path: str) -> FileResponse:
    path = (ROOT_DIR / relative_path).resolve()
    if not str(path).startswith(str(ROOT_DIR.resolve())) or not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path)
