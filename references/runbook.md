# Amazon Review Insight Runbook

## Prerequisites

1. Python dependencies installed (`uv sync`).
2. Provider API keys configured through environment variables (or a local `.env`).
3. Input file includes required columns:
   - `Content`
   - `Rating`
   - `Date`
   - `Helpful`
   - `Name` or `Author`
   - `Verified Purchase`

## Validate Environment

From the project root:

```bash
uv run python scripts/check_env.py
```

## Run Workflow

```bash
REVIEW_FILE=/path/to/reviews.csv

uv run python scripts/run_multi_agent_workflow.py "$REVIEW_FILE"
```

## With Runtime Config Override

```bash
uv run python scripts/run_multi_agent_workflow.py \
  "$REVIEW_FILE" \
  "/path/to/runtime_config.json" \
  --outdir "/path/to/runs/my-run"
```

## Troubleshooting

- If the workflow returns a non-zero status, inspect `workflow_summary.json` in the
  output directory for `failure_stage` and `error` details.
- If no provider is configured, export one of the provider API key variables
  from `references/env.example` and rerun `check_env.py`.
