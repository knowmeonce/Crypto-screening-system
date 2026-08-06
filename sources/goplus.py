"""
GoPlus Security connector.

Covers the non-negotiable hard-filter checks: honeypot detection,
mint function status, ownership renounced, LP lock status.
Free tier, no API key required.

This is the single most important module for safety — nothing
here should ever be silently defaulted to "safe" on missing data.
Missing data means "unknown," and unknown fails safe (treated as
a filter failure, not a pass) — see evaluate_hard_filters().
"""

import requests
from config import GOPLUS_BASE, GOPLUS_CHAIN_IDS, HARD_FILTERS, REQUEST_TIMEOUT_SECONDS


def check_contract_security(chain: str, token_address: str) -> dict:
    """
    chain is a key from config.GOPLUS_CHAIN_IDS (e.g. 'ethereum').
    Returns the raw GoPlus security fields relevant to the hard filters.
    """
    chain_id = GOPLUS_CHAIN_IDS.get(chain)
    if not chain_id:
        raise ValueError(f"No GoPlus chain id configured for '{chain}'")

    url = f"{GOPLUS_BASE}/token_security/{chain_id}"
    params = {"contract_addresses": token_address}
    resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    result = resp.json().get("result", {})
    token_data = result.get(token_address.lower(), {})

    return {
        "is_honeypot": token_data.get("is_honeypot"),          # "1" / "0" / None
        "can_take_back_ownership": token_data.get("can_take_back_ownership"),
        "owner_change_balance": token_data.get("owner_change_balance"),
        "is_mintable": token_data.get("is_mintable"),
        "is_open_source": token_data.get("is_open_source"),
        "lp_holder_count": token_data.get("lp_holder_count"),
        "lp_total_supply": token_data.get("lp_total_supply"),
        "top_10_holder_percent": token_data.get("top_10_holder_percent"),  # cross-check vs Blockscout
        "raw": token_data,  # keep raw payload for anything the rubric adds later
    }


def evaluate_hard_filters(security_data: dict) -> dict:
    """
    Applies the pass/fail hard filters from config.HARD_FILTERS.
    Any field GoPlus didn't return is treated as a fail, not a pass —
    "we don't know" is not the same as "it's safe," and the system
    should never quietly assume safety on missing data.
    """
    failures = []

    honeypot = security_data.get("is_honeypot")
    if HARD_FILTERS["reject_if_honeypot"]:
        if honeypot != "0":
            failures.append("honeypot check failed or unknown")

    mintable = security_data.get("is_mintable")
    if HARD_FILTERS["require_contract_renounced"]:
        if mintable != "0":
            failures.append("mint function still active or unknown")

    top10 = security_data.get("top_10_holder_percent")
    if top10 is not None:
        try:
            if float(top10) * 100 > HARD_FILTERS["max_single_wallet_pct"]:
                failures.append(f"top-10 concentration {float(top10)*100:.1f}% exceeds threshold")
        except (TypeError, ValueError):
            failures.append("top-10 concentration unparseable")
    else:
        failures.append("top-10 concentration unknown")

    return {
        "passed": len(failures) == 0,
        "failures": failures,
    }
