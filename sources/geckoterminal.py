"""
GeckoTerminal connector (CoinGecko's on-chain DEX data product).

This is the discovery engine's raw candidate source: new pools and
trending pools, per chain, free and unauthenticated. This is what
finds tokens before CoinGecko's own coin listing has heard of them —
a brand-new meme coin can have a live pool on GeckoTerminal for days
or weeks before it gets a CoinGecko id, which is normal and expected,
not a data gap to route around.

Response shape is JSON:API (data + included, related by type/id) —
parsed defensively since a malformed or partial entry should be
skipped, not crash the whole discovery run.
"""

import requests
from config import GECKOTERMINAL_BASE, REQUEST_TIMEOUT_SECONDS


def _extract_pools(payload: dict) -> list[dict]:
    """
    Flattens a GeckoTerminal pools response (JSON:API) into simple
    dicts: token address/symbol/name for the base token, plus the
    pool's own liquidity/volume/fdv figures. Entries missing a base
    token address are skipped — nothing to screen without one.
    """
    included = {
        (item.get("type"), item.get("id")): item
        for item in payload.get("included", [])
    }

    pools = []
    for entry in payload.get("data", []):
        attrs = entry.get("attributes", {})
        rel = entry.get("relationships", {})
        base_token_ref = (rel.get("base_token") or {}).get("data") or {}
        base_token = included.get((base_token_ref.get("type"), base_token_ref.get("id")))
        if not base_token:
            continue

        token_attrs = base_token.get("attributes", {})
        token_address = token_attrs.get("address")
        if not token_address:
            continue

        pools.append({
            "token_address": token_address,
            "token_symbol": token_attrs.get("symbol"),
            "token_name": token_attrs.get("name"),
            "pool_address": attrs.get("address"),
            "fdv_usd": attrs.get("fdv_usd"),
            "market_cap_usd": attrs.get("market_cap_usd"),
            "reserve_in_usd": attrs.get("reserve_in_usd"),
            "volume_usd_h24": (attrs.get("volume_usd") or {}).get("h24"),
            "pool_created_at": attrs.get("pool_created_at"),
        })
    return pools


def get_new_pools(network: str, limit: int = 15) -> list[dict]:
    """
    network is a GeckoTerminal network slug from
    config.GECKOTERMINAL_NETWORKS (e.g. 'eth', not 'ethereum').
    Newest pools first — the primary "new coin" discovery feed.
    """
    url = f"{GECKOTERMINAL_BASE}/networks/{network}/new_pools"
    resp = requests.get(url, params={"page": 1}, timeout=REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    return _extract_pools(resp.json())[:limit]


def get_trending_pools(network: str, limit: int = 15) -> list[dict]:
    """
    Trending-by-activity pools — catches obscure tokens that are
    picking up real volume even if they weren't created recently.
    """
    url = f"{GECKOTERMINAL_BASE}/networks/{network}/trending_pools"
    resp = requests.get(url, params={"page": 1}, timeout=REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    return _extract_pools(resp.json())[:limit]
