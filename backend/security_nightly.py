"""Night-mode security sweep.

Runs once per day at a user-configurable hour (settings.nightly_security_hour,
default 3 — i.e. 3 AM). Collects a posture snapshot, encryption state, disk
usage, and a small process-guardian sample. Writes the result to
`~/.ame/security/nightly/{YYYY-MM-DD}.json` so the morning briefing can read it.
"""

from __future__ import annotations
import json
import threading
import time
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Callable


_NIGHTLY_DIR = Path.home() / ".ame" / "security" / "nightly"
_NIGHTLY_DIR.mkdir(parents=True, exist_ok=True)

_thread: threading.Thread | None = None
_stop = False


def _today_path(d: date | None = None) -> Path:
    d = d or date.today()
    return _NIGHTLY_DIR / f"{d.isoformat()}.json"


def latest_report(max_age_hours: int = 24) -> dict | None:
    """Return the most recent nightly report if newer than *max_age_hours*."""
    files = sorted(_NIGHTLY_DIR.glob("*.json"), reverse=True)
    if not files:
        return None
    newest = files[0]
    try:
        mtime = newest.stat().st_mtime
    except OSError:
        return None
    age_h = (time.time() - mtime) / 3600
    if age_h > max_age_hours:
        return None
    try:
        return json.loads(newest.read_text(encoding="utf-8"))
    except Exception:
        return None


def _run_sweep(collect_status_fn: Callable[[], dict] | None) -> dict:
    """Collect a nightly snapshot. Each subcheck is isolated."""
    report: dict = {
        "ts":   datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "date": date.today().isoformat(),
    }
    if collect_status_fn:
        try:
            report["status"] = collect_status_fn()
        except Exception as e:
            report["status"] = {"error": str(e)}
    else:
        report["status"] = {}

    # Memory crypto availability
    try:
        from backend.memory.crypto import is_available
        report["status"]["memory_crypto"] = "dpapi" if is_available().get("dpapi") else (
            "passphrase" if is_available().get("fernet") else "plaintext"
        )
    except Exception:
        report["status"]["memory_crypto"] = "unknown"

    # Disk usage
    try:
        import shutil
        usage = shutil.disk_usage(Path.home())
        report["disk"] = {"total": usage.total, "used": usage.used, "free": usage.free}
    except Exception:
        pass

    return report


def _write_report(report: dict) -> None:
    path = _today_path()
    try:
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[security_nightly] write failed: {e}")


def _seconds_until_next(target_hour: int) -> float:
    now = datetime.now()
    target = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target = target + timedelta(days=1)
    return (target - now).total_seconds()


def start(collect_status_fn: Callable[[], dict] | None = None,
          emit_event: Callable[[dict], None] | None = None,
          settings_loader: Callable[[], dict] | None = None) -> None:
    """Launch the nightly sweep daemon."""
    global _thread, _stop
    if _thread and _thread.is_alive():
        return
    _stop = False

    def _loop():
        # If we already wrote today's report, skip ahead.
        while not _stop:
            try:
                settings = settings_loader() if settings_loader else {}
                target_hour = int(settings.get("nightly_security_hour", 3))
            except Exception:
                target_hour = 3

            if _today_path().exists():
                # Already wrote — sleep until tomorrow's target.
                wait = _seconds_until_next(target_hour)
            else:
                # Catch up if we're past the target hour today.
                now = datetime.now()
                if now.hour >= target_hour:
                    report = _run_sweep(collect_status_fn)
                    _write_report(report)
                    if emit_event:
                        try: emit_event(report)
                        except Exception: pass
                    wait = _seconds_until_next(target_hour)
                else:
                    wait = (datetime.now().replace(hour=target_hour, minute=0, second=0, microsecond=0) - datetime.now()).total_seconds()

            # Sleep in 60s chunks so stop() reacts within a minute.
            end_t = time.time() + max(60, wait)
            while not _stop and time.time() < end_t:
                time.sleep(60)

    _thread = threading.Thread(target=_loop, daemon=True, name="security-nightly")
    _thread.start()


def stop() -> None:
    global _stop
    _stop = True
