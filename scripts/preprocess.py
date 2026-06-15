#!/usr/bin/env python3
"""
Review Data Preprocessor

Validates an Amazon review export, normalizes required fields, applies selection
rules, and exports:

- a selected CSV for downstream LLM analysis
- an audit-friendly XLSX table with preprocessing flags
- a small metadata JSON file shared by later pipeline stages
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any

import pandas as pd


TRIVIAL_PATTERNS = [
    r"^[\s\W]*$",
    r"^(good|ok|okay|nice|fine|great|bad|yes|no|na|n/a|none|nil|love it|hate it|meh)[\s!.\?]*$",
]
TRIVIAL_RE = [re.compile(pattern, re.IGNORECASE) for pattern in TRIVIAL_PATTERNS]
MIN_CONTENT_LEN = 8
REPORT_TITLE = "Amazon Review Insight Report"
DEFAULT_CHUNK_SIZE = 150


SELLERSPRITE_COLUMNS = {
    "asin",
    "标题",
    "内容",
    "vp评论",
    "vine voice评论",
    "型号",
    "星级",
    "赞同数",
    "评论人",
    "所属国家",
    "评论时间",
}


def is_trivial(text: str) -> bool:
    if not isinstance(text, str):
        return True
    stripped = text.strip()
    if len(stripped) < MIN_CONTENT_LEN:
        return True
    return any(pattern.match(stripped) for pattern in TRIVIAL_RE)


def load_data(path: str) -> pd.DataFrame:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(path)
    if ext == ".csv":
        return pd.read_csv(path, encoding="utf-8-sig")
    return pd.read_csv(path, encoding="utf-8-sig")


def normalize_column_key(column: str) -> str:
    return re.sub(r"\s+", " ", column.strip().lower().replace("_", " ").replace("-", " "))


def build_column_rename_map(columns: list[str]) -> dict[str, str]:
    expected = {
        "content": "Content",
        "review content": "Content",
        "review text": "Content",
        "review body": "Content",
        "body": "Content",
        "text": "Content",
        "comment": "Content",
        "comments": "Content",
        "内容": "Content",
        "評論內容": "Content",
        "评论内容": "Content",
        "rating": "Rating",
        "ratings": "Rating",
        "star": "Rating",
        "stars": "Rating",
        "star rating": "Rating",
        "星级": "Rating",
        "星級": "Rating",
        "评分": "Rating",
        "date": "Date",
        "review date": "Date",
        "评论时间": "Date",
        "評論時間": "Date",
        "评论日期": "Date",
        "helpful": "Helpful",
        "helpful votes": "Helpful",
        "helpful vote": "Helpful",
        "helpful count": "Helpful",
        "赞同数": "Helpful",
        "贊同數": "Helpful",
        "有用数": "Helpful",
        "name": "Name",
        "author": "Name",
        "reviewer": "Name",
        "reviewer name": "Name",
        "customer": "Name",
        "评论人": "Name",
        "評論人": "Name",
        "作者": "Name",
        "verified purchase": "Verified Purchase",
        "verified": "Verified Purchase",
        "is verified": "Verified Purchase",
        "verified buyer": "Verified Purchase",
        "vp评论": "Verified Purchase",
        "vp評論": "Verified Purchase",
        "是否vp": "Verified Purchase",
    }
    rename_map: dict[str, str] = {}
    for column in columns:
        key = normalize_column_key(column)
        if key in expected:
            rename_map[column] = expected[key]
    return rename_map


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns=build_column_rename_map([str(column) for column in df.columns]))


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "report"


def readable_title_from_stem(stem: str) -> str:
    text = re.sub(r"[_\-]+", " ", stem).strip()
    words = [word for word in text.split() if word]
    if not words:
        return "Review File"
    return " ".join(word[:1].upper() + word[1:] for word in words)


def normalize_verified(value: Any) -> bool:
    text = str(value).strip().upper()
    return text in {
        "Y",
        "YES",
        "TRUE",
        "1",
        "VERIFIED",
        "VERIFIED PURCHASE",
        "VERIFIED BUYER",
    }


def append_reason(existing: Any, reason: str) -> str:
    current = str(existing or "").strip()
    if not current:
        return reason
    parts = [part for part in current.split(";") if part]
    if reason not in parts:
        parts.append(reason)
    return ";".join(parts)


def detect_source_format(raw_columns: list[str]) -> dict[str, Any]:
    normalized = {normalize_column_key(str(column)) for column in raw_columns}
    sellersprite_matches = normalized & SELLERSPRITE_COLUMNS
    if len(sellersprite_matches) >= 6:
        return {
            "source_format": "sellersprite_star_balanced_export",
            "method_notes": [
                (
                    "The input appears to be a SellerSprite Amazon review export. "
                    "SellerSprite exports are often collected with a star-balanced sampling strategy, "
                    "so rating distribution in this report should be interpreted as a sampled review mix "
                    "rather than the product's natural Amazon rating distribution."
                )
            ],
        }
    return {
        "source_format": "standard_amazon_review_export",
        "method_notes": [],
    }


def preprocess(input_path: str, max_reviews: int = 75000, chunk_size: int = DEFAULT_CHUNK_SIZE) -> dict[str, str]:
    raw_df = load_data(input_path)
    raw_columns = [str(column) for column in raw_df.columns]
    source_profile = detect_source_format(raw_columns)
    column_mapping = build_column_rename_map(raw_columns)
    df = raw_df.rename(columns=column_mapping).copy()

    required = ["Content", "Rating", "Date", "Helpful", "Verified Purchase"]
    missing = [column for column in required if column not in df.columns]
    if missing:
        sys.exit(f"[ERROR] Missing required columns: {missing}\nAvailable: {list(df.columns)}")
    name_missing = "Name" not in df.columns
    if name_missing:
        df["Name"] = "Unknown"

    source_file = os.path.basename(input_path)
    source_stem = os.path.splitext(source_file)[0]
    subtitle = readable_title_from_stem(source_stem)
    report_slug = slugify(f"{subtitle} {REPORT_TITLE}")

    total_raw = len(df)
    print(f"[INFO] Raw records loaded: {total_raw}")

    df = df.reset_index(drop=True)
    df["verified_purchase_bool"] = df["Verified Purchase"].apply(normalize_verified)
    df["Content"] = df["Content"].fillna("").astype(str)
    df["Name"] = df["Name"].fillna("Unknown").astype(str).replace("", "Unknown")
    df["rating_numeric"] = pd.to_numeric(df["Rating"], errors="coerce")
    df["date_normalized"] = pd.to_datetime(df["Date"], errors="coerce")
    df["helpful_numeric"] = pd.to_numeric(df["Helpful"], errors="coerce")
    df["helpful_invalid"] = df["helpful_numeric"].isna()
    df["helpful_numeric"] = df["helpful_numeric"].fillna(0).clip(lower=0).astype(int)
    df["content_normalized"] = df["Content"].str.strip()
    df["content_dedupe_key"] = df["content_normalized"].str.lower().str.replace(r"\s+", " ", regex=True)
    df["content_length"] = df["content_normalized"].str.len()
    df["rating_invalid"] = df["rating_numeric"].isna() | ~df["rating_numeric"].between(1, 5)
    df["date_invalid"] = df["date_normalized"].isna()
    df["is_duplicate"] = df.duplicated(subset=["content_dedupe_key"], keep="first")
    df["is_trivial"] = df["content_normalized"].apply(is_trivial)
    df["selected_for_analysis"] = False
    df["selection_bucket"] = ""
    df["selection_rank"] = pd.NA
    df["excluded_reason"] = ""
    df["review_id"] = pd.NA
    df["chunk_id"] = pd.NA
    df["quoted_in_report"] = False

    invalid_mask = (
        ~df["verified_purchase_bool"]
        | df["is_duplicate"]
        | df["is_trivial"]
        | df["rating_invalid"]
    )
    for mask, reason in [
        (~df["verified_purchase_bool"], "not_verified_purchase"),
        (df["is_duplicate"], "duplicate_content"),
        (df["is_trivial"], "trivial_content"),
        (df["rating_invalid"], "invalid_rating"),
    ]:
        df.loc[mask, "excluded_reason"] = df.loc[mask, "excluded_reason"].apply(
            lambda value, reason=reason: append_reason(value, reason)
        )

    candidates = df[~invalid_mask].copy()
    if candidates.empty:
        sys.exit("[ERROR] No usable verified reviews remain after preprocessing.")

    helpful_pool = candidates[candidates["helpful_numeric"] > 1].nlargest(
        min(100, max_reviews), "helpful_numeric"
    )
    remaining = candidates[~candidates.index.isin(helpful_pool.index)]
    long_pool = remaining.nlargest(max(max_reviews - len(helpful_pool), 0), "content_length")
    selected = pd.concat([helpful_pool, long_pool]).drop_duplicates(subset=["content_normalized"], keep="first")
    selected = selected.nlargest(max_reviews, ["helpful_numeric", "content_length"]).copy()
    selected["selected_for_analysis"] = True
    selected.loc[selected.index.isin(helpful_pool.index), "selection_bucket"] = "high_helpful"
    selected.loc[selected["selection_bucket"] == "", "selection_bucket"] = "long_text"
    selected = selected.sort_values(["selection_bucket", "helpful_numeric", "content_length"], ascending=[True, False, False])
    selected["selection_rank"] = range(1, len(selected) + 1)
    selected["review_id"] = range(1, len(selected) + 1)
    selected["chunk_id"] = ((selected["review_id"].astype(int) - 1) // max(chunk_size, 1)) + 1

    df.loc[selected.index, "selected_for_analysis"] = True
    df.loc[selected.index, "selection_bucket"] = selected["selection_bucket"]
    df.loc[selected.index, "selection_rank"] = selected["selection_rank"]
    df.loc[selected.index, "review_id"] = selected["review_id"]
    df.loc[selected.index, "chunk_id"] = selected["chunk_id"]
    df.loc[selected.index, "excluded_reason"] = ""

    selected_for_csv = df[df["selected_for_analysis"]].copy().sort_values("review_id")
    selected_for_csv = selected_for_csv[
        [
            "review_id",
            "Content",
            "Rating",
            "Date",
            "Helpful",
            "Name",
            "Verified Purchase",
            "rating_numeric",
            "date_normalized",
            "helpful_numeric",
            "content_length",
            "selection_bucket",
            "selection_rank",
            "chunk_id",
        ]
    ]

    export_table = df[
        [
            "review_id",
            "Content",
            "Rating",
            "Date",
            "Helpful",
            "Name",
            "Verified Purchase",
            "verified_purchase_bool",
            "content_length",
            "is_duplicate",
            "is_trivial",
            "rating_invalid",
            "date_invalid",
            "helpful_invalid",
            "selected_for_analysis",
            "excluded_reason",
            "chunk_id",
            "quoted_in_report",
            "content_normalized",
            "rating_numeric",
            "date_normalized",
            "helpful_numeric",
            "selection_bucket",
            "selection_rank",
        ]
    ].copy()

    output_dir = os.path.join(os.path.dirname(os.path.abspath(input_path)), "output")
    os.makedirs(output_dir, exist_ok=True)
    cleaned_csv_path = os.path.join(output_dir, f"{report_slug}-selected-reviews.csv")
    cleaned_xlsx_path = os.path.join(output_dir, f"{report_slug}-cleaned-reviews.xlsx")
    metadata_path = os.path.join(output_dir, f"{report_slug}-pipeline-metadata.json")
    quality_report_path = os.path.join(output_dir, f"{report_slug}-data-quality.json")

    selected_for_csv.to_csv(cleaned_csv_path, index=False, encoding="utf-8-sig")
    try:
        export_table.to_excel(cleaned_xlsx_path, index=False)
    except Exception as exc:
        sys.exit(f"[ERROR] Failed to export XLSX audit table: {exc}")

    metadata = {
        "source_file": source_file,
        "source_stem": source_stem,
        "report_title": REPORT_TITLE,
        "report_subtitle": subtitle,
        "report_slug": report_slug,
        "total_raw_reviews": int(total_raw),
        "total_selected_reviews": int(len(selected_for_csv)),
        "max_reviews": int(max_reviews),
        "chunk_size": int(chunk_size),
        "source_format": source_profile["source_format"],
        "method_notes": source_profile["method_notes"],
        "outputs": {
            "selected_csv": cleaned_csv_path,
            "cleaned_xlsx": cleaned_xlsx_path,
            "quality_report_json": quality_report_path,
        },
    }
    exclusion_counts = (
        df["excluded_reason"]
        .fillna("")
        .str.split(";")
        .explode()
        .loc[lambda series: series != ""]
        .value_counts()
        .to_dict()
    )
    quality_report = {
        "source_file": source_file,
        "total_raw_reviews": int(total_raw),
        "total_selected_reviews": int(len(selected_for_csv)),
        "source_format": source_profile["source_format"],
        "method_notes": source_profile["method_notes"],
        "column_mapping": column_mapping,
        "quality_counts": {
            "missing_name_column": name_missing,
            "not_verified_purchase": int((~df["verified_purchase_bool"]).sum()),
            "duplicate_content": int(df["is_duplicate"].sum()),
            "trivial_content": int(df["is_trivial"].sum()),
            "invalid_rating": int(df["rating_invalid"].sum()),
            "invalid_date": int(df["date_invalid"].sum()),
            "invalid_helpful": int(df["helpful_invalid"].sum()),
        },
        "exclusion_reason_counts": {str(key): int(value) for key, value in exclusion_counts.items()},
        "selection_bucket_counts": {
            str(key): int(value)
            for key, value in selected_for_csv["selection_bucket"].value_counts().to_dict().items()
        },
    }
    with open(metadata_path, "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)
    with open(quality_report_path, "w", encoding="utf-8") as handle:
        json.dump(quality_report, handle, ensure_ascii=False, indent=2)

    print(f"[OK] Exported selected CSV -> {cleaned_csv_path}")
    print(f"[OK] Exported audit XLSX -> {cleaned_xlsx_path}")
    print(f"[OK] Exported metadata -> {metadata_path}")
    print(f"[OK] Exported quality report -> {quality_report_path}")
    return {
        "selected_csv": cleaned_csv_path,
        "cleaned_xlsx": cleaned_xlsx_path,
        "metadata_json": metadata_path,
        "quality_report_json": quality_report_path,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Preprocess Amazon review data")
    parser.add_argument("input_file", help="Path to CSV/Excel review data")
    parser.add_argument("--max_reviews", type=int, default=75000, help="Maximum selected reviews")
    parser.add_argument("--chunk_size", type=int, default=DEFAULT_CHUNK_SIZE, help="Reviews per LLM chunk")
    args = parser.parse_args()
    preprocess(args.input_file, args.max_reviews, chunk_size=args.chunk_size)
