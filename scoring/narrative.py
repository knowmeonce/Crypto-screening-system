"""
Narrative bucket classification and bucket-momentum tracking.

Classification is CoinGecko category tags -> our own coarser bucket
names (config.NARRATIVE_BUCKETS), since CoinGecko has hundreds of
fine-grained categories and the spec's buckets are deliberately
broader themes.

Momentum is measured against real whole-market data (CoinGecko's own
per-category market caps and global total), not approximated from our
own small tracked subset — see sources/coingecko.py's
get_categories_market_data()/get_global_market_data() docstrings.
"""

import re

import history
from config import NARRATIVE_BUCKETS, MEME_BUCKETS

UNCATEGORIZED = "uncategorized"


def bucket_slug(bucket: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", bucket.lower()).strip("_")


def classify_bucket(categories: list[str]) -> str:
    """
    First bucket whose keywords match any of the coin's CoinGecko
    categories wins (case-insensitive substring match). No match is
    UNCATEGORIZED — a real, trackable state (feeds the bucket-approval
    flow), not an error.
    """
    if not categories:
        return UNCATEGORIZED

    lowered = [c.lower() for c in categories]
    for bucket, keywords in NARRATIVE_BUCKETS.items():
        for keyword in keywords:
            if any(keyword in cat for cat in lowered):
                return bucket
    return UNCATEGORIZED


def is_meme_bucket(bucket: str) -> bool:
    return bucket in MEME_BUCKETS


def record_daily_snapshot(categories_data: list[dict], global_data: dict) -> dict[str, float]:
    """
    Sums CoinGecko's per-category market caps into our custom buckets
    and persists today's bucket totals + the global total to history,
    one history file per bucket (key "_bucket_<slug>") plus one for
    the market-wide baseline (key "_market_global").

    Returns today's bucket -> total_market_cap_usd, for immediate use
    by compute_bucket_momentum() without re-reading from disk.
    """
    bucket_totals: dict[str, float] = {b: 0.0 for b in NARRATIVE_BUCKETS}

    for cat in categories_data:
        name = (cat.get("name") or "").lower()
        mcap = cat.get("market_cap") or 0
        for bucket, keywords in NARRATIVE_BUCKETS.items():
            if any(keyword in name for keyword in keywords):
                bucket_totals[bucket] += mcap
                break  # a raw category counts toward one bucket only

    for bucket, total in bucket_totals.items():
        key = f"_bucket_{bucket_slug(bucket)}"
        history.append_snapshot(key, {"total_market_cap_usd": total})

    global_mcap = global_data.get("total_market_cap_usd")
    if global_mcap is not None:
        history.append_snapshot("_market_global", {"total_market_cap_usd": global_mcap})

    return bucket_totals


def compute_bucket_momentum(bucket: str, days_ago: int = 7) -> dict:
    """
    Bucket's trailing-week market cap growth vs the whole market's
    growth over the same period, plus whether that momentum is
    accelerating or decelerating week over week.

    Needs at least 2*days_ago+1 daily snapshots for the acceleration
    read (fewer is enough for the plain momentum number) — reports
    insufficient_history rather than guessing, same as the rest of
    this codebase.
    """
    if bucket == UNCATEGORIZED:
        return {
            "bucket_pct_change": None, "market_pct_change": None,
            "momentum": None, "acceleration": None, "insufficient_history": True,
        }

    bucket_entries = history.load_history(f"_bucket_{bucket_slug(bucket)}")
    market_entries = history.load_history("_market_global")

    bucket_trend = history.trend(bucket_entries, "total_market_cap_usd", days_ago)
    market_trend = history.trend(market_entries, "total_market_cap_usd", days_ago)

    if bucket_trend["insufficient_history"] or market_trend["insufficient_history"]:
        return {
            "bucket_pct_change": bucket_trend["pct_change"],
            "market_pct_change": market_trend["pct_change"],
            "momentum": None, "acceleration": None, "insufficient_history": True,
        }

    momentum = round(bucket_trend["pct_change"] - market_trend["pct_change"], 2)
    accel = history.acceleration(bucket_entries, "total_market_cap_usd", days_ago)

    return {
        "bucket_pct_change": bucket_trend["pct_change"],
        "market_pct_change": market_trend["pct_change"],
        "momentum": momentum,
        "acceleration": accel["direction"],
        "insufficient_history": False,
    }
