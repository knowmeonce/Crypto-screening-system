"""
Central config for API endpoints and settings.
No paid keys required — everything here targets free tiers.
CoinGecko demo key is optional (raises the free rate limit) — set via
env var COINGECKO_API_KEY if you register for one; the pipeline works
without it, just at a lower requests-per-minute ceiling.
"""

import os

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
COINGECKO_API_KEY = os.environ.get("COINGECKO_API_KEY", "")  # optional

DEFILLAMA_BASE = "https://api.llama.fi"

DEXSCREENER_BASE = "https://api.dexscreener.com/latest/dex"

GOPLUS_BASE = "https://api.gopluslabs.io/api/v1"

# Blockscout instances are per-chain — add more as needed.
# Each entry is a free, public Blockscout deployment for that chain.
BLOCKSCOUT_CHAINS = {
    "ethereum": "https://eth.blockscout.com/api/v2",
    "base": "https://base.blockscout.com/api/v2",
    "arbitrum": "https://arbitrum.blockscout.com/api/v2",
    "polygon": "https://polygon.blockscout.com/api/v2",
}

# GoPlus chain IDs (subset — extend as needed)
GOPLUS_CHAIN_IDS = {
    "ethereum": "1",
    "base": "8453",
    "arbitrum": "42161",
    "polygon": "137",
    "bsc": "56",
}

# Hard filter thresholds — pass/fail, not scored.
# These are starting points; tune once real data is flowing.
HARD_FILTERS = {
    "max_single_wallet_pct": 20.0,   # any non-LP wallet holding more than this = fail
    "require_lp_lock": True,
    "require_contract_renounced": True,
    "reject_if_honeypot": True,
}

REQUEST_TIMEOUT_SECONDS = 10
