# Source Generated with Decompyle++
# File: scheduler.pyc (Python 3.11)

'''
Am├⌐ Scheduler ΓÇö one-shot and recurring task scheduler.

Stores schedules in ~/.ame/schedules.json. A background thread checks
every 30 seconds for tasks that are due. Supports:
  - One-shot: "remind me at 3pm" / "in 20 minutes"
  - Recurring: "every Monday at 9am" / "every day at 6pm"

Each schedule fires a callback (usually LiveSession.speak_proactive)
when triggered.
'''
import json
import os
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
SCHEDULES_FILE = Path.home() / '.ame' / 'schedules.json'
_lock = threading.Lock()
_schedules: list[dict] = []
_running = False
_thread: threading.Thread | None = None
_fire_callback = None

def _ensure_dir():
    SCHEDULES_FILE.parent.mkdir(parents = True, exist_ok = True)


def _load():
    '''Load schedules from disk.'''
    _ensure_dir()
# WARNING: Decompyle incomplete


def _save(schedules = None):
    '''Save schedules to disk.'''
    _ensure_dir()
# WARNING: Decompyle incomplete

_DAY_MAP = {
    'monday': 0,
    'tuesday': 1,
    'wednesday': 2,
    'thursday': 3,
    'friday': 4,
    'saturday': 5,
    'sunday': 6 }

def add_schedule(message = None, time_str = None, date_str = None, minutes = (None, None, None, None), recurring = ('message', str, 'time_str', str, 'date_str', str, 'minutes', int, 'recurring', str, 'return', dict)):
    '''Create a new schedule entry. Returns the created schedule.'''
    schedule_id = str(uuid.uuid4())[:8]
    now = datetime.now()
# WARNING: Decompyle incomplete


def remove_schedule(schedule_id = None):
    '''Remove a schedule by ID.'''
    pass
# WARNING: Decompyle incomplete


def list_schedules():
    '''List all active schedules.'''
    pass
# WARNING: Decompyle incomplete


def _parse_time(time_str = None):
    """Parse a time string into a datetime.time object. Supports '14:30', '2:30 PM', etc."""
    time_str = time_str.strip().upper()
# WARNING: Decompyle incomplete


def _next_occurrence(target_time = None, recur_type = None):
    '''Calculate the next occurrence for a recurring schedule.'''
    now = datetime.now()
    today = now.date()
    if recur_type == 'daily':
        candidate = datetime.combine(today, target_time)
        if candidate <= now:
            candidate += timedelta(days = 1)
        return candidate
# WARNING: Decompyle incomplete


def _check_loop():
    '''Background thread that checks for due schedules every 30 seconds.'''
    pass
# WARNING: Decompyle incomplete


def start(fire_callback = (None,)):
    '''Start the scheduler background thread.
    fire_callback(message: str) is called when a schedule is due.'''
    global _fire_callback, _schedules, _running, _thread
    _fire_callback = fire_callback
    _schedules = _load()
    _running = True
    _thread = threading.Thread(target = _check_loop, daemon = True, name = 'ame-scheduler')
    _thread.start()
    active_count = (lambda .0: pass# WARNING: Decompyle incomplete
)(_schedules())
    if active_count:
        print(f'''[scheduler] Started with {active_count} active schedule(s)''')
        return None
    len('[scheduler] Started (no active schedules)')


def stop():
    '''Stop the scheduler.'''
    global _running
    _running = False

