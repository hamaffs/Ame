# Source Generated with Decompyle++
# File: path_guard.pyc (Python 3.11)

'''Filesystem allowlist / blocklist for scan and read operations.

Goal: prevent Am├⌐ from wandering into places she has no business scanning
(System32, credentials, browser cookies, .ssh/.aws/.azure/.gcloud), while
still letting her help with Desktop, Documents, Downloads, and project dirs
the user configures.

Tools that accept a user-supplied path should call `is_allowed(path, mode)`
at the top and bail out with a friendly refusal on False.
'''
from __future__ import annotations
import os
from pathlib import Path
_HOME = Path.home().resolve()
_BLOCKED_ABS: 'list[Path]' = []
_BLOCKED_SUBPATHS: 'list[str]' = [
    'windows',
    'windows/system32',
    'windows/syswow64',
    'program files',
    'program files (x86)',
    'programdata',
    '.ssh',
    '.aws',
    '.gcloud',
    '.azure',
    '.config/gcloud',
    'appdata/local/google/chrome/user data',
    'appdata/local/microsoft/edge/user data',
    'appdata/roaming/mozilla/firefox',
    'appdata/roaming/microsoft/credentials',
    'appdata/roaming/microsoft/protect',
    'appdata/local/microsoft/credentials',
    'appdata/local/microsoft/vault']
_READ_ALLOWED_HOME_DIRS = {
    'OneDrive - Personal',
    'Dev',
    'Code',
    'Work',
    'Music',
    'Videos',
    'Desktop',
    'OneDrive',
    'Pictures',
    'Projects',
    'Documents',
    'Downloads'}
_WRITE_ALLOWED_HOME_DIRS = {
    'Desktop',
    'Documents',
    'Downloads'}

def _norm(p = None):
    return Path(p).expanduser().resolve()
# WARNING: Decompyle incomplete


def _under(child = None, parent = None):
    child.relative_to(parent)
    return True
# WARNING: Decompyle incomplete


def _lower_posix(p = None):
    return p.as_posix().lower()


def is_blocked(path = None):
    '''Return (blocked, reason) for absolute blocks that apply in every mode.'''
    raw = str(path).strip().replace('/', '\\')
    if raw.startswith('\\\\.\\') or raw.startswith('\\\\?\\'):
        return (True, 'Raw device path')
    p = None(path)
    low = _lower_posix(p)
    windir = os.environ.get('WINDIR', 'C:\\Windows')
    sysroot = _norm(windir)
    if _under(p, sysroot):
        return (True, 'Windows system directory')
    progfiles = [
        None.environ.get('ProgramFiles', 'C:\\Program Files'),
        os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)'),
        os.environ.get('ProgramData', 'C:\\ProgramData')]
    for pf in progfiles:
        if not pf:
            continue
        if _under(p, _norm(pf)):
            return (True, 'Protected program directory')
        rel = p.relative_to(_HOME).as_posix().lower()
# WARNING: Decompyle incomplete


def is_allowed(path = None, mode = None):
    '''Return (allowed, reason_if_not).

    mode: "read" for scans / file reads, "write" for file writes / deletes.
    '''
    if not path:
        return (False, 'Empty path')
    p = None(path)
    (blocked, reason) = is_blocked(p)
    if blocked:
        return (False, reason)
    if None(p, _HOME):
        rel = p.relative_to(_HOME)
        first = rel.parts[0] if rel.parts else ''
# WARNING: Decompyle incomplete


def guard_or_error(path = None, mode = None):
    '''Convenience for tool handlers: return a `{success: False, ...}` dict
    when the path is refused, or None when allowed.'''
    (ok, reason) = is_allowed(path, mode = mode)
    if ok:
        return None
    return {
        'success': None,
        'error': f'''Path blocked by guard: {reason}''',
        'blocked': True,
        'reason': reason }

