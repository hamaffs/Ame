# Source Generated with Decompyle++
# File: episodic.pyc (Python 3.11)

'''
Layer 3 ΓÇö Episodic memory for Am├⌐.
Verbatim conversation history stored in SQLite FTS5 at ~/.ame/memory/episodic.db.
BM25 full-text search over past conversations.

Previously used ChromaDB. Rewritten on top of stdlib sqlite3 + FTS5 to:
  - drop the embedding model (~200-400MB RAM, ~90MB disk) required by default
    Chroma ΓÇö Am├⌐ runs on user laptops, most of which are low-spec.
  - remove CPU inference cost per stored turn (embedding computation).
  - keep install size + startup time small.

Public API (unchanged): store_turn, search, search_relevant, get_recent, clear.
Return shape of search() items is the same: {"text", "timestamp", "distance"}.
'''
import sys
import os
os.environ.setdefault('PYTHONUTF8', '1')
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding = 'utf-8', errors = 'replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding = 'utf-8', errors = 'replace')
import re
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
MEMORY_DIR = Path.home() / '.ame' / 'memory'
EPISODIC_DB = MEMORY_DIR / 'episodic.db'
_lock = threading.Lock()
_local = threading.local()
_fts_available: bool | None = None

def _ensure_dir():
    MEMORY_DIR.mkdir(parents = True, exist_ok = True)


def _probe_fts5(conn = None):
    '''Return True if this sqlite3 build supports FTS5.'''
    conn.execute('CREATE VIRTUAL TABLE IF NOT EXISTS _fts5_probe USING fts5(x)')
    conn.execute('DROP TABLE IF EXISTS _fts5_probe')
    return True
# WARNING: Decompyle incomplete


def _get_conn():
    '''Thread-local SQLite connection. Returns None if FTS5 unavailable.'''
    pass
# WARNING: Decompyle incomplete

_OLD_CHROMA_DIR = MEMORY_DIR / 'episodic'
_MIGRATION_FLAG = MEMORY_DIR / '.chroma_migrated'

def _maybe_migrate_from_chroma(conn = None):
    '''One-shot migration from the old ChromaDB store if present. No-op otherwise.
    Keeps user history when upgrading past the rewrite.'''
    if not _MIGRATION_FLAG.exists() or _OLD_CHROMA_DIR.exists():
        return None
    import chromadb
# WARNING: Decompyle incomplete


def _init_tables(conn = None):
    conn.executescript("\n        CREATE TABLE IF NOT EXISTS turns (\n            id         INTEGER PRIMARY KEY AUTOINCREMENT,\n            turn_id    TEXT NOT NULL UNIQUE,\n            user_text  TEXT NOT NULL,\n            ame_text   TEXT NOT NULL,\n            timestamp  TEXT NOT NULL\n        );\n\n        CREATE VIRTUAL TABLE IF NOT EXISTS turns_fts USING fts5(\n            user_text,\n            ame_text,\n            content='turns',\n            content_rowid='id',\n            tokenize='porter unicode61'\n        );\n\n        CREATE TRIGGER IF NOT EXISTS turns_ai AFTER INSERT ON turns BEGIN\n            INSERT INTO turns_fts(rowid, user_text, ame_text)\n            VALUES (new.id, new.user_text, new.ame_text);\n        END;\n\n        CREATE TRIGGER IF NOT EXISTS turns_ad AFTER DELETE ON turns BEGIN\n            INSERT INTO turns_fts(turns_fts, rowid, user_text, ame_text)\n            VALUES('delete', old.id, old.user_text, old.ame_text);\n        END;\n\n        CREATE INDEX IF NOT EXISTS idx_turns_timestamp ON turns(timestamp DESC);\n    ")
    conn.commit()

_FTS_TOKEN_RE = re.compile('[A-Za-z0-9_├Ç-∩┐┐]+')

def _to_fts_query(text = None):
