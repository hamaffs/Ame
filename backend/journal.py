"""Journal — natural-language reflection over the tool-invocation audit log.

Reads `audit.iter_records()` for a given window and shapes a short, warm
summary Amé can read back when the user asks things like "what did you do
yesterday?" or "what have we been up to this week?".

This is *reflective*, not diagnostic. It groups actions, counts bursts,
names a few standouts — it doesn't dump a log. Refusals and confirmation
denials are surfaced briefly because they're part of the story.
"""

from __future__ import annotations
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Iterable

from backend import audit


def _window_iso(hours_back: int) -> str:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    return cutoff.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _bucket(records: Iterable[dict]) -> dict:
    tools: Counter[str] = Counter()
    outcomes: Counter[str] = Counter()
    refusals: list[str] = []
    for rec in records:
        tools[rec.get("tool", "?")] += 1
        outcomes[rec.get("outcome", "ok")] += 1
        if rec.get("outcome") in {"refused", "denied", "blocked"}:
            tip = rec.get("tool", "?")
            if tip not in refusals:
                refusals.append(tip)
    return {"tools": tools, "outcomes": outcomes, "refusals": refusals}


def summarize(hours_back: int = 24) -> str:
    """Return a one-paragraph reflection over the past `hours_back` hours."""
    since = _window_iso(hours_back)
    try:
        records = list(audit.iter_records(since_iso=since))
    except Exception:
        return "I couldn't read my own logs just now."
    if not records:
        return "Quiet stretch — nothing logged in that window."

    b = _bucket(records)
    total = sum(b["tools"].values())
    top = ", ".join(f"{name} ({n})" for name, n in b["tools"].most_common(3))
    parts = [f"{total} actions in the last {hours_back}h — mostly {top}."]
    refused_count = b["outcomes"].get("refused", 0) + b["outcomes"].get("blocked", 0)
    if refused_count:
        parts.append(f"{refused_count} request{'s' if refused_count != 1 else ''} I held back on ({', '.join(b['refusals'][:3])}).")
    return " ".join(parts)
