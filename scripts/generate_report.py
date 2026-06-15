#!/usr/bin/env python3
"""
Generate a branded Amazon Review Insight HTML report from the structured analysis JSON.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
from html import escape
from pathlib import Path
from typing import Any


BRAND = {
    "name": "Amazon Review Insight",
    "primary": "#00AEEF",
    "secondary": "#0B1B2B",
    "accent": "#66C6F2",
    "background": "#F4FBFE",
    "card": "#FFFFFF",
    "text": "#0B1B2B",
    "muted": "#5A6B7B",
}


def slug_to_readable(stem: str) -> str:
    text = stem.replace("-", " ").strip()
    return " ".join(part.capitalize() for part in text.split()) if text else "Review File"


def load_logo_b64() -> str:
    root_logo = Path(__file__).resolve().parents[1] / "logo.png"
    if root_logo.exists():
        return base64.b64encode(root_logo.read_bytes()).decode("ascii")
    legacy_logo = Path(__file__).resolve().parent / "logo_b64.txt"
    if legacy_logo.exists():
        return legacy_logo.read_text(encoding="utf-8").strip()
    return ""


def get_base_name(path: str) -> str:
    stem = Path(path).stem
    if stem.endswith("-analysis"):
        return stem[:-len("-analysis")]
    return stem


def quote_html(quotes: list[dict[str, Any]]) -> str:
    if not quotes:
        return "<div class='quote-box'>No direct quote fragment selected.</div>"
    boxes = []
    for quote in quotes[:2]:
        review_id = escape(str(quote.get("review_id", "")))
        text = escape(str(quote.get("quote", "")).strip())
        boxes.append(f"<div class='quote-box'><span class='id-tag'>#{review_id}</span>{text}</div>")
    return "".join(boxes)


def finding_rows(items: list[dict[str, Any]]) -> str:
    if not items:
        return "<tr><td colspan='5'>No validated findings available.</td></tr>"
    rows = []
    for index, item in enumerate(items, start=1):
        rows.append(
            f"""
            <tr>
                <td class="rank-col">{index}</td>
                <td><strong>{escape(item.get("label", ""))}</strong></td>
                <td>{item.get("coverage_pct", 0)}%</td>
                <td>{escape(item.get("business_summary", ""))}</td>
                <td>{quote_html(item.get("sample_quotes", []))}</td>
            </tr>
            """
        )
    return "".join(rows)


def priority_cards(priorities: list[dict[str, Any]]) -> str:
    if not priorities:
        return "<div class='priority-card'><h4>No strategic recommendation was generated.</h4></div>"
    cards = []
    for priority in priorities[:3]:
        linked = ", ".join(priority.get("linked_findings", []))
        linked_html = f"<p class='muted'>Linked findings: {escape(linked)}</p>" if linked else ""
        cards.append(
            f"""
            <div class="priority-card">
                <h4>{escape(priority.get("theme", ""))}</h4>
                <p>{escape(priority.get("recommendation", ""))}</p>
                <p class="muted">Category: {escape(priority.get("category", ""))}</p>
                {linked_html}
            </div>
            """
        )
    return "".join(cards)


def persona_rows(personas: list[dict[str, Any]]) -> str:
    if not personas:
        return "<tr><td colspan='4'>No validated persona clusters available.</td></tr>"
    rows = []
    for index, item in enumerate(personas[:8], start=1):
        rows.append(
            f"""
            <tr>
                <td class="rank-col">{index}</td>
                <td><strong>{escape(item.get("label", ""))}</strong></td>
                <td>{item.get("coverage_pct", 0)}%</td>
                <td>{escape(item.get("usage_context", ""))}</td>
            </tr>
            """
        )
    return "".join(rows)


def generate_html(data: dict[str, Any], analysis_path: str) -> str:
    report = data.get("report", {})
    kpis = data.get("kpis", {})
    charts = data.get("charts", {})
    personas = data.get("persona", {}).get("personas", [])
    advantages = data.get("advantages", [])
    pain_points = data.get("pain_points", [])
    strategies = data.get("strategies", {}).get("top_priorities", [])
    semantic_insights = data.get("market_semantics", {}).get("semantic_insights", [])
    dataset = data.get("dataset", {})
    method_notes = [str(note) for note in dataset.get("method_notes", []) if str(note).strip()]
    subtitle = report.get("subtitle") or slug_to_readable(get_base_name(analysis_path))
    title = report.get("title", "Amazon Review Insight Report")
    total_reviews = kpis.get("total_reviews", 0)

    top_adv = advantages[0]["label"] if advantages else "No dominant advantage identified"
    top_pain = pain_points[0]["label"] if pain_points else "No dominant pain point identified"
    executive_summary = (
        f"This report reviews {total_reviews} selected Amazon reviews. "
        f"The product holds an average rating of {kpis.get('avg_rating', 0)}/5 with a positive-rate proxy "
        f"of {kpis.get('positive_rate_pct', 0)}%. The strongest upside signal centers on {top_adv}, while "
        f"the most visible friction theme is {top_pain}."
    )

    highlights = []
    if advantages:
        highlights.append(f"Leading advantage: {advantages[0]['label']} ({advantages[0]['coverage_pct']}% coverage)")
    if pain_points:
        highlights.append(f"Leading pain point: {pain_points[0]['label']} ({pain_points[0]['coverage_pct']}% coverage)")
    if strategies:
        highlights.append(f"Top priority: {strategies[0].get('theme', '')}")
    while len(highlights) < 3:
        highlights.append("Additional validated insight was not available in this run.")

    rating_dist = kpis.get("rating_distribution", {})
    rating_pie = json.dumps(
        [{"value": rating_dist.get(str(star), {}).get("count", 0), "name": f"{star} Star"} for star in range(1, 6)]
    )
    monthly_trend = charts.get("monthly_trend", [])
    trend_months = json.dumps([item["YearMonth"] for item in monthly_trend])
    trend_counts = json.dumps([item["review_count"] for item in monthly_trend])
    trend_ratings = json.dumps([item["avg_rating"] for item in monthly_trend])
    word_frequency = charts.get("word_frequency", [])
    logo_b64 = load_logo_b64()
    max_word_freq = max((item["freq"] for item in word_frequency[:24]), default=1)
    word_cloud_html = "".join(
        [
            f"<span class='cloud-word' style='font-size:{14 + int(22 * (item['freq'] / max_word_freq))}px;opacity:{0.62 + (0.38 * (item['freq'] / max_word_freq)):.2f};'>{escape(item['word'])}</span>"
            for item in word_frequency[:24]
        ]
    )
    semantic_list_html = "".join(
        [f"<li>{escape(item)}</li>" for item in semantic_insights[:3]]
    ) or "<li>No semantic interpretation was generated.</li>"
    method_notes_html = "".join(
        [f"<li>{escape(note)}</li>" for note in method_notes]
    ) or "<li>No special source-format caveats were detected for this run.</li>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escape(title)} | {escape(subtitle)}</title>
  <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {{
      --primary: {BRAND["primary"]};
      --secondary: {BRAND["secondary"]};
      --accent: {BRAND["accent"]};
      --background: {BRAND["background"]};
      --card: {BRAND["card"]};
      --text: {BRAND["text"]};
      --muted: {BRAND["muted"]};
      --border: rgba(31, 58, 74, 0.1);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Manrope", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top right, rgba(29, 162, 216, 0.16), transparent 28%),
        linear-gradient(180deg, #fbfeff 0%, var(--background) 100%);
    }}
    .page {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 32px 24px 56px;
    }}
    .hero {{
      background: linear-gradient(135deg, rgba(31, 58, 74, 0.98), rgba(29, 162, 216, 0.94));
      color: white;
      border-radius: 28px;
      padding: 32px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) 220px;
      gap: 24px;
      box-shadow: 0 24px 50px rgba(20, 48, 59, 0.18);
    }}
    .hero h1 {{ margin: 0 0 10px; font-size: 38px; line-height: 1.05; }}
    .hero .subtitle {{ margin: 0; font-size: 18px; opacity: 0.9; }}
    .hero .logo-wrap {{
      display: flex;
      justify-content: center;
      align-items: center;
      background: transparent;
      min-height: 160px;
    }}
    .hero .logo-wrap img {{
      width: 146px;
      height: auto;
      border-radius: 28px;
      box-shadow: 0 14px 36px rgba(21, 48, 59, 0.18);
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(12, minmax(0, 1fr));
      gap: 20px;
      margin-top: 24px;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 24px;
      padding: 24px;
      box-shadow: 0 14px 30px rgba(22, 48, 59, 0.06);
    }}
    .span-12 {{ grid-column: span 12; }}
    .span-8 {{ grid-column: span 8; }}
    .span-6 {{ grid-column: span 6; }}
    .span-4 {{ grid-column: span 4; }}
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 16px;
    }}
    .kpi {{
      background: linear-gradient(180deg, rgba(29, 162, 216, 0.08), rgba(29, 162, 216, 0.02));
      border-radius: 20px;
      padding: 20px;
      border: 1px solid rgba(29, 162, 216, 0.16);
    }}
    .kpi h4 {{ margin: 0 0 10px; font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); }}
    .kpi .value {{ font-size: 30px; font-weight: 800; }}
    .section-title {{ margin: 0 0 8px; font-size: 24px; }}
    .section-copy {{ margin: 0 0 16px; color: var(--muted); line-height: 1.6; }}
    .highlights {{ margin: 0; padding-left: 18px; }}
    .highlights li {{ margin-bottom: 10px; }}
    .chart {{ height: 340px; }}
    .word-cloud {{
      min-height: 340px;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: center;
      gap: 14px;
      padding: 18px;
      border-radius: 22px;
      background: linear-gradient(180deg, rgba(29, 162, 216, 0.05), rgba(31, 58, 74, 0.04));
    }}
    .cloud-word {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 8px 14px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.84);
      border: 1px solid rgba(29, 162, 216, 0.12);
      color: var(--secondary);
      font-weight: 700;
      line-height: 1;
      box-shadow: 0 8px 20px rgba(21, 48, 59, 0.06);
    }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{
      text-align: left;
      padding: 14px 12px;
      border-bottom: 1px solid rgba(21, 48, 59, 0.08);
      vertical-align: top;
      font-size: 14px;
    }}
    th {{
      font-size: 12px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    .rank-col {{ width: 72px; font-weight: 800; color: var(--primary); }}
    .quote-box {{
      background: rgba(29, 162, 216, 0.06);
      border-radius: 14px;
      padding: 10px 12px;
      margin-bottom: 10px;
      line-height: 1.5;
    }}
    .id-tag {{
      display: inline-block;
      margin-right: 8px;
      color: var(--primary);
      font-weight: 800;
    }}
    .priority-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
    }}
    .priority-card {{
      border-radius: 20px;
      padding: 20px;
      background: linear-gradient(180deg, rgba(31, 58, 74, 0.04), rgba(29, 162, 216, 0.04));
      border: 1px solid var(--border);
    }}
    .muted {{ color: var(--muted); }}
    footer {{
      margin-top: 28px;
      color: var(--muted);
      font-size: 13px;
      text-align: center;
    }}
    @media (max-width: 980px) {{
      .hero {{ grid-template-columns: 1fr; }}
      .span-8, .span-6, .span-4 {{ grid-column: span 12; }}
      .kpi-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .priority-grid {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 640px) {{
      .page {{ padding: 18px 14px 40px; }}
      .hero {{ padding: 24px; }}
      .hero h1 {{ font-size: 30px; }}
      .kpi-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <div>
        <h1>{escape(title)}</h1>
        <p class="subtitle">{escape(subtitle)}</p>
      </div>
      <div class="logo-wrap">
        <img src="data:image/png;base64,{logo_b64}" alt="{BRAND["name"]} logo">
      </div>
    </section>

    <div class="grid">
      <section class="card span-12">
        <h2 class="section-title">Executive Summary</h2>
        <p class="section-copy">{escape(executive_summary)}</p>
        <ul class="highlights">
          <li>{escape(highlights[0])}</li>
          <li>{escape(highlights[1])}</li>
          <li>{escape(highlights[2])}</li>
        </ul>
      </section>

      <section class="card span-12">
        <div class="kpi-grid">
          <div class="kpi"><h4>Selected Sample</h4><div class="value">{total_reviews}</div></div>
          <div class="kpi"><h4>Average Rating</h4><div class="value">{kpis.get("avg_rating", 0)}</div></div>
          <div class="kpi"><h4>Positive Rate</h4><div class="value">{kpis.get("positive_rate_pct", 0)}%</div></div>
          <div class="kpi"><h4>Top Pain Point</h4><div class="value" style="font-size:22px;">{escape(top_pain)}</div></div>
        </div>
      </section>

      <section class="card span-6">
        <h2 class="section-title">Rating Distribution</h2>
        <div id="ratingChart" class="chart"></div>
      </section>

      <section class="card span-6">
        <h2 class="section-title">Trend Signals</h2>
        <div id="trendChart" class="chart"></div>
      </section>

      <section class="card span-6">
        <h2 class="section-title">Persona Clusters</h2>
        <p class="section-copy">Validated buyer or user clusters identified from the selected review sample.</p>
        <table>
          <thead>
            <tr><th>Rank</th><th>Persona</th><th>Coverage</th><th>Usage Context</th></tr>
          </thead>
          <tbody>
            {persona_rows(personas)}
          </tbody>
        </table>
      </section>

      <section class="card span-6">
        <h2 class="section-title">Word Cloud</h2>
        <p class="section-copy">Recurring review vocabulary visualized by keyword coverage, followed by model-assisted semantic interpretation.</p>
        <div class="word-cloud">{word_cloud_html}</div>
        <ul class="highlights" style="margin-top:16px;">
          {semantic_list_html}
        </ul>
      </section>

      <section class="card span-12">
        <h2 class="section-title">Top 8 Advantages</h2>
        <p class="section-copy">Ranked strictly by supporting review coverage.</p>
        <table>
          <thead>
            <tr><th>Rank</th><th>Advantage</th><th>Coverage</th><th>Business Summary</th><th>Evidence</th></tr>
          </thead>
          <tbody>
            {finding_rows(advantages)}
          </tbody>
        </table>
      </section>

      <section class="card span-12">
        <h2 class="section-title">Top 8 Pain Points</h2>
        <p class="section-copy">Ranked strictly by supporting review coverage.</p>
        <table>
          <thead>
            <tr><th>Rank</th><th>Pain Point</th><th>Coverage</th><th>Business Summary</th><th>Evidence</th></tr>
          </thead>
          <tbody>
            {finding_rows(pain_points)}
          </tbody>
        </table>
      </section>

      <section class="card span-12">
        <h2 class="section-title">Strategic Recommendations</h2>
        <p class="section-copy">Recommendations ranked by overall importance and commercial value.</p>
        <div class="priority-grid">
          {priority_cards(strategies)}
        </div>
      </section>

      <section class="card span-12">
        <h2 class="section-title">Method Notes</h2>
        <p class="section-copy">Data-source and sampling caveats that should be considered when interpreting this report.</p>
        <ul class="highlights">
          {method_notes_html}
        </ul>
      </section>
    </div>

    <footer>
      <div>Prepared by {BRAND["name"]}</div>
      <div>Based on structured analysis of Amazon review data and model-assisted interpretation.</div>
    </footer>
  </div>

  <script>
    const ratingChart = echarts.init(document.getElementById('ratingChart'));
    const trendChart = echarts.init(document.getElementById('trendChart'));
    ratingChart.setOption({{
      tooltip: {{ trigger: 'item' }},
      series: [{{
        type: 'pie',
        radius: ['44%', '74%'],
        data: {rating_pie},
        label: {{ formatter: '{{b}}\\n{{d}}%' }},
        color: ['#E26D5C', '#F6C85F', '#9ED9CC', '#5BC0EB', '#00AEEF']
      }}]
    }});

    trendChart.setOption({{
      tooltip: {{ trigger: 'axis' }},
      legend: {{ top: 0 }},
      xAxis: {{ type: 'category', data: {trend_months} }},
      yAxis: [{{ type: 'value', name: 'Reviews' }}, {{ type: 'value', name: 'Rating', min: 1, max: 5 }}],
      series: [
        {{ name: 'Review Volume', type: 'bar', data: {trend_counts}, itemStyle: {{ color: '{BRAND["primary"]}', borderRadius: [6, 6, 0, 0] }} }},
        {{ name: 'Average Rating', type: 'line', yAxisIndex: 1, smooth: true, data: {trend_ratings}, lineStyle: {{ color: '{BRAND["secondary"]}', width: 3 }} }}
      ]
    }});

    window.addEventListener('resize', () => {{
      ratingChart.resize();
      trendChart.resize();
    }});
  </script>
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Amazon Review Insight HTML report")
    parser.add_argument("analysis_json", help="Path to analysis JSON")
    args = parser.parse_args()

    with open(args.analysis_json, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    html = generate_html(data, args.analysis_json)
    base_name = get_base_name(args.analysis_json)
    output_path = os.path.join(os.path.dirname(args.analysis_json), f"{base_name}-report.html")
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(html)
    print(f"[OK] HTML report -> {output_path}")


if __name__ == "__main__":
    main()
