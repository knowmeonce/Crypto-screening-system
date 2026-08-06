"""
DexScreener connector.

Covers: liquidity pool depth, number of active pairs, volume —
free, no API key required at all.
"""

import requests
from config import DEXSCREENER_BASE, REQUEST_TIMEOUT_SECONDS


def get_pairs_for_token(token_address: str) -> list[dict]:
    """
    Returns every known trading pair for a token contract address,
    across all chains DexScreener indexes.
    """
    url = f"{DEXSCREENER_BASE}/tokens/{token_address}"
    resp = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    data = resp.json()
    return data.get("pairs") or []


def summarize_liquidity(pairs: list[dict]) -> dict:
    """
    Reduces the raw pair list to what the scoring engine needs:
    total liquidity in USD across all pools, and how many distinct
    pools exist (a single-pool token is fragile to one large sell).
    """
    if not pairs:
        return {"total_liquidity_usd": 0.0, "pair_count": 0, "top_pair_dex": None}

    total_liquidity = sum(p.get("liquidity", {}).get("usd", 0) or 0 for p in pairs)
    top_pair = max(pairs, key=lambda p: p.get("liquidity", {}).get("usd", 0) or 0)

    return {
        "total_liquidity_usd": round(total_liquidity, 2),
        "pair_count": len(pairs),
        "top_pair_dex": top_pair.get("dexId"),
        "top_pair_volume_24h_usd": top_pair.get("volume", {}).get("h24"),
    }
