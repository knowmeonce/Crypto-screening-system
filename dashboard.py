"""
Phase 4: builds the static dashboard HTML from data/latest.json,
data/alerts.json, and data/bucket_proposals.json.

Everything interactive (card expand/collapse, glossary tooltips,
search/filter, bucket-proposal dismiss) is plain client-side JS
operating on data embedded directly in the page — no server, no
build step beyond this script, matching the "just a link I open"
constraint. See lookup.py's docstring for why the search box filters
today's already-tracked coins rather than accepting an arbitrary new
address.
"""

import html
import json
import os
import re

import config


def load_json(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


def _glossary_pattern():
    terms = sorted(config.GLOSSARY.keys(), key=len, reverse=True)
    escaped = [re.escape(t) for t in terms]
    return re.compile(r"\b(" + "|".join(escaped) + r")\b", re.IGNORECASE)


_GLOSSARY_RE = _glossary_pattern()
_ANNOTATED_IN_CARD: set[str] = set()


def annotate_glossary_terms(text: str, seen: set[str]) -> str:
    """
    Wraps the first mention of each glossary term in a card with a
    hoverable/tappable info span. Only the first mention per card, so
    a paragraph that says "concentration" three times doesn't get
    three identical icons.
    """
    escaped = html.escape(text)

    def replace(match: re.Match) -> str:
        term = match.group(1)
        key = term.lower()
        if key in seen or key not in config.GLOSSARY:
            return term
        seen.add(key)
        definition = html.escape(config.GLOSSARY[key])
        return f'<span class="term" tabindex="0">{term}<span class="info-icon">ⓘ<span class="tooltip">{definition}</span></span></span>'

    return _GLOSSARY_RE.sub(replace, escaped)


def _trend_arrow(pct):
    if pct is None:
        return "—"
    if pct > 1:
        return f"▲ {pct:+.1f}%"
    if pct < -1:
        return f"▼ {pct:+.1f}%"
    return f"▬ {pct:+.1f}%"


def render_coin_card(record: dict, index: int, is_shortlist: bool = False) -> str:
    seen_terms: set[str] = set()
    symbol = html.escape(record.get("symbol") or "?")
    name = html.escape(record.get("name") or record.get("token_address", "")[:12])
    bucket = html.escape(record.get("narrative_bucket") or "uncategorized")
    coin_type = record.get("coin_type", "alt")
    score = record.get("final_score", 0)
    passed = record.get("hard_filter_result", {}).get("passed", False)
    liquidity = (record.get("liquidity") or {}).get("total_liquidity_usd")
    concentration = (record.get("concentration") or {}).get("top_10_pct")

    metric_bits = []
    if liquidity is not None:
        metric_bits.append(f"${liquidity:,.0f} liquidity")
    if concentration is not None:
        metric_bits.append(f"{concentration:.1f}% top-10 concentration")
    one_line = html.escape(" · ".join(metric_bits) if metric_bits else "insufficient market data")

    justification_html = annotate_glossary_terms(record.get("justification", ""), seen_terms)

    growth_html = ""
    if is_shortlist:
        gt = (record.get("dca_eligibility") or {}).get("growth_trajectory") or {}
        parts = []
        if gt.get("holder_trend_pct") is not None:
            parts.append(f"holders {_trend_arrow(gt['holder_trend_pct'])}")
        if gt.get("volume_trend_pct") is not None:
            parts.append(f"volume {_trend_arrow(gt['volume_trend_pct'])}")
        if gt.get("tvl_trend_pct") is not None:
            parts.append(f"TVL {_trend_arrow(gt['tvl_trend_pct'])}")
        growth_html = f'<div class="growth-indicator">{html.escape(" · ".join(parts)) if parts else "trend data pending"}</div>'

    status_class = "pass" if passed else "fail"
    status_label = "passed filters" if passed else "FAILED FILTERS"
    card_id = f"card-{index}"

    return f"""
<div class="coin-card {status_class}" data-symbol="{symbol.lower()}" data-name="{name.lower()}">
  <button class="card-head" aria-expanded="false" data-target="{card_id}">
    <div class="card-head-main">
      <span class="symbol">{symbol}</span>
      <span class="name">{name}</span>
      <span class="bucket-tag">{bucket}</span>
      <span class="status-badge {status_class}">{status_label}</span>
    </div>
    <div class="card-head-sub">
      <span class="score">{score:.1f}<span class="score-max">/100</span></span>
      <span class="one-line">{one_line}</span>
    </div>
    {growth_html}
  </button>
  <div class="card-body" id="{card_id}" hidden>
    <p>{justification_html}</p>
  </div>
</div>"""


def render_stat_tiles(latest: dict, alerts: list, dca_count: int) -> str:
    records = latest.get("records", [])
    new_today = sum(1 for r in records if r.get("first_seen") == latest.get("date"))
    passed = sum(1 for r in records if r.get("hard_filter_result", {}).get("passed"))

    tiles = [
        ("New candidates today", new_today),
        ("Passed hard filters", passed),
        ("Alerts", len(alerts)),
        ("DCA shortlist", dca_count),
    ]
    tiles_html = "".join(
        f'<div class="tile"><div class="tile-value">{v}</div><div class="tile-label">{html.escape(k)}</div></div>'
        for k, v in tiles
    )
    return f'<div class="tiles">{tiles_html}</div>'


def render_alerts(alerts: list) -> str:
    if not alerts:
        return '<p class="empty-state">No alerts today.</p>'
    items = "".join(f'<li class="alert-{html.escape(a["type"])}">{html.escape(a["message"])}</li>' for a in alerts)
    return f'<ul class="alerts-list">{items}</ul>'


def render_bucket_proposals(proposals: list) -> str:
    if not proposals:
        return '<p class="empty-state">No new narrative buckets proposed today.</p>'

    cards = []
    for i, p in enumerate(proposals):
        coins = ", ".join(f"{c.get('symbol') or '?'} ({c.get('market_cap_trend_pct', 0):+.1f}%)" for c in p["coins"])
        cards.append(f"""
<div class="proposal-card" id="proposal-{i}">
  <div class="proposal-title">Proposed bucket: "{html.escape(p['proposed_bucket_name'])}"</div>
  <p>{html.escape(p['evidence'])}</p>
  <p class="proposal-coins">Coins: {html.escape(coins)}</p>
  <div class="proposal-actions">
    <button class="dismiss-btn" data-target="proposal-{i}">Dismiss</button>
    <span class="approve-note">To approve: add "{html.escape(p['proposed_bucket_name'])}" to NARRATIVE_BUCKETS in config.py and let the next scheduled run pick it up — nothing here auto-adds a bucket.</span>
  </div>
</div>""")
    return "".join(cards)


PAGE_CSS = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  margin: 0; padding: 0 1rem 4rem;
  background: #0f1115; color: #e6e6e6;
  max-width: 900px; margin-inline: auto;
}
@media (prefers-color-scheme: light) {
  body { background: #fafafa; color: #1a1a1a; }
}
header { padding: 2rem 0 1rem; }
h1 { font-size: 1.5rem; margin: 0 0 0.25rem; }
.subtitle { color: #999; font-size: 0.9rem; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 0.75rem; margin: 1.5rem 0; }
.tile { background: rgba(127,127,127,0.1); border-radius: 10px; padding: 1rem; text-align: center; }
.tile-value { font-size: 1.8rem; font-weight: 700; }
.tile-label { font-size: 0.8rem; color: #999; margin-top: 0.25rem; }
section { margin: 2.5rem 0; }
h2 { font-size: 1.15rem; border-bottom: 1px solid rgba(127,127,127,0.3); padding-bottom: 0.5rem; }
input#search {
  width: 100%; padding: 0.75rem; border-radius: 8px; border: 1px solid rgba(127,127,127,0.4);
  background: transparent; color: inherit; font-size: 1rem; margin-bottom: 1rem;
}
.coin-card { border: 1px solid rgba(127,127,127,0.25); border-radius: 10px; margin-bottom: 0.6rem; overflow: hidden; }
.coin-card.fail { border-color: rgba(220,60,60,0.5); }
.card-head { width: 100%; text-align: left; background: rgba(127,127,127,0.06); border: none; color: inherit; cursor: pointer; padding: 0.85rem 1rem; font: inherit; }
.card-head-main { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
.symbol { font-weight: 700; }
.name { color: #aaa; font-size: 0.9rem; }
.bucket-tag { font-size: 0.75rem; background: rgba(100,140,255,0.15); color: #7fa8ff; padding: 0.15rem 0.5rem; border-radius: 999px; }
.status-badge { font-size: 0.7rem; padding: 0.15rem 0.5rem; border-radius: 999px; margin-left: auto; }
.status-badge.pass { background: rgba(60,180,90,0.15); color: #4fce78; }
.status-badge.fail { background: rgba(220,60,60,0.2); color: #ff7b7b; }
.card-head-sub { display: flex; align-items: baseline; gap: 0.75rem; margin-top: 0.4rem; }
.score { font-size: 1.3rem; font-weight: 700; }
.score-max { font-size: 0.75rem; color: #888; font-weight: 400; }
.one-line { font-size: 0.85rem; color: #999; }
.growth-indicator { margin-top: 0.35rem; font-size: 0.8rem; color: #7fa8ff; }
.card-body { padding: 0 1rem 1rem; font-size: 0.92rem; line-height: 1.5; color: #ccc; }
.term { border-bottom: 1px dotted #888; position: relative; cursor: help; }
.info-icon { font-size: 0.8em; color: #7fa8ff; margin-left: 0.15em; position: relative; }
.info-icon .tooltip {
  display: none; position: absolute; bottom: 140%; left: 50%; transform: translateX(-50%);
  background: #222; color: #fff; padding: 0.5rem 0.7rem; border-radius: 6px; font-size: 0.78rem;
  width: max-content; max-width: 240px; line-height: 1.4; z-index: 10; box-shadow: 0 4px 12px rgba(0,0,0,0.4);
}
.term:hover .tooltip, .term:focus .tooltip, .info-icon:hover .tooltip { display: block; }
.alerts-list { padding-left: 1.2rem; }
.alerts-list li { margin-bottom: 0.4rem; }
.empty-state { color: #888; font-style: italic; }
.proposal-card { border: 1px dashed rgba(127,127,127,0.4); border-radius: 10px; padding: 1rem; margin-bottom: 0.75rem; }
.proposal-title { font-weight: 700; margin-bottom: 0.4rem; }
.proposal-coins { font-size: 0.85rem; color: #999; }
.proposal-actions { display: flex; align-items: center; gap: 1rem; margin-top: 0.5rem; flex-wrap: wrap; }
.dismiss-btn { background: rgba(127,127,127,0.15); border: none; border-radius: 6px; padding: 0.4rem 0.8rem; color: inherit; cursor: pointer; }
.approve-note { font-size: 0.78rem; color: #888; }
footer { color: #777; font-size: 0.8rem; margin-top: 3rem; }
"""

PAGE_JS = """
document.addEventListener('click', function (e) {
  var head = e.target.closest('.card-head');
  if (head) {
    var body = document.getElementById(head.dataset.target);
    var expanded = head.getAttribute('aria-expanded') === 'true';
    head.setAttribute('aria-expanded', String(!expanded));
    body.hidden = expanded;
    return;
  }
  var dismiss = e.target.closest('.dismiss-btn');
  if (dismiss) {
    var card = document.getElementById(dismiss.dataset.target);
    if (card) card.remove();
  }
});

var search = document.getElementById('search');
if (search) {
  search.addEventListener('input', function () {
    var q = search.value.trim().toLowerCase();
    document.querySelectorAll('.coin-card').forEach(function (card) {
      var match = !q || card.dataset.symbol.includes(q) || card.dataset.name.includes(q);
      card.style.display = match ? '' : 'none';
    });
  });
}
"""


def build_page(latest: dict, alerts_data: dict, proposals_data: dict) -> str:
    records = latest.get("records", [])
    records_sorted = sorted(records, key=lambda r: r.get("final_score", 0), reverse=True)
    shortlist = sorted(
        [r for r in records if r.get("dca_eligibility", {}).get("eligible")],
        key=lambda r: r.get("final_score", 0), reverse=True,
    )

    system1_html = "".join(render_coin_card(r, i) for i, r in enumerate(records_sorted)) or '<p class="empty-state">No candidates scored yet.</p>'
    system2_html = "".join(render_coin_card(r, i, is_shortlist=True) for i, r in enumerate(shortlist)) or '<p class="empty-state">No coins currently meet the DCA growth-trajectory bar.</p>'

    date = html.escape(latest.get("date", "unknown"))
    stats = render_stat_tiles(latest, alerts_data.get("alerts", []), len(shortlist))
    alerts_html = render_alerts(alerts_data.get("alerts", []))
    proposals_html = render_bucket_proposals(proposals_data.get("proposals", []))

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Crypto Screening & DCA Dashboard — {date}</title>
<style>{PAGE_CSS}</style>
</head>
<body>
<header>
  <h1>Crypto Screening &amp; DCA Dashboard</h1>
  <div class="subtitle">Run date: {date} &middot; free data sources only, updated daily</div>
</header>

{stats}

<input id="search" type="search" placeholder="Search tracked coins by symbol or name…">

<section>
  <h2>Alerts</h2>
  {alerts_html}
</section>

<section>
  <h2>Proposed narrative buckets</h2>
  {proposals_html}
</section>

<section>
  <h2>System 1 — Discovery &amp; screening ({len(records_sorted)} tracked)</h2>
  {system1_html}
</section>

<section>
  <h2>System 2 — DCA shortlist ({len(shortlist)})</h2>
  {system2_html}
</section>

<footer>
  Generated automatically. Scores are heuristics from free public data — not financial advice.
</footer>

<script>{PAGE_JS}</script>
</body>
</html>"""


def main() -> None:
    latest = load_json(config.LATEST_PATH, {"date": "never run", "records": []})
    alerts_data = load_json(config.ALERTS_PATH, {"alerts": []})
    proposals_data = load_json(config.BUCKET_PROPOSALS_PATH, {"proposals": []})

    page = build_page(latest, alerts_data, proposals_data)

    os.makedirs(config.SITE_DIR, exist_ok=True)
    with open(os.path.join(config.SITE_DIR, "index.html"), "w") as f:
        f.write(page)


if __name__ == "__main__":
    main()
