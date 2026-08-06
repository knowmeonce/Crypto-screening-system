"""
Historical snapshots, persisted as JSON files committed straight into
the repo — the free substitute for a time-series database. Each
scheduled run appends one snapshot per tracked coin; growth-rate and
acceleration reads (holder growth, bucket momentum trend, the DCA
growth-trajectory gate) all read back through this module.

One file per coin (data/history/{token_key}.json, a list of daily
snapshots) rather than one giant file — keeps daily commits small and
each coin's history independently diffable.
"""

import json
import os
from datetime import datetime, timezone

from config import HISTORY_DIR


def token_key(chain: str, token_address: str) -> str:
    return f"{chain}_{token_address.lower()}"


def _history_path(key: str) -> str:
    return os.path.join(HISTORY_DIR, f"{key}.json")


def load_history(key: str) -> list[dict]:
    path = _history_path(key)
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        return json.load(f)


def append_snapshot(key: str, snapshot: dict, max_days: int = 90) -> None:
    """
    Appends today's snapshot, replacing any existing entry for today
    (so a re-run on the same day doesn't duplicate). Trims to
    max_days so history files don't grow unbounded — 90 days is far
    more than any trend/acceleration read here needs.
    """
    os.makedirs(HISTORY_DIR, exist_ok=True)
    entries = load_history(key)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    snapshot = {**snapshot, "date": today}
    entries = [e for e in entries if e.get("date") != today]
    entries.append(snapshot)
    entries = entries[-max_days:]

    with open(_history_path(key), "w") as f:
        json.dump(entries, f, indent=2, default=str)


def value_n_days_ago(entries: list[dict], field: str, days_ago: int):
    """
    Walks back from the most recent snapshot by index, not by
    calendar arithmetic — a missed run just means "N snapshots ago"
    shifts by however many runs were actually missed, which is the
    correct behavior for a daily-cadence, sometimes-skipped job.
    """
    if len(entries) <= days_ago:
        return None
    return entries[-(days_ago + 1)].get(field)


def trend(entries: list[dict], field: str, days_ago: int = 7) -> dict:
    """
    Simple percent-change trend for `field` over the last `days_ago`
    snapshots. Returns insufficient_history=True rather than guessing
    when there isn't enough history yet — same fail-safe pattern as
    the rest of this codebase.
    """
    if not entries:
        return {"now": None, "then": None, "pct_change": None, "insufficient_history": True}

    now = entries[-1].get(field)
    then = value_n_days_ago(entries, field, days_ago)

    if now is None or then is None or then == 0:
        return {"now": now, "then": then, "pct_change": None, "insufficient_history": True}

    pct_change = round(((now - then) / then) * 100, 2)
    return {"now": now, "then": then, "pct_change": pct_change, "insufficient_history": False}


def acceleration(entries: list[dict], field: str, window_days: int = 7) -> dict:
    """
    Second-derivative read: compares the most recent window's percent
    change against the window before it, to say whether growth is
    speeding up, flat, or slowing down — not just "is it growing."
    Needs at least 2*window_days of history; returns
    insufficient_history=True below that rather than a false read.
    """
    if len(entries) < 2 * window_days + 1:
        return {"direction": None, "recent_pct_change": None, "prior_pct_change": None, "insufficient_history": True}

    recent_now = entries[-1].get(field)
    recent_then = entries[-(window_days + 1)].get(field)
    prior_then = entries[-(2 * window_days + 1)].get(field)

    if None in (recent_now, recent_then, prior_then) or recent_then == 0 or prior_then == 0:
        return {"direction": None, "recent_pct_change": None, "prior_pct_change": None, "insufficient_history": True}

    recent_pct = ((recent_now - recent_then) / recent_then) * 100
    prior_pct = ((recent_then - prior_then) / prior_then) * 100

    if recent_pct > prior_pct + 1:
        direction = "accelerating"
    elif recent_pct < prior_pct - 1:
        direction = "decelerating"
    else:
        direction = "flat"

    return {
        "direction": direction,
        "recent_pct_change": round(recent_pct, 2),
        "prior_pct_change": round(prior_pct, 2),
        "insufficient_history": False,
    }
