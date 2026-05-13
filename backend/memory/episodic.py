"""
Layer 3 — Episodic memory for Amé.
Verbatim conversation history stored in SQLite FTS5 at ~/.ame/memory/episodic.db.
BM25 full-text search over past conversations.

Public API: store_turn, search, search_relevant, get_recent, clear.
Return shape of search() items: {"text", "timestamp", "distance"}.
"""

from __future__ import annotations
import re
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path


MEMORY_DIR  = Path.home() / ".ame" / "memory"
EPISODIC_DB = MEMORY_DIR / "episodic.db"

_lock = threading.Lock()
_local = threading.local()
_fts_available: bool | None = None


def _ensure_dir() -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)


def _probe_fts5(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _fts5_probe USING fts5(x)")
        conn.execute("DROP TABLE IF EXISTS _fts5_probe")
        return True
    except sqlite3.OperationalError:
        return False


def _get_conn() -> sqlite3.Connection | None:
    """Thread-local SQLite connection. Returns None if FTS5 unavailable."""
    conn = getattr(_local, "conn", None)
    if conn is not None:
        return conn

    global _fts_available
    _ensure_dir()
    try:
        conn = sqlite3.connect(EPISODIC_DB, check_same_thread=False, isolation_level=None)
        conn.row_factory = sqlite3.Row
    except Exception as e:
        print(f"[memory:episodic] open db failed: {e}")
        return None

    if _fts_available is None:
        _fts_available = _probe_fts5(conn)
        if not _fts_available:
            print("[memory:episodic] FTS5 not available — episodic search disabled")
            try: conn.close()
            except Exception: pass
            return None

    _init_tables(conn)
    _local.conn = conn
    return conn


def _init_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS turns (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            turn_id    TEXT NOT NULL UNIQUE,
            user_text  TEXT NOT NULL,
            ame_text   TEXT NOT NULL,
            timestamp  TEXT NOT NULL
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS turns_fts USING fts5(
            user_text,
            ame_text,
            content='turns',
            content_rowid='id',
            tokenize='porter unicode61'
        );

        CREATE TRIGGER IF NOT EXISTS turns_ai AFTER INSERT ON turns BEGIN
            INSERT INTO turns_fts(rowid, user_text, ame_text)
            VALUES (new.id, new.user_text, new.ame_text);
        END;

        CREATE TRIGGER IF NOT EXISTS turns_ad AFTER DELETE ON turns BEGIN
            INSERT INTO turns_fts(turns_fts, rowid, user_text, ame_text)
            VALUES('delete', old.id, old.user_text, old.ame_text);
        END;

        CREATE INDEX IF NOT EXISTS idx_turns_timestamp ON turns(timestamp DESC);
    """)


_FTS_TOKEN_RE = re.compile(r"[A-Za-z0-9_À-￿]+")


def _to_fts_query(text: str) -> str:
    """Build a safe MATCH expression — tokenize, drop short tokens, AND them."""
    toks = [t for t in _FTS_TOKEN_RE.findall(text or "") if len(t) >= 3]
    if not toks:
        return ""
    return " AND ".join(toks[:6])


def store_turn(user_text: str, ame_text: str) -> str | None:
    """Persist one turn. Returns the turn_id, or None on failure."""
    conn = _get_conn()
    if conn is None or not (user_text or ame_text):
        return None
    tid = uuid.uuid4().hex
    ts = datetime.utcnow().isoformat(timespec="seconds")
    try:
        with _lock:
            conn.execute(
                "INSERT INTO turns (turn_id, user_text, ame_text, timestamp) VALUES (?, ?, ?, ?)",
                (tid, str(user_text or ""), str(ame_text or ""), ts),
            )
        return tid
    except Exception as e:
        print(f"[memory:episodic] store_turn failed: {e}")
        return None


def search(query: str, limit: int = 5) -> list[dict]:
    """Full-text search over past turns. Returns up to `limit` items."""
    conn = _get_conn()
    if conn is None:
        return []
    expr = _to_fts_query(query)
    if not expr:
        return []
    try:
        rows = conn.execute("""
            SELECT t.user_text, t.ame_text, t.timestamp, bm25(turns_fts) AS distance
            FROM turns_fts JOIN turns t ON turns_fts.rowid = t.id
            WHERE turns_fts MATCH ?
            ORDER BY distance ASC
            LIMIT ?
        """, (expr, limit)).fetchall()
    except sqlite3.OperationalError as e:
        # Malformed query is the most common cause — return empty quietly.
        print(f"[memory:episodic] search failed: {e}")
        return []
    items = []
    for r in rows:
        items.append({
            "text": f"User: {r['user_text']}\nAmé: {r['ame_text']}",
            "timestamp": r["timestamp"],
            "distance": float(r["distance"]),
        })
    return items


def search_relevant(query: str) -> str:
    """Search and return a formatted block for prompt injection (or empty)."""
    items = search(query, limit=3)
    if not items:
        return ""
    parts = ["Relevant past exchanges:"]
    for it in items:
        parts.append(f"[{it['timestamp']}] {it['text']}")
    return "\n".join(parts)


def get_recent(limit: int = 5) -> list[dict]:
    """Return the most recent turns, newest first."""
    conn = _get_conn()
    if conn is None:
        return []
    rows = conn.execute(
        "SELECT user_text, ame_text, timestamp FROM turns ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [
        {"text": f"User: {r['user_text']}\nAmé: {r['ame_text']}",
         "timestamp": r["timestamp"], "distance": 0.0}
        for r in rows
    ]


def clear() -> None:
    """Wipe episodic memory."""
    conn = _get_conn()
    if conn is None:
        return
    with _lock:
        try:
            conn.executescript("DELETE FROM turns; INSERT INTO turns_fts(turns_fts) VALUES('rebuild');")
        except Exception:
            conn.execute("DELETE FROM turns")
