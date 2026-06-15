# Amazon Review Insight Output Contract

## Module Runner

- Command: `scripts/run_multi_agent_workflow.py` (run from the project root)
- Canonical engine:
  `scripts/run_multi_agent_workflow.py`

## Expected Artifacts

The canonical workflow writes an output directory and should include:

- `workflow_summary.json`
- `analysis_outputs.json`
- `report_outputs.json`
- `preprocess_outputs.json`
- `intake_outputs.json`

`preprocess_outputs.json` includes the selected CSV, cleaned XLSX,
preprocessing metadata JSON, and optional data quality JSON paths.

## Exit Semantics

- Exit `0`: workflow completed.
- Exit non-zero: workflow failed; inspect `workflow_summary.json` for:
  - `failure_stage`
  - `error.error_code`
  - `error.error_message`

## Diagnostic Contract

- `scripts/check_env.py` runs the canonical environment checker and reports:
  - dependency status
  - provider status
  - asset checks

## Evidence Contract

Report quotes must be traceable to the cleaned dataset: a quote is accepted only
when its text fragment matches the source review text for the same `review_id`.

## Runtime Scale Defaults

- `analysis.chunk_size`: 150 reviews per LLM chunk
- `analysis.max_chunks`: 500 chunks
- `analysis.max_reviews`: 75000 selected reviews

SellerSprite-format exports are detected automatically. For those runs, the
English report includes a method note explaining that SellerSprite data may use
a star-balanced sampling strategy, so rating distribution should not be treated
as the product's natural Amazon rating distribution.
