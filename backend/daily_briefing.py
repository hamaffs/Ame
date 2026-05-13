"""
Amé Daily Briefing — first-interaction-of-the-day personal briefing.

Runs ONCE per day, only if it's morning (5am–noon) and the briefing for
today hasn't already been delivered:
1. Weather (free wttr.in API)
2. What you were working on yesterday (from task memory)
3. News about your interests (from news_watcher logic)

Delivers as a single spoken summary on first interaction.
"""

from __future__ import annotations
import json
import os
import threading
import time
from datetime import datetime


_has_run = False
_BRIEFING_STAMP = os.path.join(os.path.expanduser("~"), ".ame", "last_briefing.json")


def _already_briefed_today() -> bool:
    if not os.path.exists(_BRIEFING_STAMP):
        return False
    try:
        with open(_BRIEFING_STAMP, "r", encoding="utf-8") as f:
            data = json.load(f)
        last = data.get("date")
        return last == datetime.now().date().isoformat()
    except Exception:
        return False


def _mark_briefed_today() -> None:
    os.makedirs(os.path.dirname(_BRIEFING_STAMP), exist_ok=True)
    try:
        with open(_BRIEFING_STAMP, "w", encoding="utf-8") as f:
            json.dump({"date": datetime.now().date().isoformat()}, f)
    except Exception:
        pass


def start_daily_briefing(live_session) -> None:
    """Launch the daily briefing in a background thread."""
    global _has_run
    if _has_run:
        return
    hour = datetime.now().hour
    if hour < 5 or hour >= 12:
        print(f"[DailyBriefing] Skipped — not morning (hour={hour})")
        return
    if _already_briefed_today():
        print("[DailyBriefing] Skipped — already delivered today")
        return
    _has_run = True
    t = threading.Thread(target=_run, args=(live_session,), daemon=True, name="DailyBriefing")
    t.start()
    print("[DailyBriefing] Scheduled (15s delay)")


def _run(live_session) -> None:
    """Main worker — assembles the briefing."""
    time.sleep(15)
    parts: list[str] = []

    weather = _get_weather()
    if weather:
        parts.append(weather)

    tasks = _get_yesterday_tasks()
    if tasks:
        parts.append(f"Yesterday you were working on: {tasks}")

    if not parts:
        return

    summary = " ".join(parts)
    if live_session and hasattr(live_session, "speak_proactive"):
        try:
            ctx = "Daily morning briefing assembled from weather + last-session tasks."
            live_session.speak_proactive(summary, ctx)
            _mark_briefed_today()
        except Exception as e:
            print(f"[DailyBriefing] speak_proactive failed: {e}")


def _get_weather() -> str | None:
    """Get weather from wttr.in (free, no API key needed)."""
    try:
        import httpx
    except Exception:
        return None
    location = ""
    try:
        from backend.memory import identity as _id_layer
        data = _id_layer.load_identity()
        id_data = data.get("identity", {}) or {}
        for key in ("location", "city", "country"):
            val = id_data.get(key)
            if isinstance(val, dict):
                val = val.get("value", "")
            if val:
                location = str(val)
                break
    except Exception:
        pass
    try:
        url = f"https://wttr.in/{location}?format=3" if location else "https://wttr.in/?format=3"
        resp = httpx.get(url, timeout=6)
        if resp.status_code == 200 and resp.text.strip():
            return resp.text.strip()
    except Exception as e:
        print(f"[DailyBriefing] weather fetch failed: {e}")
    return None


def _summarize_nightly(report: dict | None) -> str | None:
    """Turn a nightly report into one short natural-language line."""
    if not report:
        return None
    bits: list[str] = []
    status = report.get("status") or {}
    crypto_mode = status.get("memory_crypto")
    if crypto_mode and crypto_mode not in ("dpapi", "passphrase"):
        bits.append(f"memory encryption not active ({crypto_mode})")
    if not bits:
        return None
    return "Heads up: " + "; ".join(bits) + "."


def _get_yesterday_tasks() -> str | None:
    """Get what the user was working on from task memory."""
    try:
        from backend.memory.identity import get_active_tasks
        tasks = get_active_tasks()
    except Exception:
        return None
    if not tasks:
        return None
    return tasks[0][:100]
