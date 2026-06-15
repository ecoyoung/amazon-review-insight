# Prompt Contract

This file defines what the prompts must accomplish and captures the current confirmed prompt direction.

The user asked to confirm LLM prompts before they are finalized. Treat the prompt text files as reviewable drafts, not frozen final copy.

## Prompt Families

The workflow uses these prompt files, all loaded by `load_prompt_sections` from
`config/prompts/`:

1. `extract.draft.md` — combined chunk-level extraction (personas + advantages + pain points) in one LLM call per chunk
2. `strategy.draft.md` — recommendation generation from validated findings
3. `semantics.draft.md` — word-cloud semantic insights (final LLM call before reporting)

In addition, an inline normalization LLM call is invoked by
`refine_normalization_map` in `scripts/llm_analysis.py` to reconcile
near-duplicate labels after chunk-level extraction. The historical
`normalization.draft.md` file in `config/prompts/archive/` captures the
original draft for that work; it is not loaded at runtime.

The earlier `persona.draft.md`, `advantages.draft.md`, and
`pain-points.draft.md` files have been archived for historical reference.
The runtime has always used the merged prompt; those files were design
artifacts that were never loaded by the pipeline.

## Common Prompt Requirements

Every prompt should:

- operate on structured review chunks with stable `review_id`
- return strict JSON
- avoid unsupported claims
- prefer evidence-backed findings over fluent generalities
- work in English output mode
- support business-report wording
- optimize for precision first rather than breadth first
- avoid over-fragmented taxonomies by merging close synonyms aggressively when evidence supports it

## Required Output Behaviors

### Persona Prompt

Must produce:

- commerce-relevant persona label
- detailed Amazon-style consumer profile when evidence supports it
- short usage context
- supporting review IDs
- coverage or count

Persona labels should be closer to shopper and use-case segments such as interest-, need-, or lifestyle-based buyer groups, not generic demographic guesses. Avoid inventing sensitive attributes unless the review evidence clearly supports the label.
Do not infer age, gender, medical condition, or similar sensitive traits unless the reviewer explicitly self-identifies them in the review text.

### Advantage Prompt

Must produce:

- normalized advantage label
- concise business explanation
- supporting review IDs
- sample quotes tied to real IDs
- count or coverage metric
- rankable output suitable for a final Top 8 list

### Pain-Point Prompt

Must produce:

- normalized pain-point label
- concise business explanation
- supporting review IDs
- sample quotes tied to real IDs
- count or coverage metric
- rankable output suitable for a final Top 8 list

Advantages and pain points should use strict synonym consolidation so the final lists do not contain overlapping near-duplicates.

### Strategy Prompt

Must produce:

- product recommendations
- marketing recommendations
- risk mitigation recommendations
- reasoning tied back to validated findings

Recommendation tone should be agency-style, consultative, soft, and tactful. Prefer language such as `may indicate`, `suggests an opportunity to`, or `could help improve`.
Recommendations should be ranked by importance and actionability, and the final report should show the top 3 priorities.

## Quote Rules

- show `review_id`
- show only the key supporting fragment, not the full review
- keep quotes concise for report readability
- preserve original meaning even when trimming

## Confirmed Decisions

These decisions are now confirmed:

- taxonomy normalization should be strict and aggressively merge close synonyms
- persona labels should be commerce- and product-context specific for Amazon review analysis
- recommendation tone should be consultative, tactful, and agency-appropriate
- quotes should show IDs and partial key fragments
- prompts should optimize for precision first
- persona prompts should explicitly forbid sensitive-trait inference unless self-declared
- advantage and pain-point reporting should target a final Top 8
- strategy output should converge to the top 3 priorities rather than time buckets

## Remaining Open Point

One implementation detail still needs to be handled carefully in code and prompt design:

- persona extraction should likely use a hybrid approach, where LLM proposes detailed commerce personas and a downstream normalization layer reconciles near-duplicates before reporting

The drafts should reflect this hybrid assumption.
