# Archived Prompt Drafts

This directory holds prompt drafts from earlier design phases of the
`amazon-review-insight` capability that are no longer loaded at runtime.

These files are kept for historical reference and to preserve the design
context. They are not referenced by any code in this repository.

## Why these files exist

During the initial capability design, the three chunk-level extraction
families (personas, advantages, pain points) were drafted as separate
prompts. The runtime pipeline, however, was always implemented with a
single combined prompt per chunk (see `extract.draft.md` in the parent
directory) — the separate drafts were never wired in.

## What was archived

| Archived file | Replacement at runtime |
|---|---|
| `persona.draft.md` | merged into `extract.draft.md` |
| `advantages.draft.md` | merged into `extract.draft.md` |
| `pain-points.draft.md` | merged into `extract.draft.md` |
| `normalization.draft.md` | replaced by an inline LLM call in `scripts/llm_analysis.py::refine_normalization_map` |

## Current active prompt files

- `../extract.draft.md` — combined chunk-level extraction
- `../strategy.draft.md` — recommendation generation
- `../semantics.draft.md` — word-cloud semantic insights

See `../../references/prompt-contract.md` for the canonical prompt families
list and the prompt contract that all active prompts must satisfy.
