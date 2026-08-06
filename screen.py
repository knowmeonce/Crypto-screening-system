"""
The single-coin screening path: pipeline collection -> classification
-> history update -> scoring -> narrative tailwind -> DCA gate ->
justification. Shared by daily.py (the scheduled run, looping over
the whole watchlist) and lookup.py (the on-demand single-coin check),
so an ad hoc lookup can never produce a different verdict than the
daily run would for the same coin on the same day — same code path,
just called for one coin instead of the whole list.
"""

import history
from pipeline import collect_token_data
from scoring.narrative import classify_bucket, compute_bucket_momentum
from scoring.rubrics import classify_coin_type, score_alt_coin, score_meme_coin, apply_narrative_tailwind
from scoring.growth_gate import evaluate_dca_eligibility
from scoring.justify import build_justification


def screen_coin(chain: str, token_address: str, coingecko_id: str | None = None,
                 defillama_slug: str | None = None, record_history: bool = True) -> dict:
    """
    record_history controls whether this call writes a snapshot to
    disk. daily.py always does (that's the whole point of the
    scheduled run); lookup.py defaults to NOT writing one, so an ad
    hoc check of a coin that isn't already tracked doesn't silently
    start a new history series with a single point mid-day, which
    would misrepresent that coin as having been tracked since today.
    """
    record = collect_token_data(coingecko_id or "", token_address, chain, defillama_slug)

    market = record.get("market") or {}
    security = record.get("security") or {}
    concentration = record.get("concentration") or {}
    liquidity = record.get("liquidity") or {}
    tvl_trend = record.get("tvl_trend") or {}
    categories = market.get("categories") or []

    bucket = classify_bucket(categories)
    coin_type = classify_coin_type(record)
    hard_filter_result = record.get("hard_filter_result") or {"passed": False, "failures": ["hard filter check unavailable"]}

    key = history.token_key(chain, token_address)
    entries = history.load_history(key)

    if record_history:
        snapshot = {
            "holder_count": security.get("holder_count"),
            "top_10_pct": concentration.get("top_10_pct"),
            "total_liquidity_usd": liquidity.get("total_liquidity_usd"),
            "volume_usd_h24": liquidity.get("top_pair_volume_24h_usd"),
            "tvl_usd": tvl_trend.get("tvl_now"),
            "market_cap_usd": market.get("market_cap_usd"),
            "hard_filters_passed": hard_filter_result.get("passed", False),
        }
        history.append_snapshot(key, snapshot)
        entries = history.load_history(key)

    holder_growth = history.acceleration(entries, "holder_count", window_days=7)
    score_result = score_meme_coin(record, holder_growth) if coin_type == "meme" else score_alt_coin(record)

    bucket_momentum = compute_bucket_momentum(bucket)
    tailwind = apply_narrative_tailwind(score_result["total"], bucket_momentum)
    dca = evaluate_dca_eligibility(tailwind["final_score"], hard_filter_result.get("passed", False), entries)
    justification = build_justification(coin_type, bucket, hard_filter_result, score_result, tailwind, dca)

    return {
        "chain": chain,
        "token_address": token_address,
        "coingecko_id": coingecko_id,
        "symbol": market.get("symbol"),
        "name": market.get("name"),
        "coin_type": coin_type,
        "narrative_bucket": bucket,
        "raw_categories": categories,
        "hard_filter_result": hard_filter_result,
        "score": score_result,
        "bucket_momentum": bucket_momentum,
        "tailwind": tailwind,
        "final_score": tailwind["final_score"],
        "dca_eligibility": dca,
        "justification": justification,
        "market_cap_usd": market.get("market_cap_usd"),
        "price_usd": market.get("price_usd"),
        "fdv_to_mcap_ratio": record.get("fdv_to_mcap_ratio"),
        "concentration": concentration,
        "liquidity": liquidity,
        "errors": record.get("errors", {}),
        "history_days": len(entries),
    }
