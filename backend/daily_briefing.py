# Source Generated with Decompyle++
# File: daily_briefing.pyc (Python 3.11)

"""
Am├⌐ Daily Briefing ΓÇö first-interaction-of-the-day personal briefing.

Runs ONCE per day, only if it's morning (5amΓÇônoon) and the briefing for
today hasn't already been delivered:
1. Weather (free wttr.in API)
2. What you were working on yesterday (from task memory)
3. News about your interests (from news_watcher logic)

Delivers as a single spoken summary on first interaction.
"""
import json
import os
import threading
import time
from datetime import datetime
_has_run = False
_BRIEFING_STAMP = os.path.join(os.path.expanduser('~'), '.ame', 'last_briefing.json')

def _already_briefed_today():
    '''Return True if a briefing was already delivered today.'''
    if not os.path.exists(_BRIEFING_STAMP):
        return False
# WARNING: Decompyle incomplete


def _mark_briefed_today():
    os.makedirs(os.path.dirname(_BRIEFING_STAMP), exist_ok = True)
# WARNING: Decompyle incomplete


def start_daily_briefing(live_session):
    '''Launch the daily briefing in a background thread.'''
    global _has_run
    if _has_run:
        return None
    hour = None.now().hour
    if hour < 5 or hour >= 12:
        print(f'''[DailyBriefing] Skipped ΓÇö not morning (hour={hour})''')
        return None
    if None():
        print('[DailyBriefing] Skipped ΓÇö already delivered today')
        return None
    _has_run = None
    t = threading.Thread(target = _run, args = (live_session,), daemon = True, name = 'DailyBriefing')
    t.start()
    print('[DailyBriefing] Scheduled (15s delay)')


def _run(live_session):
    '''Main worker ΓÇö assembles the briefing.'''
    time.sleep(15)
    _load_settings = _load_settings
    import backend.live_session
    if not _load_settings().get('news_enabled', True):
        print('[DailyBriefing] News disabled ΓÇö running minimal briefing')
# WARNING: Decompyle incomplete


def _get_weather():
    '''Get weather from wttr.in (free, no API key needed).'''
    import httpx
    location = ''
    _id_layer = identity
    import backend.memory
    data = _id_layer.load_identity()
    id_data = data.get('identity', { })
    for key in ('location', 'city', 'country'):
        val = id_data.get(key, { })
        if isinstance(val, dict):
            val = val.get('value', '')
        if val:
            location = str(val)
        
# WARNING: Decompyle incomplete


def _summarize_nightly(report = None):
    '''Turn a nightly report into one short natural-language line.'''
    bits = []
    if not report.get('status'):
        status = { }
        if not status.get('defender'):
            defender = { }
            if isinstance(defender, dict):
                rt = defender.get('RealTimeProtectionEnabled')
                if rt is False:
                    bits.append('Defender real-time protection was off')
    if not status.get('firewall'):
        firewall = []
        if isinstance(firewall, dict):
            firewall = [
                firewall]
    disabled_fw = firewall()
    if disabled_fw:
        'firewall disabled on '(f'''{(lambda .0: pass# WARNING: Decompyle incomplete
)(disabled_fw())}''')
    crypto_mode = status.get('memory_crypto')
    if crypto_mode and crypto_mode not in ('dpapi', 'passphrase'):
        bits.append(f'''memory encryption not active ({crypto_mode})''')
# WARNING: Decompyle incomplete


def _get_yesterday_tasks():
    '''Get what the user was working on from task memory.'''
    get_active_tasks = get_active_tasks
    import backend.memory.identity
    tasks = get_active_tasks()
    if tasks:
        return tasks[0][:100]
# WARNING: Decompyle incomplete

