"""
Amé Context Engine — Unified Situational Awareness Layer.

Synthesizes OS idle time, active window title, user tone, and screen content
to trigger context-driven proactive interventions.

This is the *lean* implementation: the heavy vision pipeline (analyze_screen
loop, ambient cue scheduling, screen-fingerprint deduping) is intentionally
omitted to keep the boot path simple on Linux. The public API matches what
server.py calls — start / stop / set_enabled / mark_activity — so the
server can boot and the proactive layer can be expanded later without
changing the call sites.
"""

from __future__ import annotations
import ctypes
import json
import os
import subprocess
import sys
import threading
import time
from collections import deque


_STATE_FILE = os.path.join(os.path.expanduser("~"), ".ame", "context_engine_state.json")


def _load_persistent_state() -> dict:
    try:
        if not os.path.exists(_STATE_FILE):
            return {}
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_persistent_state(state: dict) -> None:
    try:
        os.makedirs(os.path.dirname(_STATE_FILE), exist_ok=True)
        with open(_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"[ContextEngine] state save failed: {e}")


# ── Platform probes (degrade gracefully) ──────────────────────────────────

def get_os_idle_time() -> float:
    """Returns seconds since the last mouse/keyboard input.
    Returns 0.0 if the platform can't tell us (Wayland without ext_idle)."""
    try:
        if sys.platform == "win32":
            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
            lii = LASTINPUTINFO()
            lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
            ctypes.windll.kernel32.GetTickCount.restype = ctypes.c_uint
            if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
                tick = ctypes.windll.kernel32.GetTickCount()
                millis = (tick - lii.dwTime) & 0xFFFFFFFF
                return millis / 1000.0
            return 0.0
        if sys.platform == "darwin":
            # `ioreg` exposes idle in nanoseconds via the HID system.
            try:
                out = subprocess.check_output(
                    ["ioreg", "-c", "IOHIDSystem"], text=True, stderr=subprocess.DEVNULL, timeout=2,
                )
                for line in out.splitlines():
                    if "HIDIdleTime" in line:
                        ns = int(line.split("=")[-1].strip())
                        return ns / 1_000_000_000
            except Exception:
                pass
            return 0.0
        # Linux — xprintidle on X11; nothing universal on Wayland.
        try:
            out = subprocess.check_output(["xprintidle"], text=True, stderr=subprocess.DEVNULL, timeout=1)
            return int(out.strip()) / 1000.0
        except Exception:
            return 0.0
    except Exception:
        return 0.0


def get_active_window_title() -> str:
    """Returns the title of the currently focused OS window, or ''."""
    try:
        if sys.platform == "win32":
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            return buf.value.strip()
        if sys.platform == "darwin":
            try:
                out = subprocess.check_output(
                    ["osascript", "-e",
                     'tell application "System Events" to get name of (processes whose frontmost is true)'],
                    text=True, stderr=subprocess.DEVNULL, timeout=2,
                )
                return out.strip().strip("{}")
            except Exception:
                return ""
        # Linux — xdotool first, then wmctrl.
        for cmd in (["xdotool", "getactivewindow", "getwindowname"],
                    ["bash", "-c", "wmctrl -l -p | grep $(xdotool getactivewindow) | cut -d' ' -f5-"]):
            try:
                out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL, timeout=1)
                return out.strip()
            except Exception:
                continue
        return ""
    except Exception:
        return ""


# ── Engine ─────────────────────────────────────────────────────────────────

_SENSITIVE_TITLE_KEYWORDS = [
    "bank", "banking", "paypal", "venmo", "zelle", "chase", "wells fargo",
    "citi", "capital one", "amex", "credit card", "debit card",
    "1password", "lastpass", "bitwarden", "keepass", "dashlane",
    "password", "keychain", "credential", "vault", "authenticator", "2fa", "otp",
    "private", "incognito", "inprivate",
    "medical", "health record", "hipaa", "tax return", "social security", "ssn",
]


class ContextEngine:
    """Central brain that monitors local context and signals proactive cues.

    Lean version: tracks idle time + active window every few seconds and
    flips into 'focus mode' awareness without invoking the full vision pipeline
    until the user enables it via set_enabled(True).
    """

    def __init__(self, sio, loop, live_session=None):
        self.sio = sio
        self._main_loop = loop
        self._live_session = live_session
        self._running = False
        self._enabled = False
        self._thread: threading.Thread | None = None
        self._last_activity = time.time()
        self._last_check_time = 0.0
        self._last_screen_summary = ""
        self._last_title = ""
        self._window_start_time = time.time()
        self._session_start = time.time()
        self._last_break_reminder = 0.0
        self._persistent = _load_persistent_state()
        self._proactive_cooldown_until = 0.0
        self._uptime_started_at = time.time()
        self._decision_log: "deque[dict]" = deque(maxlen=4000)
        self._stable_ticks = 0

    # ── Public API used by server.py ──────────────────────────────────────
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="ContextEngine")
        self._thread.start()
        print("[ContextEngine] Started Unified Situational Awareness Layer")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        # Persist whatever state we care about.
        _save_persistent_state({
            "last_session_end": time.time(),
        })
        print("[ContextEngine] Stopped")

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        print(f"[ContextEngine] {'Enabled' if enabled else 'Disabled'}")

    def mark_activity(self) -> None:
        """Mark that the user just spoke to Amé, resetting the idle threshold."""
        self._last_activity = time.time()

    # ── Loop ──────────────────────────────────────────────────────────────
    def _run(self) -> None:
        while self._running:
            try:
                self._tick()
            except Exception as e:
                print(f"[ContextEngine] tick error: {e}")
            time.sleep(5.0)

    def _tick(self) -> None:
        now = time.time()
        title = get_active_window_title()
        idle  = get_os_idle_time()

        # Window transition tracking.
        if title and title != self._last_title:
            self._window_start_time = now
            self._last_title = title

        # If disabled, just observe — never speak.
        if not self._enabled:
            return

        # Sensitive screen guard — never analyze passwords / banking pages.
        title_low = (title or "").lower()
        if any(kw in title_low for kw in _SENSITIVE_TITLE_KEYWORDS):
            return

        # Cooldown to avoid spamming proactive cues.
        if now < self._proactive_cooldown_until:
            return

        # The full proactive analysis flow (vision, tone, etc.) is intentionally
        # left as a future expansion point. For now, only log decisions so the
        # UI / diagnostics have data to display.
        self._decision_log.append({
            "ts": now, "title": title, "idle": idle,
            "decision": "IGNORE", "reason": "lean-mode-no-vision",
        })


# Re-export for callers using `from backend.context_engine import …`.
__all__ = ["ContextEngine", "get_os_idle_time", "get_active_window_title"]
