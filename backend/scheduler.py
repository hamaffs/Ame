"""
Amé Scheduler — one-shot and recurring task scheduler.

Stores schedules in ~/.ame/schedules.json. A background thread checks
every 30 seconds for tasks that are due. Supports:
  - One-shot: "remind me at 3pm" / "in 20 minutes"
  - Recurring: "every Monday at 9am" / "every day at 6pm"

Each schedule fires a callback (usually LiveSession.speak_proactive)
when triggered.
"""

from __future__ import annotations
import json
import re
import threading
import time as _time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable


SCHEDULES_FILE = Path.home() / ".ame" / "schedules.json"
_lock = threading.Lock()
_schedules: list[dict] = []
_running = False
_thread: threading.Thread | None = None
_fire_callback: Callable[[str], None] | None = None


def _ensure_dir() -> None:
    SCHEDULES_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load() -> list[dict]:
    _ensure_dir()
    if not SCHEDULES_FILE.exists():
        return []
    try:
        with SCHEDULES_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict)]
        return []
    except Exception as e:
        print(f"[scheduler] load failed: {e}")
        return []


def _save(schedules: list[dict]) -> None:
    _ensure_dir()
    try:
        tmp = SCHEDULES_FILE.with_suffix(SCHEDULES_FILE.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(schedules, f, indent=2, ensure_ascii=False)
        tmp.replace(SCHEDULES_FILE)
    except Exception as e:
        print(f"[scheduler] save failed: {e}")


_DAY_MAP = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


def _parse_time(time_str: str):
    """Parse a time string into a datetime.time. Supports '14:30', '2:30 PM', '9am'."""
    s = (time_str or "").strip().upper().replace(" ", "")
    m = re.match(r"^(\d{1,2})(?::(\d{2}))?(AM|PM)?$", s)
    if not m:
        return None
    h = int(m.group(1)); mins = int(m.group(2) or 0); ampm = m.group(3)
    if ampm == "PM" and h < 12: h += 12
    if ampm == "AM" and h == 12: h = 0
    if not (0 <= h < 24 and 0 <= mins < 60):
        return None
    from datetime import time as _t
    return _t(hour=h, minute=mins)


def _next_occurrence(target_time, recur_type: str) -> datetime:
    """Calculate the next occurrence for a recurring schedule."""
    now = datetime.now()
    today = now.date()
    if recur_type == "daily":
        candidate = datetime.combine(today, target_time)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate
    if recur_type in _DAY_MAP:
        target_weekday = _DAY_MAP[recur_type]
        days_ahead = (target_weekday - today.weekday()) % 7
        if days_ahead == 0:
            candidate = datetime.combine(today, target_time)
            if candidate <= now:
                days_ahead = 7
        candidate = datetime.combine(today + timedelta(days=days_ahead), target_time)
        return candidate
    # Unknown recurrence — fire once today/tomorrow.
    return datetime.combine(today + timedelta(days=1), target_time)


def add_schedule(message: str,
                 time_str: str | None = None,
                 date_str: str | None = None,
                 minutes: int | None = None,
                 recurring: str | None = None) -> dict:
    """Create a new schedule entry. Returns the created schedule."""
    schedule_id = str(uuid.uuid4())[:8]
    now = datetime.now()

    if minutes is not None:
        when = (now + timedelta(minutes=int(minutes))).isoformat(timespec="seconds")
        sched = {"id": schedule_id, "message": message, "fire_at": when, "recurring": None, "active": True}
    elif recurring:
        t = _parse_time(time_str or "") or now.time()
        when = _next_occurrence(t, recurring.lower()).isoformat(timespec="seconds")
        sched = {"id": schedule_id, "message": message, "fire_at": when, "recurring": recurring, "active": True}
    else:
        t = _parse_time(time_str or "")
        d = date_str or now.date().isoformat()
        if t is None:
            return {"error": "Could not parse time"}
        when_dt = datetime.fromisoformat(f"{d}T{t.isoformat()}")
        if when_dt <= now:
            when_dt += timedelta(days=1)
        sched = {"id": schedule_id, "message": message, "fire_at": when_dt.isoformat(timespec="seconds"), "recurring": None, "active": True}

    with _lock:
        _schedules.append(sched)
        _save(_schedules)
    return sched


def remove_schedule(schedule_id: str) -> bool:
    with _lock:
        before = len(_schedules)
        _schedules[:] = [s for s in _schedules if s.get("id") != schedule_id]
        changed = len(_schedules) != before
        if changed:
            _save(_schedules)
    return changed


def list_schedules() -> list[dict]:
    with _lock:
        return [dict(s) for s in _schedules if s.get("active", True)]


def _check_loop() -> None:
    """Background thread that checks for due schedules every 30 seconds."""
    while _running:
        try:
            now = datetime.now()
            to_save = False
            for s in list(_schedules):
                if not s.get("active", True):
                    continue
                try:
                    fire_at = datetime.fromisoformat(s["fire_at"])
                except Exception:
                    continue
                if now < fire_at:
                    continue
                # Fire!
                msg = s.get("message", "")
                if _fire_callback:
                    try:
                        _fire_callback(msg)
                    except Exception as e:
                        print(f"[scheduler] callback raised: {e}")
                if s.get("recurring"):
                    t = _parse_time(fire_at.strftime("%H:%M")) or fire_at.time()
                    s["fire_at"] = _next_occurrence(t, s["recurring"]).isoformat(timespec="seconds")
                else:
                    s["active"] = False
                to_save = True
            if to_save:
                with _lock:
                    _save(_schedules)
        except Exception as e:
            print(f"[scheduler] loop error: {e}")
        _time.sleep(30)


def start(fire_callback: Callable[[str], None] | None = None) -> None:
    """Start the scheduler background thread.
    fire_callback(message: str) is called when a schedule is due."""
    global _fire_callback, _schedules, _running, _thread
    _fire_callback = fire_callback
    with _lock:
        _schedules = _load()
    _running = True
    _thread = threading.Thread(target=_check_loop, daemon=True, name="ame-scheduler")
    _thread.start()
    active_count = sum(1 for s in _schedules if s.get("active", True))
    print(f"[scheduler] Started with {active_count} active schedule(s)" if active_count
          else "[scheduler] Started (no active schedules)")


def stop() -> None:
    global _running
    _running = False
