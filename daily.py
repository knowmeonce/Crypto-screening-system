"""
Daily orchestrator — the Phase 3 "re-run everything, every day" job.
Ties together discovery, the Phase 1 pipeline, Phase 2 scoring, and
alert detection, and writes the JSON the Phase 4 dashboard reads.

Every tracked coin gets re-screened on every run, not just at initial
discovery — a coin can fail a filter later even if it passed
yesterday, and this is the only way alerts.py has anything to compare
against.
"""

import json
import os
import time

import config
import history
import discover
from screen import screen_coin
from scoring.narrative import record_daily_snapshot, compute_bucket_momentum
from alerts import detect_coin_alerts, detect_bucket_momentum_flip
from bucket_proposals import propose_new_buckets
from sources import coingecko, defillama


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def load_watchlist() -> list[dict]:
    if not os.path.exists(config.WATCHLIST_PATH):
        return []
    with open(config.WATCHLIST_PATH) as f:
        return json.load(f)


def save_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def merge_watchlist(watchlist: list[dict], candidates: list[dict], today: str) -> list[dict]:
    existing = {(c["chain"], c["token_address"].lower()) for c in watchlist}
    for cand in candidates:
        key = (cand["chain"], cand["token_address"].lower())
        if key in existing:
            continue
        watchlist.append({
            "chain": cand["chain"],
            "token_address": cand["token_address"],
            "symbol": cand.get("token_symbol"),
            "name": cand.get("token_name"),
            "coingecko_id": None,
            "defillama_slug": None,
            "first_seen": today,
        })
        existing.add(key)
    return watchlist


def resolve_coingecko_id(entry: dict) -> str | None:
    if entry.get("coingecko_id"):
        return entry["coingecko_id"]
    platform = config.COINGECKO_PLATFORM_IDS.get(entry["chain"])
    if not platform:
        return None
    try:
        return coingecko.get_coin_id_by_contract(platform, entry["token_address"])
    except Exception:
        return None


def build_defillama_slug_index() -> dict:
    """
    Cheap, one-time-per-run symbol->slug index so alt coins that do
    have a DeFiLlama-tracked protocol get their TVL trend wired up
    automatically, without an expensive per-coin lookup call. Symbol
    matching is approximate (collisions are possible) — good enough
    for the protocol-activity score component, which already treats
    missing TVL as neutral rather than failing.
    """
    try:
        protocols = defillama.list_all_protocols()
    except Exception:
        return {}
    index = {}
    for p in protocols:
        symbol = (p.get("symbol") or "").upper()
        if symbol and symbol not in index:
            index[symbol] = p.get("slug")
    return index


def prune_watchlist(watchlist: list[dict], score_by_key: dict[str, float]) -> list[dict]:
    if len(watchlist) <= config.MAX_WATCHLIST_SIZE:
        return watchlist
    watchlist = sorted(
        watchlist,
        key=lambda e: score_by_key.get(history.token_key(e["chain"], e["token_address"]), -1),
        reverse=True,
    )
    return watchlist[: config.MAX_WATCHLIST_SIZE]


def run() -> dict:
    today = _today()
    watchlist = load_watchlist()

    discovery_result = discover.discover_candidates()
    watchlist = merge_watchlist(watchlist, discovery_result["candidates"], today)

    # Bucket momentum "as of yesterday" has to be read before today's
    # category snapshot is appended, or there'd be nothing to diff
    # against for the momentum-flip alert.
    momentum_yesterday = {b: compute_bucket_momentum(b) for b in config.NARRATIVE_BUCKETS}

    try:
        categories_data = coingecko.get_categories_market_data()
    except Exception:
        categories_data = []
    try:
        global_data = coingecko.get_global_market_data()
    except Exception:
        global_data = {}
    record_daily_snapshot(categories_data, global_data)

    defillama_index = build_defillama_slug_index()

    scored_records = []
    all_alerts = []
    pipeline_errors = {}

    for entry in watchlist:
        chain = entry["chain"]
        token_address = entry["token_address"]
        label = entry.get("symbol") or token_address[:10]

        entry["coingecko_id"] = resolve_coingecko_id(entry)

        if not entry.get("defillama_slug") and entry.get("symbol"):
            entry["defillama_slug"] = defillama_index.get(entry["symbol"].upper())

        key = history.token_key(chain, token_address)
        entries_before = history.load_history(key)
        yesterday_snapshot = entries_before[-1] if entries_before else None

        try:
            result = screen_coin(chain, token_address, entry["coingecko_id"], entry.get("defillama_slug"), record_history=True)
        except Exception as e:
            pipeline_errors[label] = str(e)
            continue

        entries_after = history.load_history(key)
        market_cap_trend_pct = None
        if len(entries_after) > 1:
            t = history.trend(entries_after, "market_cap_usd", days_ago=min(7, len(entries_after) - 1))
            market_cap_trend_pct = t.get("pct_change")

        result["symbol"] = result["symbol"] or entry.get("symbol")
        result["name"] = result["name"] or entry.get("name")
        result["market_cap_trend_pct"] = market_cap_trend_pct
        result["first_seen"] = entry.get("first_seen")
        scored_records.append(result)

        today_snapshot = entries_after[-1] if entries_after else {}
        all_alerts.extend(detect_coin_alerts(
            label, yesterday_snapshot, today_snapshot,
            result["hard_filter_result"].get("passed", False),
            yesterday_snapshot.get("hard_filters_passed") if yesterday_snapshot else None,
        ))

        if result["dca_eligibility"]["eligible"]:
            all_alerts.extend(detect_bucket_momentum_flip(
                label, result["narrative_bucket"],
                momentum_yesterday.get(result["narrative_bucket"]),
                result["bucket_momentum"],
            ))

        time.sleep(config.PER_COIN_DELAY_SECONDS)

    score_by_key = {
        history.token_key(r["chain"], r["token_address"]): r["final_score"]
        for r in scored_records
    }
    watchlist = prune_watchlist(watchlist, score_by_key)

    uncategorized = [r for r in scored_records if r["narrative_bucket"] == "uncategorized"]
    proposals = propose_new_buckets(uncategorized)

    save_json(config.WATCHLIST_PATH, watchlist)
    save_json(config.LATEST_PATH, {
        "date": today,
        "records": scored_records,
        "pipeline_errors": pipeline_errors,
        "discovery_errors": discovery_result["errors"],
    })
    save_json(f"{config.DATA_DIR}/alerts.json", {"date": today, "alerts": all_alerts})
    save_json(config.BUCKET_PROPOSALS_PATH, {"date": today, "proposals": proposals})

    return {"scored": len(scored_records), "alerts": len(all_alerts), "proposals": len(proposals)}


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
