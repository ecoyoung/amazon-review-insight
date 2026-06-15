# Output Schema

## Required Output Files

The default run should produce:

- `workflow_summary.json`
- `analysis_outputs.json`
- `report_outputs.json`
- `preprocess_outputs.json`
- `intake_outputs.json`
- a short chat summary

For compatibility with the existing analysis pipeline, `analysis_outputs.json`
and `preprocess_outputs.json` include paths to the generated files such as:

- selected CSV
- cleaned XLSX
- metadata JSON
- data quality JSON
- analysis JSON
- summary Markdown
- report HTML

## Report Requirements

The report must be:

- English only
- business presentation oriented
- branded with the Amazon Review Insight logo
- understandable to broad stakeholders
- titled `Amazon Review Insight Report`
- subtitled with the input filename without the file extension

Suggested report sections:

1. Executive Summary
2. Review Sample Overview
3. Rating and Trend Signals
4. Customer Personas and Usage Context
5. Key Advantages
6. Key Pain Points
7. Strategic Recommendations
8. Evidence and Method Notes

The Strategic Recommendations section should present the top 3 priorities ranked by importance and actionability, not phased time buckets.

## Footer Guidance

The footer should show the agency name and a neutral methodology note rather than a heavy legal disclaimer.

Recommended style:

- `Prepared by Amazon Review Insight`
- `Based on structured analysis of Amazon review data and model-assisted interpretation.`

## Output Naming

The report filename should align with the report title and subtitle. Do not append date, product name, or ASIN automatically.

## JSON Requirements

`workflow_summary.json` should include:

- top-level `status` (`completed` or `failed`)
- `failure_stage` when failed
- `error` object when failed:
  - `error_code`
  - `error_message`
  - `exception_type`
  - `retry_count`
- `node_executions` for each workflow stage:
  - `status`
  - `duration_ms`
  - `retry_count`
  - `error_code` and `error_message` when failed

The analysis JSON (pointed by `analysis_outputs.json`) should include:

- pipeline metadata
- model/provider metadata
- sample and preprocessing statistics
- KPI metrics
- chart-ready data
- persona findings
- advantage findings
- pain-point findings
- strategy recommendations
- traceability metadata

Advantages and pain points must include both:

- `supporting_review_ids`
- `sample_quotes`

`sample_quotes` must be grounded in the cleaned dataset. A quote is valid only
when the quoted fragment can be matched back to the source review text for the
same `review_id`.

## Data Quality Report

The preprocessing stage should emit a `*-data-quality.json` artifact and expose
its path as `quality_report_json`. It should include:

- source file name
- raw and selected review counts
- detected source format
- source-format method notes
- original-to-standard column mapping
- counts for missing optional reviewer name, unverified reviews, duplicates,
  trivial content, invalid rating, invalid date, and invalid helpful values
- exclusion reason counts
- selection bucket counts

## Runtime Scale Defaults

The default runtime is configured for full-run analysis up to:

- `analysis.chunk_size`: 150 reviews per LLM chunk
- `analysis.max_chunks`: 500 chunks
- `analysis.max_reviews`: 75000 selected reviews
