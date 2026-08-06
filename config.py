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
    "min_lp_locked_pct": 50.0,       # of the LP token supply, when require_lp_lock is True
    "require_contract_renounced": True,
    "reject_if_honeypot": True,
}

REQUEST_TIMEOUT_SECONDS = 10

# --- Phase 2+: discovery, scoring, narrative buckets ---

GECKOTERMINAL_BASE = "https://api.geckoterminal.com/api/v2"

# GeckoTerminal's own network slugs — NOT the same strings as
# BLOCKSCOUT_CHAINS/GOPLUS_CHAIN_IDS keys (e.g. Ethereum is "eth" here,
# not "ethereum"). This maps GeckoTerminal's slug back to our internal
# chain key so a discovered pool can be handed straight to the
# goplus/blockscout connectors.
GECKOTERMINAL_NETWORKS = {
    "eth": "ethereum",
    "base": "base",
    "arbitrum": "arbitrum",
    "polygon_pos": "polygon",
    "bsc": "bsc",
}

# How many new-pool and trending-pool candidates to pull per network,
# per daily run. Kept small — free-tier rate limits, and every
# candidate costs one call to each of 5 sources.
DISCOVERY_POOLS_PER_NETWORK = 15

# Minimum liquidity for a discovered pool to even be worth scoring —
# below this, a token is almost certainly unscreenable (can't get a
# meaningful concentration/safety read) rather than just "risky."
DISCOVERY_MIN_LIQUIDITY_USD = 2000

# Keyword -> narrative bucket mapping, checked against CoinGecko's
# `categories` list (case-insensitive substring match). First bucket
# whose keywords match wins. A coin matching none of these is
# "uncategorized" — a real bucket in its own right, not an error, and
# the input to the bucket-approval flow (Phase 4).
NARRATIVE_BUCKETS = {
    "AI x DePIN": ["artificial intelligence", "ai agent", "depin", "ai (ai)", "big data"],
    "stablecoin rails": ["stablecoin", "payment", "rwa stablecoin"],
    "RWA tokenization": ["real world assets", "rwa", "tokenized"],
    "modular blockchain infra": ["modular blockchain", "layer 2", "layer 1", "rollup", "scaling"],
    "restaking": ["restaking", "liquid staking", "eigenlayer"],
    "prediction markets": ["prediction market"],
    "pure meme/attention": ["meme", "memes"],
    "legacy/established": ["smart contract platform", "exchange-based tokens", "gmci"],
}
# Buckets scored as memes under the meme-coin rubric rather than the
# alt-coin rubric, regardless of what else they're tagged with.
MEME_BUCKETS = {"pure meme/attention"}

# Alt-coin rubric weights (must sum to 100). Applied only after hard
# filters pass. See scoring/rubrics.py for what each component reads.
ALT_RUBRIC_WEIGHTS = {
    "protocol_activity": 20,   # TVL trend direction/magnitude
    "dev_activity": 15,        # commits/PRs/contributors, last 4 weeks
    "tokenomics": 25,          # FDV/mcap ratio — how much dilution is still coming
    "distribution_health": 25, # holder concentration
    "liquidity_safety": 15,    # liquidity depth + pool count
}

# Meme-coin rubric weights (must sum to 100). Deliberately excludes
# any utility/revenue/TVL component — meme coins structurally have
# none, and scoring them on it fails every meme coin by design.
MEME_RUBRIC_WEIGHTS = {
    "distribution_health": 35,  # holder concentration
    "holder_growth_rate": 25,   # accelerating vs flat vs decelerating
    "liquidity_depth_safety": 25,  # liquidity depth + pool count
    "lp_lock_status": 15,       # from GoPlus lp_holder_count/lp_total_supply
}

# Narrative tailwind is additive on top of the 0-100 rubric score, and
# capped so it can act only as a tie-breaker — never enough to rescue
# a coin that failed hard filters (filtered out before scoring even
# runs) or that scored weakly on fundamentals.
NARRATIVE_TAILWIND_MAX_POINTS = 10

# System 2 (DCA shortlist) additional gates, applied after the normal
# rubric score. Survivability (hard filters + a minimum base score) is
# the floor; growth trajectory is the actual bar.
DCA_MIN_BASE_SCORE = 55
DCA_MIN_HISTORY_DAYS = 3  # can't judge a trend without at least this many daily snapshots

GLOSSARY = {
    "distribution health": "How spread out a coin is among different wallets. If a few wallets own most of it, any one of them can crash the price by selling. Healthy means many holders, no single whale in control.",
    "concentration": "The opposite way of saying the same thing — high concentration means few people own most of it (bad), low concentration means it's spread out (good).",
    "lp lock": "The liquidity pool is the \"swap machine\" that lets people trade the coin. LP lock means whoever set it up promised, unbreakably in code, not to walk off with the funds inside. No lock means they could drain it and disappear.",
    "mint function / renounced": "Mint is the ability to create more coins out of thin air. If the developer still holds that power, they can flood the market and tank the price whenever they want. Renounced means they gave up that power permanently in code, not just as a promise.",
    "honeypot": "You can buy the coin but the code won't let you sell it. Looks tradeable, isn't. Immediate disqualifier.",
    "circulating vs total/max supply": "Circulating is what's actually trading right now. Max supply is the total that will ever exist. A big gap means a lot more coins are coming later, which usually pushes price down.",
    "fdv (fully diluted valuation)": "What the coin would be worth if every coin that will ever exist were already out at today's price. Comparing FDV to the current market cap shows how much dilution is still coming.",
    "dilution": "Like adding water to juice — more coins entering circulation without more demand means each coin is worth a smaller slice of the pie.",
    "on-chain activity": "Real usage counted directly on the blockchain — the difference between \"everyone's talking about it\" and \"people are actually using it.\"",
    "tvl (total value locked)": "How much money people have actually deposited or staked into a project. High TVL means real trust, not just trading.",
    "nvt ratio": "Crypto's version of a stock's P/E ratio — compares total value to actual transaction activity. High NVT can mean price is ahead of real usage; low NVT can mean usage is catching up to price.",
    "narrative/sector cycle": "Crypto trends move in waves. Being early in a wave about to get attention is very different from buying after everyone already piled in.",
    "second derivative / acceleration": "Not just \"is it growing\" but \"is the rate of growth speeding up or slowing down.\"",
    "narrative bucket": "The theme a coin belongs to, grouping coins by what story is driving interest rather than just chain or category.",
    "bucket momentum": "How fast money is flowing into a theme, measured against the wider market's growth over the same period, not just raw price movement.",
    "narrative tailwind": "A bonus added to a coin's score for being in a hot, not-yet-priced-in bucket — a tie-breaker on top of the core score, never a substitute for it.",
}

DATA_DIR = "data"
HISTORY_DIR = f"{DATA_DIR}/history"
WATCHLIST_PATH = f"{DATA_DIR}/watchlist.json"
LATEST_PATH = f"{DATA_DIR}/latest.json"
BUCKET_PROPOSALS_PATH = f"{DATA_DIR}/bucket_proposals.json"
