# Source Generated with Decompyle++
# File: __init__.pyc (Python 3.11)

'''
Am├⌐ Memory Package ΓÇö Three-layer memory system.
Layer 1: Identity (structured facts)
Layer 2: Graph (temporal knowledge graph)
Layer 3: Episodic (conversation history with semantic search)

This __init__.py exposes the exact function signatures that
live_session.py and server.py expect. Do not change these signatures.
'''
import sys
import os
os.environ.setdefault('PYTHONUTF8', '1')
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding = 'utf-8', errors = 'replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding = 'utf-8', errors = 'replace')
import threading
from backend.memory.core import AmeMemory
_instance: AmeMemory = None
_lock = threading.Lock()

def _get_instance():
    pass
# WARNING: Decompyle incomplete


def load_memory():
    '''Returns the AmeMemory instance (has .get_memory_context_string()).'''
    return _get_instance()


def _get_memory():
    '''Returns the AmeMemory instance. Used internally.'''
    return _get_instance()


def update_structured_memory(category = None, key = None, value = None):
    '''Update a single structured fact in Layer 1.'''
    _get_instance().update_structured(category, key, value)


def update_memory(patch = None):
    '''Merge a partial structured_facts patch into Layer 1.'''
    _get_instance().update_from_patch(patch)


def maybe_extract_memory_bg(user_text = None, assistant_text = None):
    '''Background memory extraction after each turn. Non-blocking.

    Handles everything: episodic storage (every turn, local),
    plus combined facts/graph/personality extraction (every 3rd turn, 1 API call).
    '''
    threading.Thread(target = _get_instance().extract_and_store, args = (user_text, assistant_text), daemon = True, name = 'mem-extract').start()


def clear_memory():
    '''Clear all three memory layers.'''
    _get_instance().clear_all()

