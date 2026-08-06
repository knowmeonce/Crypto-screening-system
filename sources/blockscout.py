"""
Blockscout connector.

Covers: token holder list, used to compute distribution/concentration
metrics. Chosen over Etherscan specifically because Etherscan's free
tier has been progressively gating holder-list pagination behind paid
plans — Blockscout's public instances remain fully free per chain.

Caveat carried over from the free-source discussion: coverage depth
varies by chain, especially for very new/obscure tokens on smaller
chains. Treat missing data as missing, not as zero concentration.
"""

import requests
from config import BLOCKSCOUT_CHAINS, REQUEST_TIMEOUT_SECONDS


def get_top_holders(chain: str, token_address: str, limit: int = 50) -> list[dict]:
    """
    chain is a key from config.BLOCKSCOUT_CHAINS (e.g. 'ethereum').
    Returns up to `limit` holders, ranked by balance descending.

    Each holder's `value` field is the RAW on-chain balance (an
    undivided integer string in the token's smallest unit) — it is
    NOT decimal-adjusted. Confirmed against live data: WETH holder
    values come back as 18-decimals-raw integers, not human-readable
    token counts.
    """
    base = BLOCKSCOUT_CHAINS.get(chain)
    if not base:
        raise ValueError(f"No Blockscout instance configured for '{chain}'")

    url = f"{base}/tokens/{token_address}/holders"
    resp = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    items = resp.json().get("items", [])
    return items[:limit]


def get_token_supply_raw(chain: str, token_address: str) -> float | None:
    """
    Total supply straight from Blockscout's own token endpoint, in the
    same RAW (undivided) units as get_top_holders()'s `value` field —
    so the two can be divided directly without needing to know or
    apply the token's decimals.

    Deliberately NOT sourced from CoinGecko's circulating_supply:
    that figure is decimal-adjusted and, for a native-coin/wrapped-token
    pair like ETH/WETH, can even describe a different supply entirely.
    Mixing that human-readable figure with Blockscout's raw holder
    balances was confirmed live to produce nonsense concentration
    percentages (values over 1e17%) — this keeps numerator and
    denominator in the same units, sourced from the same place.
    """
    base = BLOCKSCOUT_CHAINS.get(chain)
    if not base:
        raise ValueError(f"No Blockscout instance configured for '{chain}'")

    url = f"{base}/tokens/{token_address}"
    resp = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    total_supply = resp.json().get("total_supply")
    return float(total_supply) if total_supply is not None else None


def compute_concentration(holders: list[dict], total_supply: float, lp_addresses: set[str] | None = None) -> dict:
    """
    Computes top-10/top-50 concentration, excluding known LP/contract
    addresses so a DEX pool itself doesn't get misread as a "whale."
    lp_addresses should be populated from the DexScreener pair data
    (the pair contract addresses) before calling this.

    total_supply must be in the same RAW units as holders' `value`
    field — use get_token_supply_raw(), not a decimal-adjusted supply
    from another source (see its docstring for why).
    """
    lp_addresses = lp_addresses or set()

    filtered = [
        h for h in holders
        if h.get("address", {}).get("hash", "").lower() not in {a.lower() for a in lp_addresses}
    ]

    def pct_of_top(n):
        top_n = filtered[:n]
        held = sum(float(h.get("value", 0)) for h in top_n)
        return round((held / total_supply) * 100, 2) if total_supply else None

    return {
        "top_10_pct": pct_of_top(10),
        "top_50_pct": pct_of_top(50),
        "largest_single_wallet_pct": pct_of_top(1),
        "holders_sampled": len(filtered),
    }
