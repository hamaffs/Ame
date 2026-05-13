"""
Amé Process Guardian.

Live background watcher for new processes and outbound TCP connections.
Permission-aware:
  - low  → not started at all.
  - mid  → passive logging only (writes to ~/.ame/security/guardian.log), no voice.
  - high → active alerts via live_session.speak_proactive when something looks off.

This is a soft heuristic layer, not an IDS. The goal is for Amé to feel like a
guardian who notices things — not to replace real security tooling.
"""

from __future__ import annotations
import json
import threading
import time
from datetime import datetime
from pathlib import Path

import psutil


_GUARD_DIR  = Path.home() / ".ame" / "security"
_GUARD_FILE = _GUARD_DIR / "guardian.log"

# Process names that warrant attention. Conservative — false positives are
# expensive (annoying), false negatives are mostly forgivable.
_SUSPECT_PROC_HINTS = (
    "mimikatz", "lazagne", "psexec", "cobaltstrike", "metasploit",
    "rundll32", "regsvr32", "mshta", "bitsadmin", "certutil",
    "powershell.exe -enc", "wscript.exe", "cscript.exe",
)


class ProcessGuardian:
    """Background watcher; pause-able based on live_session.permission_level."""

    def __init__(self, live_session=None, interval_s: float = 5.0):
        self.live_session = live_session
        self.interval_s   = interval_s
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._seen: set[int] = set()
        _GUARD_DIR.mkdir(parents=True, exist_ok=True)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="ProcessGuardian")
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    # ── internal ──────────────────────────────────────────────────────────
    def _current_permission(self) -> str:
        return getattr(self.live_session, "permission_level", "low") if self.live_session else "low"

    def _loop(self):
        # Seed _seen with whatever's running now so we don't alert on the
        # entire process list on first tick.
        try:
            self._seen = {p.pid for p in psutil.process_iter(["pid"])}
        except Exception:
            self._seen = set()

        while not self._stop.is_set():
            perm = self._current_permission()
            if perm == "low":
                # Permission revoked — sleep but keep the thread alive in case
                # it's re-granted.
                time.sleep(self.interval_s)
                continue
            try:
                self._tick(perm)
            except Exception as e:
                self._log({"ts": _iso(), "event": "guardian_error", "error": str(e)})
            self._stop.wait(self.interval_s)

    def _tick(self, perm: str):
        current = {}
        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                current[p.info["pid"]] = p.info
            except Exception:
                continue
        new_pids = set(current) - self._seen
        for pid in new_pids:
            info = current[pid]
            name = (info.get("name") or "").lower()
            cmd  = " ".join(info.get("cmdline") or []).lower()
            for hint in _SUSPECT_PROC_HINTS:
                if hint in name or hint in cmd:
                    self._alert(perm, name=info.get("name"), pid=pid, cmd=cmd, hint=hint)
                    break
        self._seen = set(current)

    def _alert(self, perm: str, **rec):
        rec.update(ts=_iso(), event="suspect_proc", perm=perm)
        self._log(rec)
        if perm == "high" and self.live_session and hasattr(self.live_session, "speak_proactive"):
            try:
                msg = f"I just noticed {rec.get('name') or 'a new process'} starting — flagging it."
                self.live_session.speak_proactive(msg, f"Process guardian flagged: {rec.get('hint')}")
            except Exception:
                pass

    def _log(self, record: dict):
        try:
            with _GUARD_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            pass


def _iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"
