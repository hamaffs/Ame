"""Thin gate layer that emits `orb_emotion('thinking')` before slow router
calls and restores the previous emotion after.

Design constraints:
- No engine-logic modifications. This module never enters the speak path,
  the router, or the state machine. It only emits UI signals.
- Safe if live_session isn't attached (dev scripts, tests): emits are no-ops.
- Restores whatever emotion was current before the call — not a fixed
  default — so we don't overwrite a legitimate 'holding'/'excited'/etc.
- Short calls shouldn't flicker 'thinking': callers pass a threshold, and
  the emit is scheduled via a timer that cancels if the call completes fast.
"""

from __future__ import annotations
import threading
from typing import Optional

_session_ref = None
_last_emotion = "watching"
_lock = threading.Lock()


def register_session(session) -> None:
    """Called once from LiveSession.__init__ so we can emit."""
    global _session_ref
    _session_ref = session


def note_emotion(emotion: str) -> None:
    """Called from anywhere that emits orb_emotion — keeps our 'last known
    emotion' in sync so restores go back to the right state, not a stale one."""
    global _last_emotion
    if not emotion or emotion == "thinking":
        return
    with _lock:
        _last_emotion = emotion


def _emit(emotion: str) -> None:
    """Best-effort emit. Silently no-op if no session attached."""
    s = _session_ref
    if s is None:
        return
    emit_fn = getattr(s, "emit_orb_emotion", None) or getattr(s, "orb_emotion", None)
    if not callable(emit_fn):
        return
    try:
        emit_fn(emotion)
    except Exception:
        pass


class ThinkingEmotion:
    """Context manager: emit 'thinking' on enter, restore on exit.

    Uses a delayed timer so fast calls (< threshold_ms) never flicker the
    emotion. If the call completes before the timer fires, nothing is emitted.
    """

    def __init__(self, threshold_ms: int = 400):
        self.threshold_ms = max(0, int(threshold_ms))
        self._timer: Optional[threading.Timer] = None
        self._emitted = False
        self._prior: Optional[str] = None

    def __enter__(self):
        self._prior = _last_emotion
        if self.threshold_ms == 0:
            self._fire()
        else:
            self._timer = threading.Timer(self.threshold_ms / 1000.0, self._fire)
            self._timer.daemon = True
            self._timer.start()
        return self

    def _fire(self) -> None:
        self._emitted = True
        _emit("thinking")

    def __exit__(self, exc_type, exc, tb):
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        if self._emitted and self._prior:
            _emit(self._prior)
        return False
