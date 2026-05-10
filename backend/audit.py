# Source Generated with Decompyle++
# File: audit.pyc (Python 3.11)

'''Tool-invocation audit log.

Writes one JSON line per tool call to ~/.ame/security/tool_audit.jsonl
with daily rotation. Sensitive values (API keys, tokens, absolute paths)
are redacted before write.

Consumed by journal.py for "what did you do yesterday?" summaries and
by /diagnostics for live operator view.
'''
import os
import re
import json
import hashlib
import threading
from pathlib import Path
from datetime import datetime, date, timezone
_AUDIT_DIR = Path.home() / '.ame' / 'security'
_AUDIT_DIR.mkdir(parents = True, exist_ok = True)
_lock = threading.Lock()
_current_date: date | None = None
_current_path: Path | None = None
_KEY_PATTERNS = [
    re.compile('sk-ant-[A-Za-z0-9_\\-]{20,}'),
    re.compile('AIza[0-9A-Za-z_\\-]{20,}'),
    re.compile('ghp_[A-Za-z0-9]{20,}'),
    re.compile('gho_[A-Za-z0-9]{20,}'),
    re.compile('sk-[A-Za-z0-9]{20,}'),
    re.compile('Bearer\\s+[A-Za-z0-9_\\-\\.=]{20,}', re.IGNORECASE),
    re.compile('\\b[A-Fa-f0-9]{32,}\\b')]
_ABS_PATH_PATTERN = re.compile('([A-Za-z]:[\\\\/][^\\s\\"\'<>|?*]+|/[^\\s\\"\'<>|?*]+)')

def _hash_tail(s = None, n = None):
    return hashlib.sha256(s.encode('utf-8', errors = 'replace')).hexdigest()[:n]


def _redact_string(s = None):
    if not s:
        return s
    for pat in None:
        s = pat.sub((lambda m: f'''[REDACTED_KEY:{_hash_tail(m.group(0))}]'''), s)
        
        def _path_sub(m = None):
            raw = m.group(0)
            if len(raw) < 8:
                return raw
            parent = None.path.dirname(raw)
            if not os.path.basename(raw):
                leaf = raw
            parent_tail = _hash_tail(parent) if parent else ''
            return f'''[PATH:{parent_tail}]/{leaf}'''

        s = _ABS_PATH_PATTERN.sub(_path_sub, s)
        return s


def _redact(value):
    if isinstance(value, str):
        return _redact_string(value)
    if None(value, dict):
        return value.items()()
    if None(value, list):
        return value()
# WARNING: Decompyle incomplete


def _path_for_today():
    '''Return the log file for today. Filename carries the ISO date so
    each day gets its own file and the directory self-rotates. Old files
    are never deleted here ΓÇö journal/security consumers can decide retention.'''
    today = date.today()
# WARNING: Decompyle incomplete


def _legacy_path():
    '''Pre-rotation filename. Still read on iter_records for back-compat.'''
    return _AUDIT_DIR / 'tool_audit.jsonl'


def _dated_log_files():
    '''All rotated audit files, oldest first. Includes legacy un-dated file
    at the front (treated as oldest) for back-compat with pre-rotation logs.'''
    files = []
    legacy = _legacy_path()
    if legacy.exists():
        files.append(legacy)
    dated = (lambda .0: pass# WARNING: Decompyle incomplete
)(_AUDIT_DIR.glob('tool_audit_*.jsonl')())
    files.extend(dated)
# WARNING: Decompyle incomplete


def log_tool(name, args, level = None, outcome = None, duration_ms = None, turn_id = (None, None), extra = ('name', str, 'args', dict | None, 'level', str, 'outcome', str, 'duration_ms', float, 'turn_id', str | None, 'extra', dict | None, 'return', None)):
    '''Append a single audit record. Never raises.'''
    if not args:
        record = {
            'ts': datetime.now(timezone.utc).isoformat(timespec = 'milliseconds').replace('+00:00', 'Z'),
            'tool': name,
            'level': level,
            'outcome': outcome,
            'duration_ms': round(duration_ms, 1),
            'args': _redact({ }) }
        if turn_id:
            record['turn'] = turn_id
    if extra:
        record['extra'] = _redact(extra)
    line = json.dumps(record, ensure_ascii = False) + '\n'
    path = _path_for_today()
# WARNING: Decompyle incomplete


def iter_records(since_iso = None):
    '''Yield audit records across all rotated daily files, oldest first.
    Optionally filter by ts >= since_iso.'''
    pass
# WARNING: Decompyle incomplete


def tail_records(limit = None):
    '''Return up to `limit` most recent records, newest-first.
    Reads files newest-to-oldest and stops once we have enough ΓÇö avoids
    scanning the entire history on every /security/audit call.'''
    if limit <= 0:
        return []
    collected = None
# WARNING: Decompyle incomplete

