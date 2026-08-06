"""
System 2 (DCA shortlist) eligibility gate.

Survivability — hard filters passing, plus a minimum base rubric
score — is the FLOOR, not the bar: a coin that merely "hasn't
collapsed" does not qualify. The actual bar is an observed upward
trend in holder growth and/or volume/TVL, read from the token's own
daily history (see history.py) — never approximated from a single
day's snapshot, since a single snapshot cannot show a trend at all.
"""

from config import DCA_MIN_BASE_SCORE, DCA_MIN_HISTORY_DAYS
import history


def evaluate_dca_eligibility(final_score: float, hard_filters_passed: bool, history_entries: list[dict]) -> dict:
    reasons_failed: list[str] = []

    if not hard_filters_passed:
        reasons_failed.append("failed a hard filter")

    if final_score < DCA_MIN_BASE_SCORE:
        reasons_failed.append(f"score {final_score:.1f} below the {DCA_MIN_BASE_SCORE} survivability floor")

    if len(history_entries) < DCA_MIN_HISTORY_DAYS:
        reasons_failed.append(f"only {len(history_entries)} day(s) of history — need {DCA_MIN_HISTORY_DAYS}+ to read a trend")
        return {
            "eligible": False,
            "reasons_failed": reasons_failed,
            "growth_trajectory": None,
        }

    holder_trend = history.trend(history_entries, "holder_count", days_ago=min(7, len(history_entries) - 1))
    volume_trend = history.trend(history_entries, "volume_usd_h24", days_ago=min(7, len(history_entries) - 1))
    tvl_trend = history.trend(history_entries, "tvl_usd", days_ago=min(7, len(history_entries) - 1))

    growth_signals = []
    if not holder_trend["insufficient_history"] and holder_trend["pct_change"] is not None:
        growth_signals.append(("holder count", holder_trend["pct_change"]))
    if not volume_trend["insufficient_history"] and volume_trend["pct_change"] is not None:
        growth_signals.append(("volume", volume_trend["pct_change"]))
    if not tvl_trend["insufficient_history"] and tvl_trend["pct_change"] is not None:
        growth_signals.append(("TVL", tvl_trend["pct_change"]))

    has_upward_trend = any(pct > 0 for _, pct in growth_signals)

    if not growth_signals:
        reasons_failed.append("no holder/volume/TVL trend data available yet")
    elif not has_upward_trend:
        summary = ", ".join(f"{name} {pct:+.1f}%" for name, pct in growth_signals)
        reasons_failed.append(f"no upward trend in holders, volume, or TVL ({summary})")

    growth_trajectory = {
        "holder_trend_pct": holder_trend["pct_change"],
        "volume_trend_pct": volume_trend["pct_change"],
        "tvl_trend_pct": tvl_trend["pct_change"],
        "has_upward_trend": has_upward_trend,
    }

    return {
        "eligible": len(reasons_failed) == 0,
        "reasons_failed": reasons_failed,
        "growth_trajectory": growth_trajectory,
    }
