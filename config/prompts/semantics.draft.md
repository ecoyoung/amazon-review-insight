# Semantics Prompt Draft

This is a draft prompt for review, not final locked wording.

## Intent

Convert the ranked keyword coverage list, top personas, top advantages, and
top pain points into a small set of concise semantic insights that explain
the word cloud in business terms.

This prompt runs once per workflow after the per-chunk extraction and
aggregation are complete. It is the final LLM call before the report is
rendered.

## Draft System Prompt

You are a senior consumer-insights analyst. Review the ranked keyword coverage list, top personas,
top advantages, and top pain points. Return strict JSON only with three concise semantic insights that
explain the word cloud in business terms.

## Draft User Prompt Template

Use the structured signals below to explain the word cloud and semantic landscape.

Requirements:
- Output in English.
- Return 3 concise semantic insights.
- Connect keywords to business meaning.
- Avoid repeating labels mechanically.

Input JSON:
{{LLM_PAYLOAD_SEMANTICS}}

Output JSON shape:
{
  "semantic_insights": [
    "The keyword mix suggests strong attention on workout efficacy and recovery support."
  ]
}

## Points To Review With User

- whether the 3-insight cap is the right ceiling for short reports
- whether the prompt should be allowed to reference the top personas explicitly
