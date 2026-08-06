"""
Bucket-approval flow (Phase 4's proposal cards, computed here in the
daily run so the dashboard only has to render pre-computed data).

Looks for a cluster of UNCATEGORIZED coins that share a raw CoinGecko
category tag not covered by any of config.NARRATIVE_BUCKETS' keyword
lists, where enough of them are showing real momentum together to be
worth a human looking at. Never adds a bucket itself — this only ever
produces a proposal for a person to accept or reject by editing
config.NARRATIVE_BUCKETS themselves; see dashboard.py's rendering of
these cards for exactly what "approve" means given this is a static
site with no backend to persist a click.
"""

from collections import defaultdict

MIN_CLUSTER_SIZE = 3
MIN_POSITIVE_MOMENTUM_SHARE = 0.6  # fraction of the cluster that must be up over the trailing week


def propose_new_buckets(uncategorized_records: list[dict]) -> list[dict]:
    """
    uncategorized_records: scored records already filtered to
    coin_type bucket == "uncategorized", each expected to carry
    "raw_categories" (the coin's full CoinGecko category list) and
    "market_cap_trend_pct" (7-day, from history — None if not yet
    available).
    """
    by_tag: dict[str, list[dict]] = defaultdict(list)
    for record in uncategorized_records:
        for tag in record.get("raw_categories", []):
            by_tag[tag].append(record)

    proposals = []
    for tag, coins in by_tag.items():
        if len(coins) < MIN_CLUSTER_SIZE:
            continue

        with_trend = [c for c in coins if c.get("market_cap_trend_pct") is not None]
        if not with_trend:
            continue

        positive = [c for c in with_trend if c["market_cap_trend_pct"] > 0]
        if len(positive) / len(with_trend) < MIN_POSITIVE_MOMENTUM_SHARE:
            continue

        avg_momentum = round(sum(c["market_cap_trend_pct"] for c in with_trend) / len(with_trend), 2)
        proposals.append({
            "proposed_bucket_name": tag,
            "coin_count": len(coins),
            "coins": [{"symbol": c.get("symbol"), "name": c.get("name"), "market_cap_trend_pct": c.get("market_cap_trend_pct")} for c in coins],
            "avg_market_cap_trend_pct": avg_momentum,
            "evidence": f"{len(positive)} of {len(with_trend)} coins tagged \"{tag}\" are up over the trailing week (avg {avg_momentum:+.1f}%), and none currently fit an existing bucket.",
        })

    return proposals
