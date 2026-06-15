# Amazon Review Insight Web

This project now ships as a Docker-deployable tool website built around the existing Amazon review analysis pipeline.

## Architecture

- `scripts/`: existing preprocessing, LLM analysis, and HTML report generation pipeline
- `backend/`: FastAPI API layer backed by Redis + RQ for queued execution, progress tracking, and artifact delivery
- `frontend/`: React + Vite interface centered on one user action: upload reviews and receive finished outputs
- `config/`: runtime and provider configuration for fallback LLM execution
- `docker-compose.yml`: frontend, backend, Redis, and worker services

## Run locally

### Backend

```bash
cd amazon-review-insight
uv sync
uv run uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

### Workers

```bash
cd amazon-review-insight
uv run python backend/run_workers.py
```

### Frontend

```bash
cd amazon-review-insight/frontend
npm install
npm run dev
```

The frontend expects the backend at `/api` during Docker deployment. For standalone Vite development, the local proxy already forwards `/api` and `/files` to `http://127.0.0.1:8000`.

## Deploy with Docker

```bash
cd amazon-review-insight
docker compose up --build
```

- Frontend: `http://localhost:8080`
- Backend API: `http://localhost:8000/api/health`

## Notes

- The backend now queues jobs through Redis + RQ with a default worker concurrency of `2`.
- Live progress includes chunk-level status such as `Processing chunk 7 of 12`.
- The backend reuses `scripts/run_multi_agent_workflow.py` rather than replacing the existing analysis path.
- The default product flow does not require a runtime config upload.
- LLM provider keys are still read from `.env` and `config/provider_registry.json`.
- Output artifacts are written under `runs/<job_id>/`.
