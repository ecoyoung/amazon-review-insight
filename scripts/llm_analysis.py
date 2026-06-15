#!/usr/bin/env python3
"""
LLM-powered semantic analysis for Amazon reviews.

This script expects the selected CSV exported by preprocess.py and produces:

- a structured JSON analysis result
- a short markdown summary

It uses configurable providers with automatic fallback:
DeepSeek -> Gemini -> Qwen -> MiniMax
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from provider_registry import (
    FALLBACK_CHAIN,
    load_runtime_config,
    ordered_providers,
    resolve_provider_settings,
)

try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage
except ImportError as exc:
    raise SystemExit(
        "[ERROR] Missing dependency: langchain_openai and langchain_core. "
        "Install them via `uv sync` before running the pipeline."
    ) from exc


STOP_WORDS = set(
    """
i me my myself we our ours ourselves you your yours yourself yourselves he him his
himself she her hers herself it its itself they them their theirs themselves what which
who whom this that these those am is are was were be been being have has had having do
does did doing a an the and but if or because as until while of at by for with about
against between through during before after above below to from up down in out on off
over under again further then once here there when where why how all both each few more
most other some such no nor not only own same so than too very s t can will just don
should now d ll m o re ve y ain aren couldn didn doesn hadn hasn haven isn ma mightn
mustn needn shan shouldn wasn weren won wouldn would could also really much got get one
two like use used using even still thing things way well go going went make made
product item bought buy got good great just really very much well also would could
able about above after again against all am an and any are as at be because been before
being below between both but by can cannot could did do does doing down during each few
for from further had has have having he her here hers herself him himself his how i if
in into is it its itself let me more most my myself no nor not of off on once only or
other ought our ours ourselves out over own same she should so some such than that the
their theirs them themselves then there these they this those through to too under until
up very was we were what when where which while who whom why with would you your yours
yourself yourselves
""".split()
)

REPORT_LANGUAGE = "English"
REPORT_STYLE = "Business presentation"
TOP_FINDINGS = 8
TOP_PRIORITIES = 3
DEFAULT_CHUNK_SIZE = 150
DEFAULT_MAX_CHUNKS = 500
MAX_QUOTES = 2


def load_reviews(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig")
    df["review_id"] = pd.to_numeric(df["review_id"], errors="coerce").astype(int)
    df["Rating"] = pd.to_numeric(df["Rating"], errors="coerce").fillna(3.0)
    df["Helpful"] = pd.to_numeric(df["Helpful"], errors="coerce").fillna(0).astype(int)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["chunk_id"] = pd.to_numeric(df["chunk_id"], errors="coerce").fillna(0).astype(int)
    df["Content"] = df["Content"].fillna("").astype(str)
    return df.sort_values("review_id").reset_index(drop=True)


def load_metadata(csv_path: str) -> dict[str, Any]:
    csv_file = Path(csv_path)
    stem = csv_file.stem
    base_stem = stem[:-len("-selected-reviews")] if stem.endswith("-selected-reviews") else stem
    metadata_path = csv_file.with_name(f"{base_stem}-pipeline-metadata.json")
    if metadata_path.exists():
        with open(metadata_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    return {
        "source_file": csv_file.name,
        "source_stem": csv_file.stem,
        "report_title": "Amazon Review Insight Report",
        "report_subtitle": csv_file.stem,
        "report_slug": base_stem,
    }


def load_prompt_sections(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8")
    system_match = re.search(
        r"## Draft System Prompt\s*\n\n([\s\S]*?)\n## Draft User Prompt Template",
        text,
    )
    user_match = re.search(
        r"## Draft User Prompt Template\s*\n\n([\s\S]*?)(?:\n## Points To Review With User|\Z)",
        text,
    )
    if not system_match or not user_match:
        raise ValueError(f"Unable to parse prompt sections from {path}")
    return system_match.group(1).strip(), user_match.group(1).strip()


def get_provider_configs(
    runtime_config: dict[str, Any] | None = None,
    provider_override: str | None = None,
    model_override: str | None = None,
) -> tuple[list[str], dict[str, str] | None]:
    """Build the fallback chain and the optional model override.

    Returns:
        (fallback_chain, model_override) where ``fallback_chain`` is a list of
        provider NAMES (resolved from ``ordered_providers()``) and
        ``model_override`` is the LangChain model identifier (or None).

    Per-provider model settings are resolved from the project's
    ``config/provider_registry.json`` plus environment variables.
    """
    runtime_config = runtime_config or {}
    chain = ordered_providers(runtime_config, provider_override)
    if not chain:
        raise SystemExit("[ERROR] No LLM providers configured. Add entries to config/provider_registry.json.")
    return chain, model_override


def call_with_fallback(
    fallback_chain: list[str],
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
    *,
    runtime_config: dict[str, Any] | None = None,
    model_override: str | None = None,
    json_retries: int = 2,
) -> tuple[str, dict[str, str]]:
    """Call each provider in order; return the first successful JSON-validated response.

    Uses OpenAI-compatible chat endpoints. Provider settings come from
    ``config/provider_registry.json`` and may be overridden by environment
    variables or runtime config ``provider_overrides``.

    Args:
        fallback_chain: List of provider NAMES from ``FALLBACK_CHAIN`` (e.g. ["deepseek", "gemini"]).
        system_prompt: System message.
        user_prompt: User message.
        temperature: Sampling temperature.
        max_tokens: Max output tokens.
        model_override: If provided, passed to ``create_chat_model`` via ``model=`` kwarg
            (overrides the registered model identifier in provider_registry.json).
        json_retries: Per-provider attempts for non-fatal errors (default 2).

    Returns:
        (content, {"provider": name, "model": model_id}).
    """
    errors: list[str] = []
    for provider_name in fallback_chain:
        for attempt in range(json_retries + 1):
            try:
                settings = resolve_provider_settings(
                    provider_name,
                    runtime_config=runtime_config,
                    model_override=model_override,
                )
                missing = [
                    key
                    for key in ("base_url", "model", "api_key")
                    if not settings.get(key)
                ]
                if missing:
                    raise RuntimeError(
                        f"{provider_name} missing {', '.join(missing)} "
                        f"(api key env: {settings.get('api_key_env')})"
                    )
                model = ChatOpenAI(
                    base_url=settings["base_url"],
                    api_key=settings["api_key"],
                    model=settings["model"],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                response = model.invoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ])
                content = _extract_text_content(response)
                if not content or not content.strip():
                    raise RuntimeError(f"{provider_name} returned an empty response")
                # Structural guard: caller still parses the same content.
                extract_json(content)
                # Resolve the actual model identifier (e.g. "deepseek-chat") for the log.
                model_id = settings["model"]
                return content, {"provider": provider_name, "model": model_id}
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{provider_name} attempt {attempt + 1}/{json_retries + 1} -> {type(exc).__name__}: {exc}")
                if attempt < json_retries:
                    time.sleep(min(2**attempt, 4))
    raise RuntimeError("All providers failed: " + " | ".join(errors))


def _extract_text_content(response: Any) -> str:
    """Extract text content from a LangChain AIMessage or similar response object."""
    content = getattr(response, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return str(content)


def extract_json(text: str) -> dict[str, Any] | list[Any]:
    match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text)
    raw = match.group(1) if match else text
    if not raw.strip().startswith(("{", "[")):
        fallback = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", raw)
        if fallback:
            raw = fallback.group(1)
    raw = raw.strip()
    if not raw:
        raise ValueError("Empty JSON payload from LLM.")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        cleaned = re.sub(r",\s*([}\]])", r"\1", raw)
        cleaned = re.sub(r"[\x00-\x1f\x7f]", "", cleaned)
        return json.loads(cleaned)


def compute_kpis(df: pd.DataFrame) -> dict[str, Any]:
    total = len(df)
    avg_rating = round(float(df["Rating"].mean()), 2) if total else 0.0
    positive_rate = round(float((df["Rating"] >= 4).mean() * 100), 1) if total else 0.0
    dist = df["Rating"].round().astype(int).value_counts().sort_index()
    rating_distribution = {}
    for star in range(1, 6):
        count = int(dist.get(star, 0))
        rating_distribution[str(star)] = {
            "count": count,
            "pct": round((count / total) * 100, 1) if total else 0.0,
        }
    return {
        "total_reviews": total,
        "avg_rating": avg_rating,
        "positive_rate_pct": positive_rate,
        "rating_distribution": rating_distribution,
    }


def compute_monthly_trend(df: pd.DataFrame) -> list[dict[str, Any]]:
    valid = df.dropna(subset=["Date"]).copy()
    if valid.empty:
        return []
    valid["YearMonth"] = valid["Date"].dt.to_period("M").astype(str)
    grouped = valid.groupby("YearMonth").agg(review_count=("Rating", "size"), avg_rating=("Rating", "mean")).reset_index()
    grouped["avg_rating"] = grouped["avg_rating"].round(2)
    grouped = grouped.sort_values("YearMonth")
    return grouped.to_dict(orient="records")


def compute_word_freq(df: pd.DataFrame, top_n: int = 40) -> list[dict[str, Any]]:
    total = len(df)
    text_blob = " ".join(df["Content"].tolist()).lower()
    tokens = re.findall(r"[a-zA-Z\u4e00-\u9fff]{3,}", text_blob)
    filtered = [token for token in tokens if token not in STOP_WORDS]
    counter = Counter(filtered)
    rows = []
    for token, _ in counter.most_common(top_n * 2):
        mentions = int(df["Content"].str.contains(re.escape(token), case=False, regex=True).sum())
        rows.append({"word": token, "freq": mentions, "pct": round((mentions / total) * 100, 2) if total else 0.0})
    rows.sort(key=lambda item: item["freq"], reverse=True)
    return rows[:top_n]


def build_chunks(df: pd.DataFrame, chunk_size: int = DEFAULT_CHUNK_SIZE) -> list[dict[str, Any]]:
    chunks = []
    chunk_size = max(int(chunk_size), 1)
    for start in range(0, len(df), chunk_size):
        chunk_df = df.iloc[start : start + chunk_size]
        reviews = [
            {
                "review_id": int(row.review_id),
                "rating": float(row.Rating),
                "helpful": int(row.Helpful),
                "content": row.Content,
            }
            for row in chunk_df.itertuples(index=False)
        ]
        chunks.append(
            {
                "chunk_id": int(chunk_df["chunk_id"].iloc[0]) if not chunk_df.empty else (start // chunk_size) + 1,
                "review_ids": [review["review_id"] for review in reviews],
                "reviews": reviews,
            }
        )
    return chunks


def render_user_prompt(template: str, placeholder: str, payload: dict[str, Any]) -> str:
    return template.replace(placeholder, json.dumps(payload, ensure_ascii=False, indent=2))


def normalize_label_text(label: str) -> str:
    cleaned = re.sub(r"[^a-z0-9\s]", " ", label.lower())
    tokens = [token for token in cleaned.split() if token and token not in STOP_WORDS]
    singularized = []
    for token in tokens:
        if token.endswith("ies") and len(token) > 4:
            singularized.append(token[:-3] + "y")
        elif token.endswith("s") and len(token) > 3 and not token.endswith("ss"):
            singularized.append(token[:-1])
        else:
            singularized.append(token)
    return " ".join(singularized)


def tokenize_label(label: str) -> set[str]:
    generic = {
        "benefit",
        "benefits",
        "issue",
        "issues",
        "problem",
        "problems",
        "concern",
        "concerns",
    }
    base = normalize_label_text(label)
    return {token for token in base.split() if token not in generic}


def collect_findings(chunk_results: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for result in chunk_results:
        for item in result.get(key, []):
            label = str(item.get("label", "")).strip()
            if not label:
                continue
            quotes = []
            for quote in item.get("sample_quotes", [])[:MAX_QUOTES]:
                try:
                    review_id = int(quote.get("review_id"))
                except Exception:  # noqa: BLE001
                    continue
                quote_text = str(quote.get("quote", "")).strip()
                if quote_text:
                    quotes.append({"review_id": review_id, "quote": quote_text})
            findings.append(
                {
                    "label": label,
                    "business_summary": str(item.get("business_summary", "")).strip(),
                    "supporting_review_ids": [int(value) for value in item.get("supporting_review_ids", []) if str(value).isdigit()],
                    "sample_quotes": quotes,
                }
            )
    return findings


def build_normalization_map(labels: list[str]) -> dict[str, str]:
    unique = [label.strip() for label in labels if label and label.strip()]
    if not unique:
        return {}

    groups: list[dict[str, Any]] = []
    for label in unique:
        tokens = tokenize_label(label)
        normalized = normalize_label_text(label)
        match = None
        for group in groups:
            group_tokens = group["tokens"]
            if not tokens or not group_tokens:
                if normalized == group["normalized"]:
                    match = group
                    break
                continue
            overlap = len(tokens & group_tokens)
            union = len(tokens | group_tokens)
            subset = tokens <= group_tokens or group_tokens <= tokens
            jaccard = overlap / union if union else 0.0
            if subset or jaccard >= 0.6:
                match = group
                break
        if match is None:
            groups.append({"labels": [label], "tokens": set(tokens), "normalized": normalized})
        else:
            match["labels"].append(label)
            match["tokens"].update(tokens)

    mapping: dict[str, str] = {}
    for group in groups:
        canonical = min(
            group["labels"],
            key=lambda item: (len(tokenize_label(item) or {item}), len(item), item.lower()),
        )
        for label in group["labels"]:
            mapping[label] = canonical
    return mapping


def refine_normalization_map(
    fallback_chain: list[str],
    labels: list[str],
    family: str,
    base_mapping: dict[str, str],
    model_log: list[dict[str, str]],
    runtime_config: dict[str, Any] | None = None,
) -> dict[str, str]:
    canonicals = sorted({base_mapping.get(label, label) for label in labels if label})
    if len(canonicals) <= 1:
        return base_mapping

    system_prompt = (
        "You are a taxonomy normalization assistant for Amazon review analysis. "
        "Merge near-duplicate labels aggressively when they describe the same commercial concept. "
        "Return strict JSON only."
    )
    user_prompt = f"""Normalize these {family} labels into a clean final taxonomy.

Requirements:
- Output in English.
- Merge near-duplicates aggressively.
- Preserve materially different concepts.
- Prefer concise, report-friendly labels.

Input JSON:
{json.dumps({"labels": canonicals}, ensure_ascii=False, indent=2)}

Output JSON shape:
{{
  "normalized_labels": [
    {{
      "final_label": "No Taste",
      "merged_from": ["Neutral/No Taste", "Flavorless / No Taste"]
    }}
  ]
}}"""
    raw, used = call_with_fallback(
        fallback_chain,
        system_prompt,
        user_prompt,
        temperature=0.0,
        max_tokens=1800,
        runtime_config=runtime_config,
    )
    model_log.append(used)
    parsed = extract_json(raw)
    llm_map = {label: label for label in canonicals}
    if isinstance(parsed, dict):
        for item in parsed.get("normalized_labels", []):
            final_label = str(item.get("final_label", "")).strip()
            merged_from = [str(value).strip() for value in item.get("merged_from", [])]
            if not final_label:
                continue
            for label in merged_from:
                if label:
                    llm_map[label] = final_label

    refined = {}
    for label in labels:
        base = base_mapping.get(label, label)
        refined[label] = llm_map.get(base, base)
    return refined


def aggregate_findings(
    findings: list[dict[str, Any]],
    total_reviews: int,
    top_n: int,
    normalization_map: dict[str, str],
) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for finding in findings:
        label = normalization_map.get(finding["label"], finding["label"])
        bucket = buckets.setdefault(
            label,
            {
                "label": label,
                "business_summary": "",
                "supporting_review_ids": set(),
                "sample_quotes": [],
            },
        )
        if finding["business_summary"] and not bucket["business_summary"]:
            bucket["business_summary"] = finding["business_summary"]
        bucket["supporting_review_ids"].update(finding["supporting_review_ids"])
        existing = {(quote["review_id"], quote["quote"]) for quote in bucket["sample_quotes"]}
        for quote in finding["sample_quotes"]:
            identity = (quote["review_id"], quote["quote"])
            if identity not in existing:
                bucket["sample_quotes"].append(quote)
                existing.add(identity)

    rows = []
    for bucket in buckets.values():
        support_ids = sorted(bucket["supporting_review_ids"])
        count = len(support_ids)
        rows.append(
            {
                "label": bucket["label"],
                "count": count,
                "coverage_pct": round((count / total_reviews) * 100, 2) if total_reviews else 0.0,
                "business_summary": bucket["business_summary"],
                "supporting_review_ids": support_ids,
                "sample_quotes": bucket["sample_quotes"][:MAX_QUOTES],
            }
        )
    rows.sort(key=lambda item: (-item["count"], item["label"].lower()))
    return rows[:top_n]


def aggregate_personas(
    chunk_results: list[dict[str, Any]],
    total_reviews: int,
    normalization_map: dict[str, str],
) -> dict[str, Any]:
    buckets: dict[str, dict[str, Any]] = {}
    for result in chunk_results:
        for persona in result.get("personas", []):
            label = str(persona.get("label", "")).strip()
            if not label:
                continue
            normalized = normalization_map.get(label, label)
            bucket = buckets.setdefault(
                normalized,
                {
                    "label": normalized,
                    "usage_context": "",
                    "supporting_review_ids": set(),
                },
            )
            if persona.get("usage_context") and not bucket["usage_context"]:
                bucket["usage_context"] = str(persona["usage_context"]).strip()
            for value in persona.get("supporting_review_ids", []):
                if str(value).isdigit():
                    bucket["supporting_review_ids"].add(int(value))

    rows = []
    for bucket in buckets.values():
        support_ids = sorted(bucket["supporting_review_ids"])
        count = len(support_ids)
        rows.append(
            {
                "label": bucket["label"],
                "usage_context": bucket["usage_context"],
                "count": count,
                "coverage_pct": round((count / total_reviews) * 100, 2) if total_reviews else 0.0,
                "supporting_review_ids": support_ids,
            }
        )
    rows.sort(key=lambda item: (-item["count"], item["label"].lower()))
    return {"personas": rows[:8]}


def compute_priority_scores(advantages: list[dict[str, Any]], pain_points: list[dict[str, Any]]) -> list[str]:
    top_adv = advantages[0]["label"] if advantages else "No dominant advantage identified"
    top_pain = pain_points[0]["label"] if pain_points else "No dominant pain point identified"
    return [top_adv, top_pain]


def normalize_quote_match_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def quote_matches_review(snippet: str, review_text: str) -> bool:
    normalized_snippet = normalize_quote_match_text(snippet)
    if not normalized_snippet:
        return False
    normalized_review = normalize_quote_match_text(review_text)
    return normalized_snippet in normalized_review


def validate_quotes(df: pd.DataFrame, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    review_lookup = dict(zip(df["review_id"], df["Content"]))
    validated: list[dict[str, Any]] = []
    for item in items:
        clean_quotes = []
        clean_ids = []
        for review_id in item["supporting_review_ids"]:
            if review_id in review_lookup:
                clean_ids.append(review_id)
        seen = set()
        for quote in item["sample_quotes"]:
            try:
                review_id = int(quote["review_id"])
            except Exception:  # noqa: BLE001
                continue
            if review_id not in review_lookup:
                continue
            snippet = str(quote["quote"]).strip()
            if not quote_matches_review(snippet, str(review_lookup[review_id])):
                continue
            identity = (review_id, snippet)
            if identity in seen:
                continue
            clean_quotes.append(
                {
                    "review_id": review_id,
                    "quote": snippet,
                    "validation_status": "matched_source_review",
                }
            )
            seen.add(identity)
        validated.append(
            {
                **item,
                "count": len(clean_ids),
                "coverage_pct": round((len(clean_ids) / len(df)) * 100, 2) if len(df) else 0.0,
                "supporting_review_ids": clean_ids,
                "sample_quotes": clean_quotes[:MAX_QUOTES],
            }
        )
    validated.sort(key=lambda row: (-row["count"], row["label"].lower()))
    return validated


def update_xlsx_flags(metadata: dict[str, Any], advantages: list[dict[str, Any]], pain_points: list[dict[str, Any]], personas: dict[str, Any]) -> None:
    xlsx_path = metadata.get("outputs", {}).get("cleaned_xlsx")
    if not xlsx_path or not os.path.exists(xlsx_path):
        return

    df = pd.read_excel(xlsx_path)
    quoted_ids = set()
    advantage_tags: dict[int, list[str]] = defaultdict(list)
    pain_tags: dict[int, list[str]] = defaultdict(list)
    persona_tags: dict[int, list[str]] = defaultdict(list)

    for item in advantages:
        for review_id in item["supporting_review_ids"]:
            advantage_tags[review_id].append(item["label"])
        for quote in item["sample_quotes"]:
            quoted_ids.add(int(quote["review_id"]))
    for item in pain_points:
        for review_id in item["supporting_review_ids"]:
            pain_tags[review_id].append(item["label"])
        for quote in item["sample_quotes"]:
            quoted_ids.add(int(quote["review_id"]))
    for item in personas.get("personas", []):
        for review_id in item["supporting_review_ids"]:
            persona_tags[review_id].append(item["label"])

    def join_tags(mapping: dict[int, list[str]], review_id: Any) -> str:
        if pd.isna(review_id):
            return ""
        labels = sorted(set(mapping.get(int(review_id), [])))
        return "; ".join(labels)

    df["quoted_in_report"] = df["review_id"].apply(lambda value: False if pd.isna(value) else int(value) in quoted_ids)
    df["persona_tags"] = df["review_id"].apply(lambda value: join_tags(persona_tags, value))
    df["advantage_tags"] = df["review_id"].apply(lambda value: join_tags(advantage_tags, value))
    df["pain_point_tags"] = df["review_id"].apply(lambda value: join_tags(pain_tags, value))
    df.to_excel(xlsx_path, index=False)


def write_summary(path: str, metadata: dict[str, Any], kpis: dict[str, Any], advantages: list[dict[str, Any]], pain_points: list[dict[str, Any]], strategies: dict[str, Any]) -> None:
    summary_lines = [
        f"# {metadata['report_title']}",
        "",
        f"**Subtitle:** {metadata['report_subtitle']}",
        "",
        "## Executive Summary",
        "",
        (
            f"The analysis covers {kpis['total_reviews']} selected Amazon reviews with an average rating of "
            f"{kpis['avg_rating']}/5 and a positive-rate proxy of {kpis['positive_rate_pct']}%."
        ),
        "",
        "## Highlights",
        "",
    ]
    if advantages:
        summary_lines.append(f"- Leading advantage: **{advantages[0]['label']}** ({advantages[0]['coverage_pct']}% coverage)")
    if pain_points:
        summary_lines.append(f"- Leading pain point: **{pain_points[0]['label']}** ({pain_points[0]['coverage_pct']}% coverage)")
    top_priority = strategies.get("top_priorities", [])
    if top_priority:
        summary_lines.append(f"- Top recommendation: **{top_priority[0]['theme']}**")
    method_notes = [str(note) for note in metadata.get("method_notes", []) if str(note).strip()]
    if method_notes:
        summary_lines.extend(["", "## Method Notes", ""])
        summary_lines.extend([f"- {note}" for note in method_notes])
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(summary_lines) + "\n")


def shorten_theme(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(value).strip())
    if not cleaned:
        return "Recommendation"
    head = re.split(r"[:;,\-]", cleaned, maxsplit=1)[0].strip()
    words = head.split()
    if len(words) > 4:
        head = " ".join(words[:4])
    head = re.sub(r"\b(and|or|to|for|with|of)$", "", head, flags=re.IGNORECASE).strip()
    return head[:48].strip() or "Recommendation"


def run_analysis(
    csv_path: str,
    provider_override: str | None = None,
    model_override: str | None = None,
    config_path: str | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, str]:
    def emit(**payload: Any) -> None:
        if progress_callback:
            progress_callback(payload)

    metadata = load_metadata(csv_path)
    runtime_config = load_runtime_config(config_path)
    analysis_cfg = runtime_config.get("analysis", {}) or {}
    chunk_size = int(analysis_cfg.get("chunk_size", DEFAULT_CHUNK_SIZE))
    max_chunks = int(analysis_cfg.get("max_chunks", DEFAULT_MAX_CHUNKS))
    chunk_max_tokens = int(analysis_cfg.get("chunk_max_tokens", 8000))
    fallback_chain, model_override_resolved = get_provider_configs(runtime_config, provider_override, model_override)
    df = load_reviews(csv_path)
    total_reviews = len(df)
    if total_reviews == 0:
        raise SystemExit("[ERROR] No selected reviews found in the cleaned CSV.")

    prompt_dir = Path(__file__).resolve().parents[1] / "config" / "prompts"
    strategy_system, strategy_template = load_prompt_sections(prompt_dir / "strategy.draft.md")
    extract_system, extract_template = load_prompt_sections(prompt_dir / "extract.draft.md")
    semantics_system, semantics_template = load_prompt_sections(prompt_dir / "semantics.draft.md")

    chunks = build_chunks(df, chunk_size=chunk_size)[:max_chunks]
    model_log: list[dict[str, str]] = []

    print("[STEP 1] Computing KPIs...", flush=True)
    emit(stage="analysis", step=1, message="Computing KPIs.", progress_pct=18)
    kpis = compute_kpis(df)
    print("[STEP 2] Computing monthly trend...", flush=True)
    emit(stage="analysis", step=2, message="Computing rating trends.", progress_pct=22)
    monthly_trend = compute_monthly_trend(df)
    print("[STEP 3] Computing word frequency...", flush=True)
    emit(stage="analysis", step=3, message="Extracting word frequency patterns.", progress_pct=26)
    word_frequency = compute_word_freq(df)

    chunk_results = []
    for index, chunk in enumerate(chunks, start=1):
        print(f"[STEP 4] Processing chunk {index}/{len(chunks)}", flush=True)
        chunk_progress = 26 + int((index / max(len(chunks), 1)) * 54)
        emit(
            stage="analysis",
            step=4,
            message=f"Processing chunk {index} of {len(chunks)}.",
            progress_pct=chunk_progress,
            chunk_index=index,
            chunk_total=len(chunks),
        )
        common_payload = {
            "task": {
                "goal": "Analyze Amazon reviews",
                "output_language": REPORT_LANGUAGE,
                "sections": ["persona", "advantages", "pain_points"],
            },
            "dataset_summary": {
                "sample_size": total_reviews,
                "avg_rating": kpis["avg_rating"],
                "positive_rate_pct": kpis["positive_rate_pct"],
            },
            "review_chunks": [chunk],
        }

        raw, used = call_with_fallback(
            fallback_chain,
            extract_system,
            render_user_prompt(extract_template, "{{LLM_PAYLOAD_COMBINED}}", common_payload),
            temperature=0.1,
            max_tokens=chunk_max_tokens,
            runtime_config=runtime_config,
            model_override=model_override_resolved,
        )
        model_log.append(used)
        parsed = extract_json(raw)
        chunk_results.append(parsed if isinstance(parsed, dict) else {})

    persona_labels = [item.get("label", "") for result in chunk_results for item in result.get("personas", [])]
    advantage_findings = collect_findings(chunk_results, "advantages")
    pain_findings = collect_findings(chunk_results, "pain_points")
    advantage_labels = [item["label"] for item in advantage_findings]
    pain_labels = [item["label"] for item in pain_findings]

    print("[STEP 5] Normalizing labels...", flush=True)
    emit(stage="analysis", step=5, message="Normalizing labels across chunks.", progress_pct=84)
    persona_map = refine_normalization_map(fallback_chain, persona_labels, "persona", build_normalization_map(persona_labels), model_log, runtime_config)
    advantage_map = refine_normalization_map(fallback_chain, advantage_labels, "advantage", build_normalization_map(advantage_labels), model_log, runtime_config)
    pain_map = refine_normalization_map(fallback_chain, pain_labels, "pain point", build_normalization_map(pain_labels), model_log, runtime_config)

    print("[STEP 6] Aggregating findings...", flush=True)
    emit(stage="analysis", step=6, message="Aggregating findings.", progress_pct=89)
    personas = aggregate_personas(chunk_results, total_reviews, persona_map)
    advantages = aggregate_findings(advantage_findings, total_reviews, TOP_FINDINGS, advantage_map)
    pain_points = aggregate_findings(pain_findings, total_reviews, TOP_FINDINGS, pain_map)
    advantages = validate_quotes(df, advantages)
    pain_points = validate_quotes(df, pain_points)

    print("[STEP 7] Generating recommendations...", flush=True)
    emit(stage="analysis", step=7, message="Generating recommendations.", progress_pct=93)
    strategy_payload = {
        "kpis": kpis,
        "advantages": advantages,
        "pain_points": pain_points,
        "persona": personas,
        "priority_context": compute_priority_scores(advantages, pain_points),
    }
    raw, used = call_with_fallback(
        fallback_chain,
        strategy_system,
        render_user_prompt(strategy_template, "{{LLM_PAYLOAD_STRATEGY}}", strategy_payload),
        temperature=0.2,
        max_tokens=4000,
        runtime_config=runtime_config,
        model_override=model_override_resolved,
    )
    model_log.append(used)
    parsed = extract_json(raw)
    strategies = parsed if isinstance(parsed, dict) else {"top_priorities": []}
    strategies["top_priorities"] = list(strategies.get("top_priorities", []))[:TOP_PRIORITIES]
    for priority in strategies.get("top_priorities", []):
        priority["theme"] = shorten_theme(priority.get("theme", ""))

    print("[STEP 8] Generating semantic word-cloud insights...", flush=True)
    emit(stage="analysis", step=8, message="Generating semantic insight summary.", progress_pct=96)
    semantics_payload = {
        "word_frequency": word_frequency[:20],
        "personas": personas.get("personas", [])[:5],
        "advantages": advantages[:5],
        "pain_points": pain_points[:5],
    }
    raw, used = call_with_fallback(
        fallback_chain,
        semantics_system,
        render_user_prompt(semantics_template, "{{LLM_PAYLOAD_SEMANTICS}}", semantics_payload),
        temperature=0.2,
        max_tokens=1200,
        runtime_config=runtime_config,
        model_override=model_override_resolved,
    )
    model_log.append(used)
    parsed = extract_json(raw)
    market_semantics = parsed if isinstance(parsed, dict) else {"semantic_insights": []}

    pipeline = {
        "project_name": "amazon-review-insight",
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "provider": model_log[0]["provider"] if model_log else fallback_chain[0],
        "model": model_log[0]["model"] if model_log else fallback_chain[0],
        "report_language": REPORT_LANGUAGE,
        "report_style": REPORT_STYLE,
        "provider_attempts": model_log,
        "chunk_size": chunk_size,
        "max_chunks": max_chunks,
        "chunk_max_tokens": chunk_max_tokens,
        "processed_chunks": len(chunks),
    }

    result = {
        "pipeline": pipeline,
        "report": {
            "title": metadata["report_title"],
            "subtitle": metadata["report_subtitle"],
            "brand_name": "Amazon Review Insight",
            "brand_primary": "#00AEEF",
        },
        "dataset": {
            "source_type": "amazon_reviews",
            "source_file": metadata["source_file"],
            "total_raw_reviews": metadata.get("total_raw_reviews", total_reviews),
            "total_cleaned_reviews": total_reviews,
            "total_analyzed_reviews": total_reviews,
            "source_format": metadata.get("source_format", "standard_amazon_review_export"),
            "method_notes": metadata.get("method_notes", []),
        },
        "kpis": kpis,
        "charts": {
            "monthly_trend": monthly_trend,
            "word_frequency": word_frequency,
        },
        "market_semantics": market_semantics,
        "persona": personas,
        "advantages": advantages,
        "pain_points": pain_points,
        "strategies": strategies,
        "traceability": {
            "review_id_namespace": "selected_review_sample",
            "citation_policy": "All reported quotes and supporting IDs must map to selected reviews.",
        },
    }

    output_dir = os.path.dirname(os.path.abspath(csv_path))
    base_name = metadata["report_slug"]
    json_path = os.path.join(output_dir, f"{base_name}-analysis.json")
    summary_path = os.path.join(output_dir, f"{base_name}-summary.md")
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    write_summary(summary_path, metadata, kpis, advantages, pain_points, strategies)
    update_xlsx_flags(metadata, advantages, pain_points, personas)

    print(f"[OK] Analysis JSON -> {json_path}")
    print(f"[OK] Summary Markdown -> {summary_path}")
    return {"analysis_json": json_path, "summary_md": summary_path}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run configurable LLM analysis on selected Amazon reviews")
    parser.add_argument("cleaned_csv", help="Path to the selected reviews CSV")
    parser.add_argument("--provider", help="Optional provider override")
    parser.add_argument("--model", help="Optional model override")
    parser.add_argument("--config", help="Optional path to a runtime config JSON file")
    args = parser.parse_args()
    run_analysis(
        args.cleaned_csv,
        provider_override=args.provider,
        model_override=args.model,
        config_path=args.config,
    )
