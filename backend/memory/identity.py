# Source Generated with Decompyle++
# File: identity.pyc (Python 3.11)

'''
Layer 1 ΓÇö Identity store for Am├⌐.
Fast structured facts about the user, stored at ~/.ame/memory/identity.json.
Loaded into every session prompt. Capped at ~500 tokens.
'''
import sys
import os
os.environ.setdefault('PYTHONUTF8', '1')
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding = 'utf-8', errors = 'replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding = 'utf-8', errors = 'replace')
import json
import threading
from datetime import date
from pathlib import Path
from backend.memory.crypto import encrypt_json, decrypt_json, is_available as _crypto_available
MEMORY_DIR = Path.home() / '.ame' / 'memory'
IDENTITY_FILE = MEMORY_DIR / 'identity.json'
CATEGORIES = [
    'identity',
    'personality',
    'preferences',
    'projects',
    'relationships',
    'digital_life',
    'health',
    'finances',
    'wishes',
    'active_tasks',
    'notes']
_LEGACY_MAP = { }
_lock = threading.Lock()
_NAME_COMMON_WORDS = {
    'hi',
    'is',
    'my',
    'uh',
    'um',
    'hey',
    'the',
    'cyxa',
    'like',
    'name',
    'okay',
    'test',
    'user',
    'yeah',
    'damen',
    'hello'}

def validate_name(name = None):
    '''Return True only if name looks like a real human name.'''
    name = name.strip()
    if len(name) < 2 or len(name) > 20:
        return False
    if not None.replace('-', '').replace("'", '').isalpha():
        return False
    if None.lower() in _NAME_COMMON_WORDS:
        return False

_is_valid_name = validate_name

def _ensure_dir():
    MEMORY_DIR.mkdir(parents = True, exist_ok = True)


def load_identity():
    '''Load the identity store from disk. Transparently decrypts if DPAPI is available.
    Returns {category: {key: {value, updated, source}}}.'''
    _ensure_dir()
    if not IDENTITY_FILE.exists():
        default = CATEGORIES()
        save_identity(default)
        return default
# WARNING: Decompyle incomplete


def save_identity(data = None):
    '''Save the identity store to disk. Encrypts with DPAPI when available.'''
    _ensure_dir()
    payload = encrypt_json(data)
# WARNING: Decompyle incomplete


def update_fact(category = None, key = None, value = None, source = ('conversation',)):
    '''Thread-safe update of a single fact.'''
    if not category == 'identity' and key == 'name' and _is_valid_name(value):
        print(f'''[memory:identity] Rejected invalid name: {repr(value)}''')
        return None
    if None not in CATEGORIES:
        category = 'notes'
# WARNING: Decompyle incomplete


def update_from_patch(data = None, patch = None):
    '''Apply a structured_facts-format patch dict. Returns updated data. Caller must save.'''
    today = date.today().isoformat()
    for cat, keys in patch.items():
        if cat not in CATEGORIES:
            cat = _LEGACY_MAP.get(cat, 'notes')
        data.setdefault(cat, { })
        if not isinstance(keys, dict):
            continue
        for k, v in keys.items():
            if cat == 'identity' and k == 'name':
                val = v.get('value', v) if isinstance(v, dict) else str(v)
                if not _is_valid_name(str(val)):
                    print(f'''[memory:identity] Rejected invalid name from patch: {repr(val)}''')
                    continue
            if isinstance(v, dict):
                v.setdefault('source', 'conversation')
                v.setdefault('updated', today)
                data[cat][k] = v
                continue
            data[cat][k] = {
                'value': str(v),
                'updated': today,
                'source': 'conversation' }
            return data

_MAX_PROMPT_CHARS = 1000

def get_prompt_block(data = None):
    '''Return formatted string for injection into system prompt, capped at ~500 tokens.'''
    pass
# WARNING: Decompyle incomplete


def _trim_if_needed(data = None):
    '''If the prompt block exceeds the token cap, trim oldest facts from least important categories.'''
    pass
# WARNING: Decompyle incomplete

_MAX_ACTIVE_TASKS = 5

def set_active_task(description = None, source = None):
    '''Save what the user is currently working on. Keeps the last N tasks.'''
    pass
# WARNING: Decompyle incomplete


def get_active_tasks():
    '''Return list of active task descriptions, most recent first.'''
    data = load_identity()
    tasks = data.get('active_tasks', { })
    if not tasks:
        return []
    sorted_items = None(tasks.items(), key = (lambda kv: kv[0]), reverse = True)
    return sorted_items()


def clear_active_tasks():
    '''Clear all active tasks.'''
    pass
# WARNING: Decompyle incomplete


def get_task_prompt_block():
    '''Return a prompt block about what the user was working on last session.'''
    tasks = get_active_tasks()
    if not tasks:
        return ''
    lines = [
        None]
    for t in tasks[:3]:
        lines.append(f'''  - {t}''')
        lines.append('If appropriate, ask if they want to continue where they left off.')
        return '\n'.join(lines)

