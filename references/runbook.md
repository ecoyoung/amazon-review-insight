# amazon-review-insight Runbook

## Prerequisites

1. Python dependencies installed in the environment running this skill.
2. Provider API keys configured through environment variables.
3. Input file includes required columns:
   - `Content`
   - `Rating`
   - `Date`
   - `Helpful`
   - `Name` or `Author`
   - `Verified Purchase`

## Validate Environment

```bash
python3 ci/amazon-review-insight/scripts/check_env.py
```

## Run Workflow

```bash
REVIEW_FILE=/path/to/reviews.csv

python3 ci/amazon-review-insight/scripts/run_multi_agent_workflow.py \
"$REVIEW_FILE"
```

## With Runtime Config Override

```bash
python3 ci/amazon-review-insight/scripts/run_multi_agent_workflow.py \
"$REVIEW_FILE" \
"/path/to/runtime_config.json" \
--outdir "/path/to/runs/my-run"
```

## Troubleshooting

- If workflow returns non-zero status, inspect `workflow_summary.json` in the
  output directory for `failure_stage` and `error` details.
- If no provider is configured, export one of the provider API key variables
  from `references/env.example` and rerun `check_env.py`.
