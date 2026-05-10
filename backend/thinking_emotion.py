# Source Generated with Decompyle++
# File: thinking_emotion.pyc (Python 3.11)

"""Thin gate layer that emits `orb_emotion('thinking')` before slow router
calls and restores the previous emotion after.

Scope: WP-04. The orb renderer has a `thinking` emotion that nearly holds
her breath (rate 0.2x, depth 0.08) while slow operations run ΓÇö AGENT_PLAN,
CREATIVE_BREAKDOWN, VISION_SCREEN. When the call returns, breath ramps back
up smoothly via the existing emotion lerp.

Design constraints:
- No engine-logic modifications. This module never enters the speak path,
  the router, or the state machine. It only emits UI signals.
- Safe if live_session isn't attached (dev scripts, tests): emits are no-ops.
- Restores whatever emotion was current before the call ΓÇö not a fixed
  default ΓÇö so we don't overwrite a legitimate 'holding'/'excited'/etc.
- Short calls shouldn't flicker 'thinking': callers pass a threshold, and
  the emit is scheduled via a timer that cancels if the call completes fast.
"""
from __future__ import annotations
import threading
from typing import Optional
_session_ref = None
_last_emotion = 'watching'
_lock = threading.Lock()

def register_session(session = None):
    '''Called once from LiveSession.__init__ so we can emit.'''
    global _session_ref
    _session_ref = session


def note_emotion(emotion = None):
    """Called from anywhere that emits orb_emotion ΓÇö keeps our 'last known
    emotion' in sync so restores go back to the right state, not a stale one.
    """
    if emotion or emotion == 'thinking':
        return None
# WARNING: Decompyle incomplete


def _emit(emotion = None):
    '''Best-effort emit. Silently no-op if no session attached.'''
    s = _session_ref
# WARNING: Decompyle incomplete


class ThinkingEmotion:
    """Context manager: emit 'thinking' on enter, restore on exit.

    Uses a delayed timer so fast calls (< threshold_ms) never flicker the
    emotion. If the call completes before the timer fires, nothing is emitted.

    Usage:
        with ThinkingEmotion(threshold_ms=400):
            result = route(Purpose.AGENT_PLAN, prompt, timeout=8)
    """
    
    def __init__(self = None, threshold_ms = None):
        self.threshold_ms = max(0, int(threshold_ms))
        self._timer = None
        self._emitted = False
        self._prior = None

    
    def __enter__(self):
        pass
    # WARNING: Decompyle incomplete

    
    def _fire(self):
        self._emitted = True
        _emit('thinking')

    
    def __exit__(self, exc_type, exc, tb):
        pass
    # WARNING: Decompyle incomplete


