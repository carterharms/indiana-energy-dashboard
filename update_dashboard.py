#!/usr/bin/env python3
"""
Indiana Energy Affordability Dashboard ‚Äî auto-updater.

Run once to generate dashboard.html, then schedule via cron to keep it current.
Requires: pip install anthropic
Requires: ANTHROPIC_API_KEY environment variable
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import anthropic

SCRIPT_DIR = Path(__file__).parent
DASHBOARD_PATH    = SCRIPT_DIR / "dashboard.html"
LOG_PATH          = SCRIPT_DIR / "update.log"
PREV_DATA_PATH    = SCRIPT_DIR / "previous_data.json"

# ‚îÄ‚îÄ Research prompt ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ

RESEARCH_PROMPT = """
Today's date is {today}. You are a policy researcher specializing in Indiana
energy affordability. You MUST use the web_search tool to find current
information ‚Äî do NOT rely on training data. Search specifically for content
from 2025 and 2026. Use multiple targeted searches per topic, including the
year 2026 in your search queries.

‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ
TOPIC 1 ‚Äî RECENT RATE CASES (last 12 months)
‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ
Search the Indiana Utility Regulatory Commission (IURC) and Indiana news sources
for recent rate cases and significant proceedings involving:
  ‚Ä¢ Duke Energy Indiana
  ‚Ä¢ AES Indiana (formerly Indianapolis Power & Light / IPL)
  ‚Ä¢ NIPSCO (Northern Indiana Public Service Company) ‚Äî gas & electric
  ‚Ä¢ Vectren / CenterPoint Energy Indiana
  ‚Ä¢ Any other Indiana electric or gas utilities

For each case include:
  - utility: utility company name
  - case_number: IURC Cause number if available (e.g. "Cause No. 45XXX")
  - description: what is being requested or decided (1‚Äì2 sentences)
  - status: one of "Pending", "Approved", "Denied", "Settled", "Under Review"
  - date: filed date or decision date (Month Year format)
  - rate_change: rate increase/decrease amount or percentage if available, else ""

‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ
TOPIC 2 ‚Äî NEWS ARTICLES (last 60 days)
‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ
Find 8‚Äì10 recent news articles about:
  ‚Ä¢ Indiana utility rates and affordability
  ‚Ä¢ Utility disconnection / shutoff policies in Indiana
  ‚Ä¢ LIHEAP and low-income energy assistance in Indiana
  ‚Ä¢ IURC proceedings and decisions
  ‚Ä¢ Energy burden on Indiana households
  ‚Ä¢ Indiana energy policy developments

For each article include:
  - headline: article title
  - source: publication name
  - date: published date
  - url: full URL
  - summary: 2‚Äì3 sentence plain-language summary

‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ
TOPIC 3 ‚Äî STAKEHOLDER VOICES (last 6 months)
‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ
Find recent quotes or statements from Indiana energy stakeholders including:
  ‚Ä¢ IURC commissioners
  ‚Ä¢ Indiana Office of Utility Consumer Counselor (OUCC)
  ‚Ä¢ Citizens Action Coalition of Indiana
  ‚Ä¢ AARP Indiana
  ‚Ä¢ Duke Energy Indiana, AES Indiana, NIPSCO executives
  ‚Ä¢ Indiana legislators on energy/utility committees
  ‚Ä¢ Community action agencies or other consumer advocates

For each quote include:
  - name: person's full name
  - title: job title
  - organization: their organization
  - quote: exact quote or close paraphrase (clearly note if paraphrased)
  - source: where it appeared (news article, testimony, press release, etc.)
  - date: when it was said or published

‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ
TOPIC 4 ‚Äî STRATEGIC COMMUNICATIONS SUMMARY
‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ
Based on the search results above, apply Silverman and Smith's principles of
strategic communication to recommend 3‚Äì4 messaging strategies for advocates
working on Indiana energy affordability. For each recommendation include:
  - audience: the target audience (e.g. "Low-income ratepayers", "Legislators")
  - message: the core message (1‚Äì2 sentences)
  - rationale: why this message works strategically (1 sentence)

Also write a 2‚Äì3 sentence plain-language overview of the current Indiana
energy affordability landscape based on the search results.

‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ
OUTPUT FORMAT
‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ‚îÅ
Return ONLY a valid JSON object ‚Äî no text before or after it.
Use this exact structure. Use YYYY-MM-DD format for all dates.

{
  "summary": {
    "overview": "",
    "messaging_recommendations": [
      {"audience": "", "message": "", "rationale": ""}
    ]
  },
  "rate_cases": [
    {
      "utility": "",
      "case_number": "",
      "description": "",
      "status": "",
      "date": "",
      "rate_change": ""
    }
  ],
  "articles": [
    {
      "headline": "",
      "source": "",
      "date": "",
      "url": "",
      "summary": ""
    }
  ],
  "stakeholders": [
    {
      "name": "",
      "title": "",
      "organization": "",
      "quote": "",
      "source": "",
      "date": ""
    }
  ]
}

Only include real, verifiable information from the search results provided.
"""

# ‚îÄ‚îÄ HTML template ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Indiana Energy Affordability Dashboard</title>
<style>
  :root {{
    --blue:   #002D62;
    --gold:   #CFB53B;
    --light:  #f4f6f9;
    --white:  #ffffff;
    --text:   #1a1a2e;
    --muted:  #6c757d;
    --border: #dee2e6;
    --green:  #1a7a4a;
    --orange: #b85c00;
    --red:    #b01c2e;
    --card-shadow: 0 2px 8px rgba(0,0,0,.08);
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--light);
    color: var(--text);
    line-height: 1.6;
  }}

  /* ‚îÄ‚îÄ Header ‚îÄ‚îÄ */
  header {{
    background: var(--blue);
    color: var(--white);
    padding: 24px 32px;
    border-bottom: 4px solid var(--gold);
  }}
  header h1 {{
    font-size: 1.6rem;
    font-weight: 700;
    letter-spacing: -.3px;
  }}
  header p {{
    font-size: .85rem;
    opacity: .75;
    margin-top: 4px;
  }}
  .header-meta {{
    display: flex;
    align-items: center;
    gap: 16px;
    margin-top: 10px;
    flex-wrap: wrap;
  }}
  .stat-pill {{
    background: rgba(255,255,255,.12);
    border: 1px solid rgba(255,255,255,.2);
    border-radius: 20px;
    padding: 4px 14px;
    font-size: .8rem;
  }}
  .updated {{
    font-size: .78rem;
    opacity: .6;
    margin-left: auto;
  }}

  /* ‚îÄ‚îÄ Layout ‚îÄ‚îÄ */
  main {{
    max-width: 1200px;
    margin: 0 auto;
    padding: 32px 24px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    grid-template-rows: auto auto;
    gap: 28px;
  }}

  /* Rate cases spans full width on top */
  .section-rate-cases {{ grid-column: 1 / -1; }}

  @media (max-width: 768px) {{
    main {{ grid-template-columns: 1fr; }}
    .section-rate-cases {{ grid-column: 1; }}
  }}

  /* ‚îÄ‚îÄ Section titles ‚îÄ‚îÄ */
  section h2 {{
    font-size: 1rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .8px;
    color: var(--blue);
    border-bottom: 3px solid var(--gold);
    padding-bottom: 8px;
    margin-bottom: 16px;
  }}

  /* ‚îÄ‚îÄ Cards ‚îÄ‚îÄ */
  .card {{
    background: var(--white);
    border-radius: 8px;
    padding: 16px 18px;
    box-shadow: var(--card-shadow);
    border: 1px solid var(--border);
    margin-bottom: 12px;
  }}
  .card:last-child {{ margin-bottom: 0; }}

  .meta {{
    font-size: .76rem;
    color: var(--muted);
    margin-top: 8px;
  }}

  /* ‚îÄ‚îÄ Rate case cards ‚îÄ‚îÄ */
  .rate-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 12px;
  }}
  .rate-grid .card {{ margin-bottom: 0; }}

  .card-header {{
    display: flex;
    align-items: flex-start;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 8px;
  }}
  .utility-name {{
    font-weight: 700;
    font-size: .95rem;
    color: var(--blue);
  }}
  .case-number {{
    font-size: .75rem;
    background: #e8edf5;
    color: var(--blue);
    border-radius: 4px;
    padding: 2px 7px;
    font-family: monospace;
    white-space: nowrap;
  }}
  .badge {{
    border-radius: 12px;
    padding: 2px 10px;
    font-size: .72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: .4px;
    margin-left: auto;
    white-space: nowrap;
  }}
  .badge-approved {{ background: #d4edda; color: var(--green); }}
  .badge-pending  {{ background: #fff3cd; color: var(--orange); }}
  .badge-denied   {{ background: #f8d7da; color: var(--red); }}
  .badge-neutral  {{ background: #e2e3e5; color: #495057; }}

  .card p {{ font-size: .88rem; color: #444; }}

  .rate-change {{
    display: inline-block;
    margin-top: 8px;
    font-size: .82rem;
    font-weight: 600;
    color: var(--blue);
    background: #e8edf5;
    border-radius: 4px;
    padding: 2px 8px;
  }}

  /* ‚îÄ‚îÄ Article cards ‚îÄ‚îÄ */
  .article-headline {{
    font-weight: 600;
    font-size: .92rem;
    line-height: 1.4;
    margin-bottom: 6px;
  }}
  .article-headline a {{
    color: var(--blue);
    text-decoration: none;
  }}
  .article-headline a:hover {{
    text-decoration: underline;
    color: #004899;
  }}

  /* ‚îÄ‚îÄ Quote cards ‚îÄ‚îÄ */
  blockquote {{
    font-size: .9rem;
    font-style: italic;
    color: #333;
    border-left: 3px solid var(--gold);
    padding-left: 12px;
    margin-bottom: 10px;
    line-height: 1.5;
  }}
  .attribution {{ font-size: .82rem; }}
  .attribution strong {{ display: block; color: var(--blue); }}
  .attribution span {{ color: var(--muted); }}

  /* ‚îÄ‚îÄ Summary box ‚îÄ‚îÄ */
  .summary-box {{
    background: var(--white);
    border-radius: 8px;
    border: 1px solid var(--border);
    border-top: 4px solid var(--gold);
    box-shadow: var(--card-shadow);
    padding: 20px 24px;
    grid-column: 1 / -1;
  }}
  .summary-box h2 {{
    font-size: 1rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .8px;
    color: var(--blue);
    border-bottom: 3px solid var(--gold);
    padding-bottom: 8px;
    margin-bottom: 14px;
  }}
  .summary-overview p {{
    font-size: .92rem;
    color: #333;
    margin-bottom: 16px;
    line-height: 1.6;
  }}
  .summary-columns {{
    display: grid;
    grid-template-columns: 1fr 2fr;
    gap: 24px;
  }}
  @media (max-width: 768px) {{
    .summary-columns {{ grid-template-columns: 1fr; }}
  }}
  .summary-col h3 {{
    font-size: .85rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .5px;
    color: var(--blue);
    margin-bottom: 10px;
  }}
  .changes-list {{
    list-style: none;
    padding: 0;
  }}
  .changes-list li {{
    font-size: .85rem;
    color: #444;
    padding: 5px 0 5px 18px;
    position: relative;
    border-bottom: 1px solid var(--border);
  }}
  .changes-list li:last-child {{ border-bottom: none; }}
  .changes-list li::before {{
    content: "‚ñ∏";
    position: absolute;
    left: 0;
    color: var(--gold);
    font-size: .8rem;
  }}
  .theory-tag {{
    font-size: .65rem;
    background: #e8edf5;
    color: var(--blue);
    border-radius: 4px;
    padding: 1px 6px;
    font-weight: 400;
    text-transform: none;
    letter-spacing: 0;
    vertical-align: middle;
    margin-left: 6px;
  }}
  .rec-card {{
    border-left: 3px solid var(--gold);
    padding: 8px 12px;
    margin-bottom: 10px;
    background: #fafbfc;
    border-radius: 0 6px 6px 0;
  }}
  .rec-audience {{
    font-size: .72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .4px;
    color: var(--blue);
    margin-bottom: 3px;
  }}
  .rec-message {{
    font-size: .88rem;
    color: #222;
    margin-bottom: 3px;
  }}
  .rec-rationale {{
    font-size: .78rem;
    color: var(--muted);
    font-style: italic;
  }}

  .empty {{
    color: var(--muted);
    font-size: .88rem;
    font-style: italic;
    padding: 12px 0;
  }}

  footer {{
    text-align: center;
    padding: 24px;
    font-size: .75rem;
    color: var(--muted);
    border-top: 1px solid var(--border);
    margin-top: 8px;
  }}
</style>
</head>
<body>

<header>
  <h1>‚ö° Indiana Energy Affordability Dashboard</h1>
  <p>Rate cases ¬∑ News ¬∑ Stakeholder voices ‚Äî updated automatically</p>
  <div class="header-meta">
    <span class="stat-pill">üìã {n_cases} Rate Cases</span>
    <span class="stat-pill">üì∞ {n_articles} Articles</span>
    <span class="stat-pill">üí¨ {n_quotes} Quotes</span>
    <span class="updated">Last updated: {updated_at}</span>
  </div>
</header>

<main>

  <section class="summary-box">
    <h2>Summary &amp; Strategic Communications</h2>
    {summary_html}
  </section>

  <section class="section-rate-cases">
    <h2>Recent Rate Cases</h2>
    <div class="rate-grid">
      {rate_cases_html}
    </div>
  </section>

  <section>
    <h2>Recent Articles</h2>
    {articles_html}
  </section>

  <section>
    <h2>Stakeholder Voices</h2>
    {stakeholders_html}
  </section>

</main>

<footer>
  Indiana Energy Affordability Dashboard ¬∑ Research by Claude (Anthropic) ¬∑
  Auto-refreshed weekly ¬∑ Data from public sources
</footer>

</body>
</html>
"""

# ‚îÄ‚îÄ Helpers ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ

def log(msg: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line, flush=True)
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")


def load_previous_data() -> dict:
    if PREV_DATA_PATH.exists():
        try:
            return json.loads(PREV_DATA_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def compute_changes(prev: dict, curr: dict) -> list[str]:
    changes = []

    prev_cases = {f"{c.get('utility','')}|{c.get('case_number','')}": c for c in prev.get("rate_cases", [])}
    for c in curr.get("rate_cases", []):
        key = f"{c.get('utility','')}|{c.get('case_number','')}"
        if key not in prev_cases:
            changes.append(f"New rate case: {c.get('utility','')} ‚Äî {c.get('description','')[:80]}")
        elif prev_cases[key].get("status") != c.get("status"):
            changes.append(f"Status change: {c.get('utility','')} case now {c.get('status','')}")

    prev_headlines = {a.get("headline","") for a in prev.get("articles", [])}
    new_articles = [a for a in curr.get("articles", []) if a.get("headline","") not in prev_headlines]
    if new_articles:
        changes.append(f"{len(new_articles)} new article{'s' if len(new_articles) != 1 else ''} since last update")

    prev_quotes = {f"{s.get('name','')}|{s.get('date','')}": True for s in prev.get("stakeholders", [])}
    for s in curr.get("stakeholders", []):
        key = f"{s.get('name','')}|{s.get('date','')}"
        if key not in prev_quotes:
            changes.append(f"New quote: {s.get('name','')} ({s.get('organization','')})")

    return changes if changes else ["No significant changes detected since last update"]


def research(client: anthropic.Anthropic) -> dict:
    """Use Anthropic server-side web search for live, high-quality results."""
    tools    = [{"type": "web_search_20260209", "name": "web_search"}]
    today    = datetime.now().strftime("%B %d, %Y")
    messages = [{"role": "user", "content": RESEARCH_PROMPT.format(today=today)}]
    container_id = None

    for attempt in range(8):
        log(f"  API call {attempt + 1}‚Ä¶")
        kwargs = dict(
            model="claude-sonnet-4-6",
            max_tokens=8000,
            tools=tools,
            messages=messages,
        )
        if container_id:
            kwargs["container_id"] = container_id

        for retry in range(5):
            try:
                raw      = client.messages.with_raw_response.create(**kwargs)
                response = raw.parse()
                break
            except anthropic.RateLimitError:
                wait = 65 * (retry + 1)
                log(f"  Rate limit ‚Äî waiting {wait}s‚Ä¶")
                time.sleep(wait)
        else:
            raise RuntimeError("Rate limit retries exhausted.")

        if not container_id:
            for h in ["x-container-id", "container-id", "x-session-id"]:
                val = raw.headers.get(h)
                if val:
                    container_id = val
                    log(f"  container_id captured from header '{h}'")
                    break
            if not container_id:
                cid = getattr(response, "container_id", None) or \
                      (getattr(response, "model_extra", None) or {}).get("container_id")
                if cid:
                    container_id = cid
                    log(f"  container_id captured from response body")
            if not container_id:
                log(f"  Note: no container_id found (headers: {list(raw.headers.keys())})")

        log(f"  stop_reason={response.stop_reason} container={'set' if container_id else 'unset'}")

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    text  = block.text.strip()
                    start = text.find("{")
                    end   = text.rfind("}") + 1
                    if start != -1 and end > start:
                        try:
                            return json.loads(text[start:end])
                        except json.JSONDecodeError as exc:
                            raise ValueError(f"JSON parse error: {exc}\n\n{text[start:end][:600]}")
            raise ValueError("No JSON in end_turn response.")

        if response.stop_reason == "pause_turn":
            for block in response.content:
                btype = getattr(block, "type", "unknown")
                bid   = getattr(block, "id", None)
                extra = getattr(block, "model_extra", {}) or {}
                log(f"  pause_turn block: type={btype} id={bid} extra_keys={list(extra.keys())}")
                if not container_id and bid:
                    container_id = bid
                    log(f"  container_id set from block id: {container_id[:20]}‚Ä¶")
            messages.append({"role": "assistant", "content": response.content})
            continue

        raise ValueError(f"Unexpected stop_reason: {response.stop_reason!r}")

    raise RuntimeError("Exceeded max continuation attempts.")


# ‚îÄ‚îÄ HTML builder ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ

def _badge(status: str) -> str:
    s = status.lower()
    if any(w in s for w in ("approv", "grant", "order")):
        return "badge-approved"
    if any(w in s for w in ("pend", "filed", "review", "under")):
        return "badge-pending"
    if any(w in s for w in ("deni", "reject")):
        return "badge-denied"
    return "badge-neutral"


def build_html(data: dict, updated_at: str, changes: list[str] | None = None) -> str:
    # ‚îÄ‚îÄ Summary box ‚îÄ‚îÄ
    summary     = data.get("summary", {})
    overview    = summary.get("overview", "")
    recs        = summary.get("messaging_recommendations", [])
    changes     = changes or []

    changes_html = "".join(f"<li>{c}</li>" for c in changes) if changes else "<li style='font-style:italic;color:#888'>First run ‚Äî changes will appear after the next update.</li>"
    recs_html    = "".join(
        f'<div class="rec-card">'
        f'<div class="rec-audience">{r.get("audience","")}</div>'
        f'<div class="rec-message">{r.get("message","")}</div>'
        f'<div class="rec-rationale">{r.get("rationale","")}</div>'
        f'</div>'
        for r in recs
    )

    summary_html = f"""
      <div class="summary-overview"><p>{overview}</p></div>
      <div class="summary-columns">
        <div class="summary-col">
          <h3>What Changed</h3>
          <ul class="changes-list">{changes_html}</ul>
        </div>
        <div class="summary-col">
          <h3>Messaging Recommendations <span class="theory-tag">Silverman &amp; Smith</span></h3>
          {recs_html}
        </div>
      </div>"""

    # ‚îÄ‚îÄ Rate cases ‚îÄ‚îÄ
    rate_cases_html = ""
    for case in data.get("rate_cases", []):
        status = case.get("status", "")
        badge  = _badge(status)
        cn     = (f'<span class="case-number">{case["case_number"]}</span>'
                  if case.get("case_number") else "")
        rc     = (f'<div class="rate-change">{case["rate_change"]}</div>'
                  if case.get("rate_change") else "")
        rate_cases_html += f"""
      <div class="card">
        <div class="card-header">
          <span class="utility-name">{case.get("utility","")}</span>
          {cn}
          <span class="badge {badge}">{status}</span>
        </div>
        <p>{case.get("description","")}</p>
        {rc}
        <div class="meta">{case.get("date","")}</div>
      </div>"""

    if not rate_cases_html:
        rate_cases_html = '<p class="empty">No recent rate cases found.</p>'

    # ‚îÄ‚îÄ Articles (sorted newest first) ‚îÄ‚îÄ
    articles_html = ""
    sorted_articles = sorted(
        data.get("articles", []),
        key=lambda a: a.get("date", ""),
        reverse=True,
    )
    for art in sorted_articles:
        url  = art.get("url", "")
        link = (f'<a href="{url}" target="_blank" rel="noopener">'
                f'{art.get("headline","")}</a>'
                if url else art.get("headline", ""))
        articles_html += f"""
      <div class="card">
        <div class="article-headline">{link}</div>
        <p style="font-size:.85rem;color:#444">{art.get("summary","")}</p>
        <div class="meta">{art.get("source","")} ¬∑ {art.get("date","")}</div>
      </div>"""

    if not articles_html:
        articles_html = '<p class="empty">No recent articles found.</p>'

    # ‚îÄ‚îÄ Stakeholders ‚îÄ‚îÄ
    stakeholders_html = ""
    for s in data.get("stakeholders", []):
        stakeholders_html += f"""
      <div class="card">
        <blockquote>"{s.get("quote","")}"</blockquote>
        <div class="attribution">
          <strong>{s.get("name","")}</strong>
          <span>{s.get("title","")}, {s.get("organization","")}</span>
        </div>
        <div class="meta">{s.get("source","")} ¬∑ {s.get("date","")}</div>
      </div>"""

    if not stakeholders_html:
        stakeholders_html = '<p class="empty">No recent stakeholder quotes found.</p>'

    return HTML_TEMPLATE.format(
        updated_at=updated_at,
        summary_html=summary_html,
        rate_cases_html=rate_cases_html,
        articles_html=articles_html,
        stakeholders_html=stakeholders_html,
        n_cases=len(data.get("rate_cases", [])),
        n_articles=len(data.get("articles", [])),
        n_quotes=len(data.get("stakeholders", [])),
    )


# ‚îÄ‚îÄ Main ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ

def main() -> None:
    log("‚îÅ‚îÅ‚îÅ Dashboard update started ‚îÅ‚îÅ‚îÅ")
    client = anthropic.Anthropic()

    prev_data = load_previous_data()

    log("Researching rate cases, articles, and stakeholder quotes‚Ä¶")
    try:
        data = research(client)
    except Exception as exc:
        log(f"ERROR during research: {exc}")
        sys.exit(1)

    log(
        f"Research complete ‚Äî "
        f"{len(data.get('rate_cases', []))} rate cases, "
        f"{len(data.get('articles', []))} articles, "
        f"{len(data.get('stakeholders', []))} quotes"
    )

    changes = [] if not prev_data else compute_changes(prev_data, data)
    log(f"Changes detected: {len(changes)}")

    updated_at = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    html = build_html(data, updated_at, changes)
    DASHBOARD_PATH.write_text(html, encoding="utf-8")
    log(f"Dashboard written ‚Üí {DASHBOARD_PATH}")

    PREV_DATA_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    log(f"Previous data saved ‚Üí {PREV_DATA_PATH}")
    log("‚îÅ‚îÅ‚îÅ Done ‚îÅ‚îÅ‚îÅ")


if __name__ == "__main__":
    main()
