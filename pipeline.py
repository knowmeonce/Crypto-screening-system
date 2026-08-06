"""
Pipeline orchestrator.

Phase 1 deliverable: given a token, pull raw data from every source
and return one consolidated record. This does NOT score or filter
anything yet — that's phases 2/3. Phase 1's job is only: get clean,
labeled data in one place, with missing data clearly marked as
missing rather than silently defaulted.
"""

from sources import coingecko, dexscreener, defillama, goplus, blockscout


def collect_token_data(
    coingecko_id: str,
    token_address: str,
    chain: str,
    defillama_slug: str | None = None,
) -> dict:
    """
    coingecko_id: e.g. 'bitcoin' (CoinGecko's own id, not the ticker)
    token_address: the on-chain contract address
    chain: key matching config.BLOCKSCOUT_CHAINS / GOPLUS_CHAIN_IDS
    defillama_slug: optional — only relevant for tokens with a
        DeFiLlama-tracked protocol (mostly alts, not memes)

    Every source call is wrapped so one failing source doesn't take
    down the whole record — failures are recorded per-source, not
    swallowed silently, so the scoring engine (and the commentary
    text later) can see exactly what data was and wasn't available.
    """
    record = {
        "coingecko_id": coingecko_id,
        "token_address": token_address,
        "chain": chain,
        "errors": {},
    }

    # --- Market data, supply, FDV, category tags ---
    try:
        market = coingecko.get_coin_market_data(coingecko_id)
        record["market"] = market
        record["fdv_to_mcap_ratio"] = coingecko.get_fdv_to_mcap_ratio(market)
    except Exception as e:
        record["market"] = None
        record["fdv_to_mcap_ratio"] = None
        record["errors"]["coingecko"] = str(e)

    # --- Liquidity ---
    lp_addresses = set()
    try:
        pairs = dexscreener.get_pairs_for_token(token_address)
        record["liquidity"] = dexscreener.summarize_liquidity(pairs)
        lp_addresses = {p.get("pairAddress") for p in pairs if p.get("pairAddress")}
    except Exception as e:
        record["liquidity"] = None
        record["errors"]["dexscreener"] = str(e)

    # --- Contract safety / hard filters ---
    try:
        security = goplus.check_contract_security(chain, token_address)
        record["security"] = security
        record["hard_filter_result"] = goplus.evaluate_hard_filters(security)
    except Exception as e:
        record["security"] = None
        record["hard_filter_result"] = {"passed": False, "failures": [f"security check unavailable: {e}"]}
        record["errors"]["goplus"] = str(e)

    # --- Holder concentration ---
    # total_supply is sourced from Blockscout itself, not from the
    # CoinGecko market record above — it must be in the same raw,
    # undivided units as Blockscout's holder `value` field, which a
    # decimal-adjusted figure like circulating_supply is not. See
    # blockscout.get_token_supply_raw()'s docstring.
    try:
        holders = blockscout.get_top_holders(chain, token_address)
        total_supply = blockscout.get_token_supply_raw(chain, token_address)
        record["concentration"] = blockscout.compute_concentration(holders, total_supply, lp_addresses)
    except Exception as e:
        record["concentration"] = None
        record["errors"]["blockscout"] = str(e)

    # --- TVL (alts only, where applicable) ---
    if defillama_slug:
        try:
            record["tvl_trend"] = defillama.get_tvl_trend(defillama_slug)
        except Exception as e:
            record["tvl_trend"] = None
            record["errors"]["defillama"] = str(e)
    else:
        record["tvl_trend"] = None

    return record


if __name__ == "__main__":
    # Manual smoke-test entry point. Won't reach the live internet from
    # this sandbox — run this from wherever the pipeline is actually
    # deployed to confirm real connectivity.
    import json
    result = collect_token_data(
        coingecko_id="ethereum",
        token_address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        chain="ethereum",
        defillama_slug=None,
    )
    print(json.dumps(result, indent=2, default=str))
