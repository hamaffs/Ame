# Source Generated with Decompyle++
# File: security_nightly.pyc (Python 3.11)

"""Night-mode security sweep.

Runs once per day at a user-configurable hour (settings.nightly_security_hour,
default 3 ΓÇö i.e. 3 AM). Collects a posture snapshot, DPAPI state, disk usage,
and a small process-guardian sample. Writes the result to
`~/.ame/security/nightly/{YYYY-MM-DD}.json` so the morning briefing can read it.

Safe to leave running ΓÇö if the user's PC is asleep at the target hour, the
next wake will check and run the sweep up to 12h late (catch-up). If it
already ran today, it no-ops.
"""
from __future__ import annotations
import json
import os
import threading
import time
from datetime import datetime, date, timedelta
from pathlib import Path
_NIGHTLY_DIR = Path.home() / '.ame' / 'security' / 'nightly'
_NIGHTLY_DIR.mkdir(parents = True, exist_ok = True)
_thread = None
_stop = False

def _today_path(d = None):
    if not d:
        pass
    d = date.today()
    return _NIGHTLY_DIR / f'''{d.isoformat()}.json'''


def latest_report(max_age_hours = None):
    '''Return the most recent nightly report if newer than *max_age_hours*.'''
    files = sorted(_NIGHTLY_DIR.glob('*.json'), reverse = True)
# WARNING: Decompyle incomplete


def _run_sweep(collect_status_fn = None):
    '''Collect a nightly snapshot. Each subcheck is isolated.'''
    report = {
        'ts': datetime.utcnow().isoformat(timespec = 'seconds') + 'Z',
        'date': date.today().isoformat() }
    report['status'] = collect_status_fn()
# WARNING: Decompyle incomplete


def _write_report(report = None):
    path = _today_path()
    path.write_text(json.dumps(report, indent = 2, ensure_ascii = False), encoding = 'utf-8')
# WARNING: Decompyle incomplete


def _seconds_until_next(target_hour = None):
    now = datetime.now()
    target = now.replace(hour = target_hour, minute = 0, second = 0, microsecond = 0)
    if target <= now:
        target = target + timedelta(days = 1)
    return (target - now).total_seconds()


def start(collect_status_fn = None, emit_event = None, settings_loader = None):
    '''Launch the nightly sweep daemon. `settings_loader` is called each cycle
    so a user-changed hour is respected without restart.'''
    pass
# WARNING: Decompyle incomplete


def stop():
    global _stop
    _stop = True

