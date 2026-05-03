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

SCRIPT_DIR = Path(__file__).parent
DASHBOARD_PATH = SCRIPT_DIR / "dashboard.html"
LOG_PATH = SCRIPT_DIR / "update.log"

# ── Research prompt ────────────────────────────────────────────────────────────

RESEARCH_PROMPT = """
You are a policy researcher specializing in Indiana energy affordability.
Search the web thoroughly and gather current, accurate information on the
three topics below. Use multiple searches per topic.

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
OUTPUT FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Return ONLY a valid JSON object — no text before or after it.
Use this exact structure:

{
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

Search thoroughly. Only include real, verifiable information.
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


def research(client: anthropic.Anthropic) -> dict:
    """Run the research loop — handles server-side tool pagination."""
    tools = [
        {"type": "web_search_20260209", "name": "web_search"},
        {"type": "web_fetch_20260209",  "name": "web_fetch"},
    ]
    messages = [{"role": "user", "content": RESEARCH_PROMPT}]
    container_id = None

    for attempt in range(6):  # up to 6 continuation calls
        log(f"  API call {attempt + 1}…")
        kwargs = dict(
            model="claude-sonnet-4-6",
            max_tokens=6000,
            tools=tools,
            messages=messages,
        )
        if container_id:
            kwargs["container_id"] = container_id

        for retry in range(5):
            try:
                response = client.messages.create(**kwargs)
                break
            except anthropic.RateLimitError:
                wait = 65 * (retry + 1)
                log(f"  Rate limit hit — waiting {wait}s before retry {retry + 1}/5…")
                time.sleep(wait)
        else:
            raise RuntimeError("Rate limit retries exhausted.")

        if hasattr(response, "container_id") and response.container_id:
            container_id = response.container_id

        if response.stop_reason == "end_turn":
            # Extract the JSON block from the final text response
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

        if response.stop_reason == "pause_turn":
            # Server-side tools hit their iteration cap — append and continue.
            messages.append({"role": "assistant", "content": response.content})
            continue

        raise ValueError(f"Unexpected stop_reason: {response.stop_reason!r}")

    raise RuntimeError("Exceeded max continuation attempts without a final response.")


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


def build_html(data: dict, updated_at: str) -> str:
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

    # ── Articles ──
    articles_html = ""
    for art in data.get("articles", []):
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

    updated_at = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    html = build_html(data, updated_at)
    DASHBOARD_PATH.write_text(html, encoding="utf-8")
    log(f"Dashboard written → {DASHBOARD_PATH}")
    log("━━━ Done ━━━")


if __name__ == "__main__":
    main()
