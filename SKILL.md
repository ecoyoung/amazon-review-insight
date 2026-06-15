---
name: amazon-review-insight
description: Analyze Amazon review CSV or Excel exports and generate a report, analysis JSON, cleaned XLSX, and summary. Use when the user asks to analyze Amazon reviews, SellerSprite review exports, review sentiment, advantages, pain points, personas, rating trends, word clouds, or recommendation actions from files with columns such as Content, Rating, Date, Helpful, Name or Author, and Verified Purchase. Do not use for generic web scraping, live Amazon browsing, or non-review datasets.
---

# Amazon Review Insight

## Overview

Use this skill to run and troubleshoot a standalone Amazon review insight workflow. The skill includes its own scripts, prompts, config schemas, provider registry, and report assets.

## Quick Start

From the repository root, validate the environment first:

```bash
python3 ci/amazon-review-insight/scripts/check_env.py
```

Run the workflow with a review CSV:

```bash
python3 ci/amazon-review-insight/scripts/run_multi_agent_workflow.py /path/to/reviews.csv
```

Use a runtime config override or custom output directory when needed:

```bash
python3 ci/amazon-review-insight/scripts/run_multi_agent_workflow.py \
  /path/to/reviews.csv \
  /path/to/runtime_config.json \
  --outdir /path/to/output/run
```

## Workflow

1. Confirm the input file has the required review columns: `Content`, `Rating`, `Date`, `Helpful`, `Name` or `Author`, and `Verified Purchase`.
2. Run `scripts/check_env.py` before the first workflow run or when provider/config errors appear.
3. Run `scripts/run_multi_agent_workflow.py` with the CSV path, optional runtime config, and optional `--outdir`.
4. Inspect the output directory returned by the runner. For failures, read `workflow_summary.json` first.

## References

- Read `references/runbook.md` for detailed operation and troubleshooting steps.
- Read `references/output-contract.md` when validating generated artifacts or failure semantics.
- Use `references/env.example` as the environment template for provider keys.

## Notes

The scripts resolve resources relative to this skill directory. The skill can be moved out of the original monorepo as long as its internal folder structure is preserved.
