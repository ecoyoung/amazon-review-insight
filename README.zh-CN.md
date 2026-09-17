**简体中文** | [English](README.md)

# Amazon Review Insight Web

本项目现在作为一个可通过 Docker 部署的工具网站发布，围绕既有的 Amazon 评论分析流水线构建。

## 架构

- `scripts/`：既有的预处理、LLM 分析与 HTML 报告生成流水线
- `backend/`：基于 Redis + RQ 的 FastAPI API 层，提供队列执行、进度跟踪与产物交付
- `frontend/`：React + Vite 界面，围绕一个核心用户操作设计：上传评论并获得成品输出
- `config/`：用于回退 LLM 执行的运行时与提供商配置
- `docker-compose.yml`：frontend、backend、Redis 与 worker 服务

## 本地运行

### 后端

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

### 前端

```bash
cd amazon-review-insight/frontend
npm install
npm run dev
```

在 Docker 部署时，前端期望后端位于 `/api`。在独立的 Vite 开发模式下，本地代理已将 `/api` 和 `/files` 转发到 `http://127.0.0.1:8000`。

## 使用 Docker 部署

```bash
cd amazon-review-insight
docker compose up --build
```

- Frontend: `http://localhost:8080`
- Backend API: `http://localhost:8000/api/health`

## 说明

- 后端现在通过 Redis + RQ 对任务进行排队，默认 worker 并发数为 `2`。
- 实时进度包含分块（chunk）级状态，例如 `Processing chunk 7 of 12`。
- 后端复用 `scripts/run_multi_agent_workflow.py`，而非替换现有的分析路径。
- 默认的产品流程无需上传运行时配置。
- LLM 提供商密钥仍从 `.env` 和 `config/provider_registry.json` 读取。
- 输出产物写入 `runs/<job_id>/` 目录下。
