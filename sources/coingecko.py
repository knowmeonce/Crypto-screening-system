"""
CoinGecko connector.

Covers: price, market cap, circulating/total/max supply, FDV,
and category tags (used for narrative bucket classification).

Free demo tier: no key required for basic access; set
COINGECKO_API_KEY env var if you register for a free demo key
(raises the rate limit ceiling, does not change what's available).
"""

import requests
from config import COINGECKO_BASE, COINGECKO_API_KEY, REQUEST_TIMEOUT_SECONDS


def _headers():
    headers = {"accept": "application/json"}
    if COINGECKO_API_KEY:
        headers["x-cg-demo-api-key"] = COINGECKO_API_KEY
    return headers


def get_coin_market_data(coin_id: str) -> dict:
    """
    Pull core market data for one coin by its CoinGecko id
    (e.g. 'bitcoin', not the ticker 'BTC').

    Returns the fields the scoring engine actually needs:
    price, market cap, FDV, circulating/total/max supply, categories.
    """
    url = f"{COINGECKO_BASE}/coins/{coin_id}"
    params = {
        "localization": "false",
        "tickers": "false",
        "market_data": "true",
        "community_data": "false",
        "developer_data": "true",  # dev commit activity, useful for alt-coin score
        "sparkline": "false",
    }
    resp = requests.get(url, params=params, headers=_headers(), timeout=REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    data = resp.json()

    market_data = data.get("market_data", {})

    return {
        "id": data.get("id"),
        "symbol": data.get("symbol", "").upper(),
        "name": data.get("name"),
        "categories": data.get("categories", []),  # feeds narrative bucket tagging
        "price_usd": market_data.get("current_price", {}).get("usd"),
        "market_cap_usd": market_data.get("market_cap", {}).get("usd"),
        "fully_diluted_valuation_usd": market_data.get("fully_diluted_valuation", {}).get("usd"),
        "circulating_supply": market_data.get("circulating_supply"),
        "total_supply": market_data.get("total_supply"),
        "max_supply": market_data.get("max_supply"),
        "dev_activity": data.get("developer_data", {}),
    }


def get_fdv_to_mcap_ratio(coin_data: dict) -> float | None:
    """
    Compute FDV/mcap from a get_coin_market_data() result.
    Returns None if either figure is missing (common for very new coins
    with no FDV yet reported) rather than guessing.
    """
    mcap = coin_data.get("market_cap_usd")
    fdv = coin_data.get("fully_diluted_valuation_usd")
    if not mcap or not fdv:
        return None
    return round(fdv / mcap, 2)


def list_coins_by_category(category_id: str, per_page: int = 100) -> list[dict]:
    """
    Pull all coins tagged under a CoinGecko category id — the raw input
    for computing narrative bucket momentum (aggregate market cap of a
    bucket, tracked over time).
    """
    url = f"{COINGECKO_BASE}/coins/markets"
    params = {
        "vs_currency": "usd",
        "category": category_id,
        "order": "market_cap_desc",
        "per_page": per_page,
        "page": 1,
    }
    resp = requests.get(url, params=params, headers=_headers(), timeout=REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    return resp.json()
