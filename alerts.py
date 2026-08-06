"""
Day-over-day alert detection (Phase 3). Compares today's scored
record for a coin against yesterday's snapshot and flags the
conditions the spec calls out explicitly: a previously-passing coin
now failing a hard filter, top-10 concentration rising sharply,
liquidity dropping sharply, and — for shortlisted coins — a bucket's
momentum flipping from accelerating to decelerating.

Needs at least two days of history to say anything; a coin's first
day on the watchlist produces no alerts, which is correct (nothing to
compare against yet), not a bug.
"""

CONCENTRATION_SPIKE_PCT_POINTS = 10.0   # top-10 concentration rising by this many percentage points
LIQUIDITY_DROP_PCT = 30.0               # liquidity dropping by this % day-over-day


def detect_coin_alerts(token_label: str, yesterday: dict | None, today: dict,
                        hard_filters_passed_today: bool, hard_filters_passed_yesterday: bool | None) -> list[dict]:
    alerts = []

    if yesterday is None:
        return alerts

    if hard_filters_passed_yesterday and not hard_filters_passed_today:
        alerts.append({
            "type": "hard_filter_newly_failed",
            "token": token_label,
            "message": f"{token_label} previously passed hard filters and now fails.",
        })

    y_conc = yesterday.get("top_10_pct")
    t_conc = today.get("top_10_pct")
    if y_conc is not None and t_conc is not None and (t_conc - y_conc) >= CONCENTRATION_SPIKE_PCT_POINTS:
        alerts.append({
            "type": "concentration_spike",
            "token": token_label,
            "message": f"{token_label} top-10 concentration rose from {y_conc:.1f}% to {t_conc:.1f}% since yesterday.",
        })

    y_liq = yesterday.get("total_liquidity_usd")
    t_liq = today.get("total_liquidity_usd")
    if y_liq and t_liq is not None and y_liq > 0:
        drop_pct = ((y_liq - t_liq) / y_liq) * 100
        if drop_pct >= LIQUIDITY_DROP_PCT:
            alerts.append({
                "type": "liquidity_drop",
                "token": token_label,
                "message": f"{token_label} liquidity dropped {drop_pct:.1f}% since yesterday (${y_liq:,.0f} -> ${t_liq:,.0f}).",
            })

    return alerts


def detect_bucket_momentum_flip(token_label: str, bucket: str, momentum_yesterday: dict | None, momentum_today: dict | None) -> list[dict]:
    """
    Only meaningful for coins on the DCA shortlist — a bucket cooling
    off matters most for money going in on a recurring schedule.
    Call this only for shortlisted coins.
    """
    if not momentum_yesterday or not momentum_today:
        return []
    if momentum_yesterday.get("acceleration") == "accelerating" and momentum_today.get("acceleration") == "decelerating":
        return [{
            "type": "bucket_momentum_flip",
            "token": token_label,
            "message": f"{token_label}'s \"{bucket}\" bucket flipped from accelerating to decelerating momentum.",
        }]
    return []
