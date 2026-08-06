"""
Alt-coin and meme-coin scoring rubrics.

Two separate rubrics, not one shared one: meme coins are deliberately
never scored on utility/revenue/TVL (they structurally have none —
scoring them on it just fails every meme coin by design), and alt
coins are never scored on holder-growth-rate acceleration the way
memes are (an alt coin's TVL/protocol activity is the more meaningful
usage signal).

Every score function returns both a 0-100 number AND the plain-English
justification lines behind it — the dashboard's per-coin commentary
paragraph is built directly from these, not written separately, so the
prose can never drift from the numbers it's describing.

Hard filters run before any of this (see goplus.evaluate_hard_filters)
and are pass/fail, never part of the weighted score. Narrative
tailwind is applied additively afterward, in apply_narrative_tailwind
— never folded into the base weights, so it can never compensate for
a weak fundamentals score, only break a tie on top of one.
"""

from config import ALT_RUBRIC_WEIGHTS, MEME_RUBRIC_WEIGHTS, NARRATIVE_TAILWIND_MAX_POINTS
from scoring.narrative import classify_bucket, is_meme_bucket
from sources.goplus import summarize_lp_lock


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def classify_coin_type(record: dict) -> str:
    """
    "meme" or "alt". Driven by narrative bucket (pure meme/attention
    -> meme, everything else -> alt) rather than a separate
    classifier, so a coin's rubric and its displayed bucket can never
    disagree with each other.
    """
    categories = (record.get("market") or {}).get("categories") or []
    bucket = classify_bucket(categories)
    return "meme" if is_meme_bucket(bucket) else "alt"


def _score_liquidity(liquidity: dict | None) -> tuple[float | None, str]:
    if not liquidity:
        return None, "liquidity data unavailable"

    usd = liquidity.get("total_liquidity_usd") or 0
    pairs = liquidity.get("pair_count") or 0

    if usd < 2000:
        base = 0
    elif usd < 25000:
        base = 30
    elif usd < 100000:
        base = 55
    elif usd < 500000:
        base = 75
    elif usd < 2000000:
        base = 90
    else:
        base = 100

    # A single pool is fragile to one large sell regardless of depth —
    # cap the score rather than let deep-but-single-pool liquidity
    # read as fully safe.
    if pairs <= 1:
        base = min(base, 60)

    note = f"${usd:,.0f} in liquidity across {pairs} pool(s)"
    return base, note


def _score_distribution(concentration: dict | None) -> tuple[float | None, str]:
    if not concentration or concentration.get("top_10_pct") is None:
        return None, "holder concentration unavailable"

    top10 = concentration["top_10_pct"]
    score = _clamp(100 - top10)
    note = f"top 10 non-LP holders control {top10:.1f}% of supply"
    return score, note


def score_alt_coin(record: dict) -> dict:
    """
    Weighted 0-100 alt-coin score from config.ALT_RUBRIC_WEIGHTS:
    protocol activity (TVL trend), dev activity, tokenomics
    (FDV/mcap), distribution health, liquidity safety. A component
    with unavailable data scores neutral (50) and is called out by
    name in the justification, rather than silently dragging the
    total down or being skipped (skipping would let missing data
    inflate the average of what's left).
    """
    weights = ALT_RUBRIC_WEIGHTS
    components: dict[str, float] = {}
    notes: list[str] = []

    tvl = record.get("tvl_trend")
    if tvl and not tvl.get("insufficient_history") and tvl.get("tvl_pct_change") is not None:
        pct = tvl["tvl_pct_change"]
        components["protocol_activity"] = _clamp(50 + pct)
        notes.append(f"TVL {'up' if pct >= 0 else 'down'} {abs(pct):.1f}% over the trailing week")
    else:
        components["protocol_activity"] = 50
        notes.append("no TVL history available yet to read a protocol-activity trend")

    dev = (record.get("market") or {}).get("dev_activity") or {}
    commits = dev.get("commit_count_4_weeks")
    if commits is not None:
        components["dev_activity"] = _clamp(commits * 2)
        notes.append(f"{commits} commits in the last 4 weeks ({dev.get('pull_request_contributors', 0)} contributors)")
    else:
        components["dev_activity"] = 50
        notes.append("no developer activity data available")

    fdv_ratio = record.get("fdv_to_mcap_ratio")
    if fdv_ratio is not None:
        components["tokenomics"] = _clamp(100 - (fdv_ratio - 1) * 20)
        notes.append(f"FDV is {fdv_ratio:.2f}x current market cap — {'no further dilution priced in' if fdv_ratio <= 1.05 else 'more supply still to unlock'}")
    else:
        components["tokenomics"] = 50
        notes.append("FDV/market-cap ratio unavailable (no FDV reported yet)")

    dist_score, dist_note = _score_distribution(record.get("concentration"))
    components["distribution_health"] = dist_score if dist_score is not None else 50
    notes.append(dist_note)

    liq_score, liq_note = _score_liquidity(record.get("liquidity"))
    components["liquidity_safety"] = liq_score if liq_score is not None else 50
    notes.append(liq_note)

    total = sum(components[k] * weights[k] / 100 for k in weights)
    return {"total": round(total, 1), "components": components, "notes": notes}


def score_meme_coin(record: dict, holder_growth: dict | None = None) -> dict:
    """
    Weighted 0-100 meme-coin score from config.MEME_RUBRIC_WEIGHTS:
    distribution health, holder growth rate (accelerating vs flat vs
    decelerating — pass the result of history.acceleration() on
    holder_count via the `holder_growth` argument, since that needs
    multi-day history the pipeline record alone doesn't carry),
    liquidity depth/safety, LP lock status. Deliberately excludes any
    utility/revenue/TVL component.
    """
    weights = MEME_RUBRIC_WEIGHTS
    components: dict[str, float] = {}
    notes: list[str] = []

    dist_score, dist_note = _score_distribution(record.get("concentration"))
    components["distribution_health"] = dist_score if dist_score is not None else 50
    notes.append(dist_note)

    if holder_growth and not holder_growth.get("insufficient_history"):
        direction = holder_growth["direction"]
        score_by_direction = {"accelerating": 100, "flat": 55, "decelerating": 15}
        components["holder_growth_rate"] = score_by_direction.get(direction, 50)
        notes.append(f"holder growth is {direction} ({holder_growth.get('recent_pct_change', 0):.1f}% vs {holder_growth.get('prior_pct_change', 0):.1f}% the prior week)")
    else:
        components["holder_growth_rate"] = 50
        notes.append("not enough holder-count history yet to read a growth trend")

    liq_score, liq_note = _score_liquidity(record.get("liquidity"))
    components["liquidity_depth_safety"] = liq_score if liq_score is not None else 50
    notes.append(liq_note)

    security = record.get("security") or {}
    lp_lock = summarize_lp_lock(security)
    if not lp_lock["insufficient_data"]:
        components["lp_lock_status"] = _clamp(lp_lock["lp_locked_pct"])
        notes.append(f"{lp_lock['lp_locked_pct']:.1f}% of LP supply is locked")
    else:
        components["lp_lock_status"] = 0
        notes.append("LP lock status unknown — scored as unlocked until proven otherwise")

    total = sum(components[k] * weights[k] / 100 for k in weights)
    return {"total": round(total, 1), "components": components, "notes": notes}


def apply_narrative_tailwind(base_score: float, bucket_momentum: dict | None) -> dict:
    """
    Adds up to config.NARRATIVE_TAILWIND_MAX_POINTS on top of the base
    rubric score for being in a bucket that's outgrowing the wider
    market. Purely additive and capped — cannot rescue a coin that
    scored weakly on fundamentals, only break a tie between two coins
    that both already scored well.
    """
    if not bucket_momentum or bucket_momentum.get("insufficient_history") or bucket_momentum.get("momentum") is None:
        return {"final_score": round(base_score, 1), "tailwind_points": 0, "note": "no bucket momentum data yet"}

    momentum = bucket_momentum["momentum"]
    if momentum <= 0:
        points = 0
    else:
        # Linear up to the cap at +50 percentage points of relative
        # outperformance — a deliberately generous ceiling since this
        # is meant to matter, just never dominate.
        points = min(NARRATIVE_TAILWIND_MAX_POINTS, (momentum / 50) * NARRATIVE_TAILWIND_MAX_POINTS)

    accel = bucket_momentum.get("acceleration")
    note = f"bucket outgrowing the market by {momentum:.1f} points over the trailing week"
    if accel:
        note += f", momentum {accel}"

    return {"final_score": round(base_score + points, 1), "tailwind_points": round(points, 1), "note": note}
