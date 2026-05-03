#!/usr/bin/env python3
"""
Indiana Energy Affordability Dashboard — auto-updater.

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
from duckduckgo_search import DDGS

SCRIPT_DIR = Path(__file__).parent
DASHBOARD_PATH    = SCRIPT_DIR / "dashboard.html"
LOG_PATH          = SCRIPT_DIR / "update.log"
PREV_DATA_PATH    = SCRIPT_DIR / "previous_data.json"

# ── Research prompt ────────────────────────────────────────────────────────────

RESEARCH_PROMPT = """
You are a policy researcher specializing in Indiana energy affordability.
Below are live web search results on four topics. Extract and summarize the
most relevant, accurate information from these results.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOPIC 1 — RECENT RATE CASES (last 12 months)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Search the Indiana Utility Regulatory Commission (IURC) and Indiana news sources
for recent rate cases and significant proceedings involving:
  • Duke Energy Indiana
  • AES Indiana (formerly Indianapolis Power & Light / IPL)
  • NIPSCO (Northern Indiana Public Service Company) — gas & electric
  • Vectren / CenterPoint Energy Indiana
  • Any other Indiana electric or gas utilities

For each case include:
  - utility: utility company name
  - case_number: IURC Cause number if available (e.g. "Cause No. 45XXX")
  - description: what is being requested or decided (1–2 sentences)
  - status: one of "Pending", "Approved", "Denied", "Settled", "Under Review"
  - date: filed date or decision date (Month Year format)
  - rate_change: rate increase/decrease amount or percentage if available, else ""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOPIC 2 — NEWS ARTICLES (last 60 days)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Find 8–10 recent news articles about:
  • Indiana utility rates and affordability
  • Utility disconnection / shutoff policies in Indiana
  • LIHEAP and low-income energy assistance in Indiana
  • IURC proceedings and decisions
  • Energy burden on Indiana households
  • Indiana energy policy developments

For each article include:
  - headline: article title
  - source: publication name
  - date: published date
  - url: full URL
  - summary: 2–3 sentence plain-language summary

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOPIC 3 — STAKEHOLDER VOICES (last 6 months)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Find recent quotes or statements from Indiana energy stakeholders including:
  • IURC commissioners
  • Indiana Office of Utility Consumer Counselor (OUCC)
  • Citizens Action Coalition of Indiana
  • AARP Indiana
  • Duke Energy Indiana, AES Indiana, NIPSCO executives
  • Indiana legislators on energy/utility committees
  • Community action agencies or other consumer advocates

For each quote include:
  - name: person's full name
  - title: job title
  - organization: their organization
  - quote: exact quote or close paraphrase (clearly note if paraphrased)
  - source: where it appeared (news article, testimony, press release, etc.)
  - date: when it was said or published

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOPIC 4 — STRATEGIC COMMUNICATIONS SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Based on the search results above, apply Silverman and Smith's principles of
strategic communication to recommend 3–4 messaging strategies for advocates
working on Indiana energy affordability. For each recommendation include:
  - audience: the target audience (e.g. "Low-income ratepayers", "Legislators")
  - message: the core message (1–2 sentences)
  - rationale: why this message works strategically (1 sentence)

Also write a 2–3 sentence plain-language overview of the current Indiana
energy affordability landscape based on the search results.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Return ONLY a valid JSON object — no text before or after it.
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

# ── HTML template ──────────────────────────────────────────────────────────────

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

  /* ── Header ── */
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

  /* ── Layout ── */
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

  /* ── Section titles ── */
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

  /* ── Cards ── */
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

  /* ── Rate case cards ── */
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

  /* ── Article cards ── */
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

  /* ── Quote cards ── */
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

  /* ── Summary box ── */
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
    content: "▸";
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
  <h1>⚡ Indiana Energy Affordability Dashboard</h1>
  <p>Rate cases · News · Stakeholder voices — updated automatically</p>
  <div class="header-meta">
    <span class="stat-pill">📋 {n_cases} Rate Cases</span>
    <span class="stat-pill">📰 {n_articles} Articles</span>
    <span class="stat-pill">💬 {n_quotes} Quotes</span>
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
  Indiana Energy Affordability Dashboard · Research by Claude (Anthropic) ·
  Auto-refreshed weekly · Data from public sources
</footer>

</body>
</html>
"""

# ── Helpers ────────────────────────────────────────────────────────────────────

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
            changes.append(f"New rate case: {c.get('utility','')} — {c.get('description','')[:80]}")
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


SEARCH_QUERIES = [
    "Indiana utility rate case IURC 2025",
    "Duke Energy Indiana AES Indiana NIPSCO rate increase 2025",
    "Indiana energy affordability low income assistance 2025",
    "Indiana utility disconnection LIHEAP 2025",
    "IURC Indiana Utility Regulatory Commission decision 2025",
    "Citizens Action Coalition Indiana energy 2025",
    "Indiana energy policy legislation 2025",
]


def web_search(queries: list[str]) -> str:
    """Run DuckDuckGo searches and return combined results as text."""
    ddgs = DDGS()
    all_results = []
    for query in queries:
        log(f"  Searching: {query}")
        try:
            results = ddgs.text(query, max_results=5)
            for r in results:
                all_results.append(f"HEADLINE: {r.get('title','')}\nSOURCE: {r.get('href','')}\nSNIPPET: {r.get('body','')}\n")
        except Exception as exc:
            log(f"  Search error for '{query}': {exc}")
        time.sleep(1)
    return "\n---\n".join(all_results)


def research(client: anthropic.Anthropic) -> dict:
    """Search the web then ask Claude to format results as dashboard JSON."""
    log("  Running web searches…")
    search_results = web_search(SEARCH_QUERIES)
    log(f"  Got {len(search_results)} chars of search data")

    prompt = RESEARCH_PROMPT + f"\n\nSEARCH RESULTS:\n{search_results[:12000]}"

    for retry in range(5):
        log(f"  Calling Claude (attempt {retry + 1})…")
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            )
            break
        except anthropic.RateLimitError:
            wait = 65 * (retry + 1)
            log(f"  Rate limit hit — waiting {wait}s…")
            time.sleep(wait)
    else:
        raise RuntimeError("Rate limit retries exhausted.")

    for block in response.content:
        if hasattr(block, "text"):
            text = block.text.strip()
            start = text.find("{")
            end   = text.rfind("}") + 1
            if start != -1 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError as exc:
                    raise ValueError(f"JSON parse error: {exc}\n\n{text[start:end][:600]}")
    raise ValueError("Response ended but contained no JSON.")


# ── HTML builder ───────────────────────────────────────────────────────────────

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
    # ── Summary box ──
    summary     = data.get("summary", {})
    overview    = summary.get("overview", "")
    recs        = summary.get("messaging_recommendations", [])
    changes     = changes or []

    changes_html = "".join(f"<li>{c}</li>" for c in changes)
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

    # ── Rate cases ──
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

    # ── Articles (sorted newest first) ──
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
        <div class="meta">{art.get("source","")} · {art.get("date","")}</div>
      </div>"""

    if not articles_html:
        articles_html = '<p class="empty">No recent articles found.</p>'

    # ── Stakeholders ──
    stakeholders_html = ""
    for s in data.get("stakeholders", []):
        stakeholders_html += f"""
      <div class="card">
        <blockquote>"{s.get("quote","")}"</blockquote>
        <div class="attribution">
          <strong>{s.get("name","")}</strong>
          <span>{s.get("title","")}, {s.get("organization","")}</span>
        </div>
        <div class="meta">{s.get("source","")} · {s.get("date","")}</div>
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


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    log("━━━ Dashboard update started ━━━")
    client = anthropic.Anthropic()

    prev_data = load_previous_data()

    log("Researching rate cases, articles, and stakeholder quotes…")
    try:
        data = research(client)
    except Exception as exc:
        log(f"ERROR during research: {exc}")
        sys.exit(1)

    log(
        f"Research complete — "
        f"{len(data.get('rate_cases', []))} rate cases, "
        f"{len(data.get('articles', []))} articles, "
        f"{len(data.get('stakeholders', []))} quotes"
    )

    changes = compute_changes(prev_data, data)
    log(f"Changes detected: {len(changes)}")

    updated_at = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    html = build_html(data, updated_at, changes)
    DASHBOARD_PATH.write_text(html, encoding="utf-8")
    log(f"Dashboard written → {DASHBOARD_PATH}")

    PREV_DATA_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    log(f"Previous data saved → {PREV_DATA_PATH}")
    log("━━━ Done ━━━")


if __name__ == "__main__":
    main()
