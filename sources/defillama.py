"""
DeFiLlama connector.

Covers: Total Value Locked (TVL) for protocols — free, no API key.
Used mainly for the alt-coin fundamentals score (real usage signal)
and for System 2's survivability gate.
"""

import requests
from config import DEFILLAMA_BASE, REQUEST_TIMEOUT_SECONDS


def get_protocol_tvl_history(protocol_slug: str) -> dict:
    """
    protocol_slug is DeFiLlama's own identifier for the protocol
    (e.g. 'aave', not the token ticker) — look it up via
    GET /protocols if unsure, not guessed from the ticker.
    """
    url = f"{DEFILLAMA_BASE}/protocol/{protocol_slug}"
    resp = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    return resp.json()


def get_tvl_trend(protocol_slug: str, days: int = 7) -> dict:
    """
    Reduces full TVL history to a short trend read: current TVL vs
    TVL N days ago, and the resulting percentage change — the input
    the growth-trajectory gate actually needs, not the full history.
    """
    data = get_protocol_tvl_history(protocol_slug)
    tvl_series = data.get("tvl", [])
    if len(tvl_series) < days + 1:
        return {"tvl_now": None, "tvl_pct_change": None, "insufficient_history": True}

    tvl_now = tvl_series[-1].get("totalLiquidityUSD")
    tvl_then = tvl_series[-(days + 1)].get("totalLiquidityUSD")

    if not tvl_then:
        return {"tvl_now": tvl_now, "tvl_pct_change": None, "insufficient_history": True}

    pct_change = round(((tvl_now - tvl_then) / tvl_then) * 100, 2)
    return {"tvl_now": tvl_now, "tvl_pct_change": pct_change, "insufficient_history": False}


def list_all_protocols() -> list[dict]:
    """Full protocol list — used to resolve a token to its DeFiLlama slug."""
    url = f"{DEFILLAMA_BASE}/protocols"
    resp = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    return resp.json()
