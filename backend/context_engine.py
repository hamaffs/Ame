# Source Generated with Decompyle++
# File: context_engine.pyc (Python 3.11)

'''
Am├⌐ Context Engine ΓÇö Unified Situational Awareness Layer.

Replaces the old mechanical ScreenWatcher. 
Synthesizes OS idle time, active window title, user tone, and screen content
to trigger hyper-aware, context-driven proactive interventions.
'''
import base64
import json
import os
import threading
import time
import ctypes
from collections import deque
_STATE_FILE = os.path.join(os.path.expanduser('~'), '.ame', 'context_engine_state.json')

def _load_persistent_state():
    pass
# WARNING: Decompyle incomplete


def _save_persistent_state(state = None):
    os.makedirs(os.path.dirname(_STATE_FILE), exist_ok = True)
# WARNING: Decompyle incomplete

from backend import vision as _vision_module

def get_os_idle_time():
    '''Returns how many seconds the user has been physically idle (no mouse/keyboard).'''
    
    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [
            ('cbSize', ctypes.c_uint),
            ('dwTime', ctypes.c_uint)]

    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    ctypes.windll.kernel32.GetTickCount.restype = ctypes.c_uint
    if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
        tick = ctypes.windll.kernel32.GetTickCount()
        millis = tick - lii.dwTime & 0xFFFFFFFF
        return millis / 1000
# WARNING: Decompyle incomplete


def get_active_window_title():
    '''Returns the title of the currently focused OS window.'''
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value.strip()
# WARNING: Decompyle incomplete

PROACTIVE_PROMPT = 'You are AM├ë, a highly aware personal AI assistant. \nYou are silently monitoring the user\'s context and screen to decide if you should proactively speak up to help them.\n\n{context_str}\n\nYour job is to decide TWO things:\n1. Does the user need help RIGHT NOW based on their tone, idle time, active window, and screen content?\n2. If yes, what is the most natural, human, and empathetic thing to say?\n\nURGENT INTERVENTION (Respond immediately):\n- The user is \'frustrated\' on an error, crash, or bug.\n- The user has been staring at an error, bug, or crash for a while.\n- A critical error or blocking popup is on screen.\n\nPASSIVE INTERVENTION (Respond gently):\n- The user sounds \'tired\' and has been working on the same code for a while.\n- You see an obvious typo or issue they missed, even if their tone is neutral.\n\nALWAYS SKIP:\n- Normal workflow (coding, browsing, gaming) when there are NO visible errors.\n- The EXACT SAME situation/error you already addressed (do not nag).\n- If you are not 100% confident your interruption will be genuinely helpful.\n\nRESPONSE FORMAT (Pick exactly ONE):\nURGENT: [one short, natural sentence] ||| [Extract the exact error/code AND write a brief step-by-step solution to fix it so you can answer instantly if asked]\nPASSIVE: [one short, gentle sentence] ||| [Extract the exact issue AND write the solution]\nSKIP: [briefly explain why you skipped]\n\nDO NOT output "Reasoning:". Use the exact format above, separated by |||.\n\nExample URGENT: Looks like a recursion error, want some help? ||| Error: RecursionError on line 42. Solution: Add a base case `if n == 0: return 1` at the start of the factorial function.\n'

class ContextEngine:
    '''Central brain that monitors all local context streams and triggers AI vision when needed.'''
    
    def __init__(self, sio, loop, live_session = (None,)):
        self.sio = sio
        self._main_loop = loop
        self._live_session = live_session
        self._running = False
        self._enabled = False
        self._thread = None
        self._last_activity = 0
        self._last_check_time = 0
        self._last_screen_summary = ''
        self._last_title = ''
        self._window_start_time = time.time()
        self._session_start = time.time()
        self._last_break_reminder = 0
        self._persistent = _load_persistent_state()
        self._last_downloads_check = float(self._persistent.get('last_downloads_check', 0))
        self._last_downloads_warning = float(self._persistent.get('last_downloads_warning', 0))
        self._last_git_check = 0
        self._notified_git_repos = set()
        self._focus_mode = False
        self._focus_queue = []
        self._focus_start = 0
        self._focus_suggested = False
        self._last_ambient_cue = 0
        self._last_cue_kind = ''
        self._was_idle_deep = False
        self._cpu_spike_until = 0
        self._last_emotion = ''
        self._last_emotion_at = 0
        self._last_clipboard_warning = 0
        self._last_quota_health = 'healthy'
        self._last_quota_check = 0
        self._spoke_quota_notice_for = ''
        self._proactive_cooldown_until = 0
        ClipboardSentinel = ClipboardSentinel
        import backend.observation_signals
        self._clipboard = ClipboardSentinel()
        self._last_gate_run = 0
        self._last_gate_decision = 'IGNORE'
        self._uptime_started_at = time.time()
        self._decision_log = deque(maxlen = 4000)
        self._vision_log = deque(maxlen = 1000)
        self._stable_skip_count = 0
        self._last_fingerprint = ''
        self._stable_ticks = 0

    
    def start(self):
        if self._thread and self._thread.is_alive():
            return None
        self._running = None
        self._thread = threading.Thread(target = self._run, daemon = True, name = 'ContextEngine')
        self._thread.start()
        print('[ContextEngine] Started Unified Situational Awareness Layer')

    
    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout = 3)
        print('[ContextEngine] Stopped')

    
    def set_enabled(self = None, enabled = None):
        self._enabled = enabled
        print(f'''[ContextEngine] {'Enabled' if enabled else 'Disabled'}''')

    
    def mark_activity(self):
        '''Mark that the user just spoke to Am├⌐, resetting the idle threshold.'''
        self._last_activity = time.time()

    
    def _run(self):
        pass
    # WARNING: Decompyle incomplete

    _SENSITIVE_TITLE_KEYWORDS = [
        'bank',
        'banking',
        'paypal',
        'venmo',
        'zelle',
        'chase',
        'wells fargo',
        'citi',
        'capital one',
        'amex',
        'credit card',
        'debit card',
        '1password',
        'lastpass',
        'bitwarden',
        'keepass',
        'dashlane',
        'password',
        'keychain',
        'credential',
        'vault',
        'authenticator',
        '2fa',
        'otp',
        'private',
        'incognito',
        'inprivate',
        'medical',
        'health record',
        'hipaa',
        'tax return',
        'social security',
        'ssn']
    
    def _analyze_context(self, reason, idle_time, tone, title, time_on_window):
        pass
    # WARNING: Decompyle incomplete

    
    def set_focus_mode(self = None, enabled = None):
        '''Toggle focus mode. In focus mode, passive proactive messages are queued.'''
        self._focus_mode = enabled
        if enabled:
            self._focus_queue = []
            self._focus_start = time.time()
            print('[ContextEngine] Focus mode ON ΓÇö suppressing passive notifications')
            return None
        held = None(self._focus_queue)
        duration = time.time() - self._focus_start if self._focus_start else 0
        print(f'''[ContextEngine] Focus mode OFF ΓÇö releasing {held} held notifications''')
        if held > 0 and self.sio and self._main_loop:
            import asyncio
            summary = f'''While you were focused ({int(duration / 60)}m): {held} notification{'s' if held > 1 else ''} held'''
            asyncio.run_coroutine_threadsafe(self.sio.emit('focus_summary', {
                'summary': summary,
                'count': held,
                'messages': self._focus_queue[:10],
                'duration_minutes': int(duration / 60) }), self._main_loop)
        self._focus_queue = []
        self._focus_start = 0

    
    def set_proactive_cooldown(self = None, cooldown_ms = None):
        '''Suppress proactive emissions for the given duration. Set by the
        frontend when the user ignores a proactive for 10s, or cleared by
        explicit user-summon (hotkey / voice).'''
        self._proactive_cooldown_until = time.time() + max(0, int(cooldown_ms)) / 1000
        remaining = int(max(0, self._proactive_cooldown_until - time.time()))
        print(f'''[ContextEngine] Proactive cooldown set for {remaining}s''')
        return None
    # WARNING: Decompyle incomplete

    
    def clear_proactive_cooldown(self):
        self._proactive_cooldown_until = 0

    
    def _proactive_in_cooldown(self = None):
        return time.time() < self._proactive_cooldown_until

    
    def _emit_observation(self, text, mode = ('passive',)):
        '''Emit a proactive observation to the UI and optionally speak it.
        In focus mode, passive messages are queued; urgent messages still go through.'''
        if self._proactive_in_cooldown() and mode != 'urgent':
            print(f'''[ContextEngine] Suppressed (cooldown): \'{text[:50]}...\'''')
            return None
        if None._focus_mode and mode != 'urgent':
            self._focus_queue.append(text)
            print(f'''[ContextEngine] Focus mode: queued \'{text[:50]}...\'''')
            return None
        if None.sio and self._main_loop:
            import asyncio
            note_emotion = note_emotion
            import backend.thinking_emotion
            note_emotion('curious')
            asyncio.run_coroutine_threadsafe(self.sio.emit('orb_emotion', {
                'emotion': 'curious' }), self._main_loop)
            asyncio.run_coroutine_threadsafe(self.sio.emit('orb_travel', {
                'to': 'center',
                'reason': 'proactive' }), self._main_loop)
            asyncio.run_coroutine_threadsafe(self.sio.emit('proactive_message', {
                'text': text,
                'mode': mode }), self._main_loop)
        if self._live_session:
            self._live_session.speak_proactive(text, '')
            return None

    _GATE_PROMPT = "You are AM├ë's silent observer. You are the SINGLE decision point for whether AM├ë takes a screenshot and intervenes. You DO NOT see the screen ΓÇö only the signals below.\n\nSignals:\n- active_window: {window_title}\n- window_category: {window_cat}\n- window_has_error_word: {has_error}\n- time_on_window_seconds: {time_on_window}\n- physical_idle_state: {idle_state} ({idle_seconds}s)\n- recent_voice_tone: {tone}\n- clipboard_changed_recently: {clip_changed}\n- seconds_since_last_vision: {since_last_speak}\n- heavy_trigger: {heavy_trigger}\n\nAbout heavy_trigger: this is set when a coarse rule fired (e.g. user has been idle >25s, on an error window for >30s, or frustrated tone while looking at an error). Treat it as one input among many ΓÇö NOT as a command. A 'staring_at_screen_25s' on a chill workflow is still IGNORE. A 'frustrated_on_error' is almost always SPEAK.\n\nDecision rules:\n- SPEAK: clear evidence of distress or being genuinely stuck (frustrated tone + error word, OR error word with idle > 15s, OR heavy_trigger=frustrated_on_error/stuck_on_error_window). Also SPEAK if the user is mid-creative-work (editor + sustained activity + recent clipboard) and clearly hit a wall (long pause + tone shift).\n- WATCH: something is brewing ΓÇö clipboard change, paused on editor, heavy_trigger fired but signals don't clearly mean stuck. Orb leans in, no speech.\n- IGNORE: normal workflow, browsing, media, games, idle-without-signs. This is the default and should be your most common answer.\n\nBias HEAVILY toward IGNORE. Speaking up incorrectly is worse than missing a moment. Aim for fewer than 5 SPEAK decisions per hour. When in doubt between SPEAK and WATCH, choose WATCH. When in doubt between WATCH and IGNORE, choose IGNORE.\n\nReply with ONE LINE in this exact format:\nDECISION: <reason in <=10 words>\nwhere DECISION is exactly SPEAK, WATCH, or IGNORE."
    
    def _compute_signal_fingerprint(self, title = None, idle_time = None, tone = None, time_on_window = ('title', str, 'idle_time', float, 'tone', str, 'time_on_window', float, 'return', str)):
        """Hash the signals the gate sees. If two consecutive ticks produce
        the same fingerprint, the gate would return the same decision ΓÇö skip.

        Identity prefers the foreground process name (e.g. 'spotify.exe') over
        the window title because titles change for apps with dynamic state ΓÇö
        Spotify shows the track name, browsers show the tab title, Discord
        shows the channel name. Same exe = same activity = stable. We fall
        back to a truncated title only when the process name isn't available
        (rare ΓÇö psutil failure or no foreground window).

        Uses coarse buckets so micro-movements don't bust stability:
        - idle: active / brief / away / deep_away
        - time-on-window: 0-30s / 30-120s / 120s-10m / longer
        - clipboard: changed-recently bool
        - tone passed through (string equality)
        """
        classify_idle = classify_idle
        get_foreground_process_name = get_foreground_process_name
        import backend.observation_signals
        idle_state = classify_idle(idle_time)
        if time_on_window < 30:
            tow_bucket = 'fresh'
        elif time_on_window < 120:
            tow_bucket = 'settled'
        elif time_on_window < 600:
            tow_bucket = 'deep'
        else:
            tow_bucket = 'long'
        clip_changed = self._clipboard.seconds_since_change() < 30
        proc = get_foreground_process_name()
        identity = proc if proc else f'''title:{title[:80]}'''
        return f'''{identity}|{idle_state}|{tone}|{tow_bucket}|{int(clip_changed)}'''

    
    def _run_gate_observation(self, current_time, idle_time = None, tone = None, title = None, time_on_window = ('',), heavy_trigger = ('heavy_trigger', str)):
        '''The SINGLE decision point for whether vision fires.

        Replaces the old "heavy triggers fire vision directly + gate runs in
        parallel" architecture. Now: heavy triggers feed in as `heavy_trigger`
        evidence ΓÇö the gate weighs them alongside the cheap signals and
        decides SPEAK / WATCH / IGNORE. Only on SPEAK does vision actually
        run. Result: 95%+ fewer screenshots taken when nothing\'s happening.
        '''
        pass
    # WARNING: Decompyle incomplete

    
    def get_telemetry(self = None):
        now = time.time()
        hour_ago = now - 3600
        day_ago = now - 86400
        decisions_last_hour = {
            'SPEAK': 0,
            'WATCH': 0,
            'IGNORE': 0 }
        decisions_last_24h = {
            'SPEAK': 0,
            'WATCH': 0,
            'IGNORE': 0 }
        heavy_triggers_24h = { }
        gate_calls_total = len(self._decision_log)
        gate_calls_last_hour = 0
        for ts, decision, trigger, _wc in self._decision_log:
            if decision in decisions_last_24h and ts >= day_ago and trigger:
                heavy_triggers_24h.get(trigger, 0) + 1 = None
            if ts >= hour_ago:
                gate_calls_last_hour += 1
                if decision in decisions_last_hour:
                    pass
            0 = None
            vision_calls_last_24h = 0
            provider_breakdown = { }
            for ts, provider, _latency, _ok in self._vision_log:
                if ts >= day_ago:
                    vision_calls_last_24h += 1
                    bucket = 'local' if provider or 'gemma4' in ''.lower() else 'cloud'
                    provider_breakdown[bucket] = provider_breakdown.get(bucket, 0) + 1
                if ts >= hour_ago:
                    vision_calls_last_hour += 1
        return {
            'uptime_hours': round((now - self._uptime_started_at) / 3600, 2),
            'gate_calls_total': gate_calls_total,
            'gate_calls_last_hour': gate_calls_last_hour,
            'decisions_last_hour': decisions_last_hour,
            'decisions_last_24h': decisions_last_24h,
            'heavy_trigger_breakdown_last_24h': heavy_triggers_24h,
            'vision_calls_last_hour': vision_calls_last_hour,
            'vision_calls_last_24h': vision_calls_last_24h,
            'vision_provider_breakdown_last_24h': provider_breakdown,
            'stable_skips_total': self._stable_skip_count,
            'current_gate_decision': self._last_gate_decision,
            'last_gate_at': self._last_gate_run if self._last_gate_run else None,
            'last_vision_at': self._last_check_time if self._last_check_time else None,
            'quota_health': self._quota_health() }

    
    def _quota_health(self = None):
        """Returns 'healthy' | 'partial' | 'exhausted' based on cooldowns.
        Fail-open: any error ΓåÆ healthy (so we don't show alarm states that
        aren't real)."""
        cooldown_status = cooldown_status
        TASK_MODELS = TASK_MODELS
        import backend.gemini_client
        if not cooldown_status():
            cooled = { }
            if not cooled:
                return 'healthy'
            if None(cooled) >= len(TASK_MODELS):
                return 'exhausted'
            return None
    # WARNING: Decompyle incomplete

    
    def _check_work_break(self, current_time):
        '''Suggest a break after 4+ hours of continuous session.'''
        hours_active = (current_time - self._session_start) / 3600
        if hours_active >= 4 or current_time - self._last_break_reminder > 7200:
            self._last_break_reminder = current_time
            h = int(hours_active)
            self._emit_observation(f'''You\'ve been going for {h} hours straight. Maybe grab some water or stretch a bit?''', 'passive')
            return None
        return None

    
    def _check_downloads_size(self, current_time):
        """Check Downloads folder size periodically and suggest cleanup.

        Throttles persist across restarts so the user isn't nagged on every boot:
        - Folder is scanned at most once per 6h.
        - The actual warning is emitted at most once per 3 days, regardless of restarts.
        """
        wall_now = time.time()
        if current_time - self._last_downloads_check < 21600:
            return None
        self._last_downloads_check = None
        WARNING_COOLDOWN = 259200
        if wall_now - self._last_downloads_warning < WARNING_COOLDOWN:
            self._persistent['last_downloads_check'] = current_time
            _save_persistent_state(self._persistent)
            return None
        downloads = None.path.join(os.path.expanduser('~'), 'Downloads')
        if not os.path.isdir(downloads):
            return None
        total_bytes = 0
    # WARNING: Decompyle incomplete

    
    def _check_git_repos(self, current_time):
        '''Check known project directories for uncommitted changes or stale repos.'''
        if current_time - self._last_git_check < 3600:
            return None
        self._last_git_check = None
        import subprocess
        home = os.path.expanduser('~')
        search_dirs = []
    # WARNING: Decompyle incomplete

    
    def run_observations(self, current_time):
        '''Run all lightweight proactive observations. Called from the main _run loop.'''
        self._check_work_break(current_time)
    # WARNING: Decompyle incomplete

    _CUE_MIN_GAP = {
        'cpu_spike': 45,
        'rest': 120,
        'wake': 30,
        'email_soft': 60,
        'guardian': 10,
        'quota_partial': 30,
        'quota_exhausted': 30,
        'quota_recovered': 30 }
    
    def _ambient_tick(self = None, current_time = None, idle_time = None):
        if self._was_idle_deep and idle_time < 5:
            self._was_idle_deep = False
            self._emit_ambient_cue('wake', current_time, color = 'cyan')
        elif not idle_time > 600 and self._was_idle_deep:
            self._was_idle_deep = True
            self._emit_ambient_cue('rest', current_time, color = 'dim')
        import psutil
        cpu = psutil.cpu_percent(interval = None)
        if cpu >= 85 and current_time > self._cpu_spike_until:
            self._cpu_spike_until = current_time + 45
            self._emit_ambient_cue('cpu_spike', current_time, color = 'amber', meta = {
                'cpu': cpu })
    # WARNING: Decompyle incomplete

    
    def _derive_emotion(self = None, idle_time = None):
        '''Map current local context to an orb emotion, or None to leave as-is.

        Priorities (first match wins):
          - frustrated/tired tone ΓåÆ holding (warm, dim)
          - recent gate WATCH or unresolved error window ΓåÆ curious
          - mid-session deep_away (5ΓÇô10 min) ΓåÆ withdrawn
          - default: watching (the always-on baseline presence)
        '''
        tone = self._live_session._current_tone if self._live_session else 'neutral'
    # WARNING: Decompyle incomplete

    
    def _emit_emotion(self = None, emotion = None):
        """Emit `orb_emotion` to the UI, deduped + lightly throttled.

        The same emotion isn't re-sent within 8s; switching to a new emotion
        is allowed instantly so transitions feel responsive.
        """
        now = time.time()
        if emotion == self._last_emotion and now - self._last_emotion_at < 8:
            return None
        self._last_emotion = None
        self._last_emotion_at = now
        if not self.sio or self._main_loop:
            return None
        import asyncio
        note_emotion = note_emotion
        import backend.thinking_emotion
        note_emotion(emotion)
        asyncio.run_coroutine_threadsafe(self.sio.emit('orb_emotion', {
            'emotion': emotion }), self._main_loop)
        return None
    # WARNING: Decompyle incomplete

    
    def _emit_ambient_cue(self = None, kind = None, current_time = None, color = (None,), meta = ('kind', str, 'current_time', float, 'color', str, 'meta', dict | None)):
        gap = self._CUE_MIN_GAP.get(kind, 30)
        if kind == self._last_cue_kind and current_time - self._last_ambient_cue < gap:
            return None
        self._last_cue_kind = None
        self._last_ambient_cue = current_time
        payload = {
            'kind': kind,
            'color': color,
            'at': current_time }
        if meta:
            payload['meta'] = meta
        if not self.sio or self._main_loop:
            return None
        import asyncio
        asyncio.run_coroutine_threadsafe(self.sio.emit('ambient_cue', payload), self._main_loop)
        return None
    # WARNING: Decompyle incomplete

    
    def emit_external_cue(self = None, kind = None, color = None, meta = ('rose', None)):
        '''Public entry point for other watchers (e.g. ProcessGuardian) to raise a cue.'''
        self._emit_ambient_cue(kind, time.time(), color = color, meta = meta)


