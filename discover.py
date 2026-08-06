"""
Daily candidate discovery: scans GeckoTerminal's new-pool and
trending-pool feeds across every configured chain, and returns a
deduped list of (chain, token_address) candidates ready to hand to
pipeline.collect_token_data().

Each network is scanned independently and failures are per-network,
not fatal to the whole run — one chain's GeckoTerminal endpoint being
slow or down shouldn't stop discovery on the other four.
"""

from config import GECKOTERMINAL_NETWORKS, DISCOVERY_POOLS_PER_NETWORK, DISCOVERY_MIN_LIQUIDITY_USD
from sources import geckoterminal


def discover_candidates() -> dict:
    """
    Returns {"candidates": [{"chain": ..., "token_address": ...,
    "token_symbol": ..., "token_name": ..., "source": "new"|"trending"}],
    "errors": {network: error}} — errors are reported, never swallowed
    silently, same fail-safe pattern as the rest of the pipeline.
    """
    seen: set[tuple[str, str]] = set()
    candidates = []
    errors = {}

    for gt_network, chain in GECKOTERMINAL_NETWORKS.items():
        for source_name, fetch in (("new", geckoterminal.get_new_pools), ("trending", geckoterminal.get_trending_pools)):
            try:
                pools = fetch(gt_network, limit=DISCOVERY_POOLS_PER_NETWORK)
            except Exception as e:
                errors[f"{gt_network}:{source_name}"] = str(e)
                continue

            for pool in pools:
                liquidity = pool.get("reserve_in_usd")
                try:
                    if liquidity is not None and float(liquidity) < DISCOVERY_MIN_LIQUIDITY_USD:
                        continue
                except (TypeError, ValueError):
                    pass

                address = pool.get("token_address")
                if not address:
                    continue
                key = (chain, address.lower())
                if key in seen:
                    continue
                seen.add(key)

                candidates.append({
                    "chain": chain,
                    "token_address": address,
                    "token_symbol": pool.get("token_symbol"),
                    "token_name": pool.get("token_name"),
                    "source": source_name,
                })

    return {"candidates": candidates, "errors": errors}
