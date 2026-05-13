"""
Layer 2 — Temporal knowledge graph for Amé.
Stores entities, relationships, and facts in SQLite at ~/.ame/memory/graph.db.
"""

from __future__ import annotations
import json
import sqlite3
import threading
from datetime import date, datetime
from pathlib import Path


MEMORY_DIR = Path.home() / ".ame" / "memory"
GRAPH_DB   = MEMORY_DIR / "graph.db"

_lock = threading.Lock()
_local = threading.local()


def _ensure_dir() -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)


def _get_conn() -> sqlite3.Connection:
    """Thread-local SQLite connection."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        _ensure_dir()
        conn = sqlite3.connect(GRAPH_DB, check_same_thread=False, isolation_level=None)
        conn.row_factory = sqlite3.Row
        _init_tables(conn)
        _local.conn = conn
    return conn


def _init_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            attributes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            predicate  TEXT NOT NULL,
            object_id  INTEGER NOT NULL,
            valid_from TEXT,
            valid_until TEXT,
            confidence REAL DEFAULT 1.0,
            source     TEXT,
            FOREIGN KEY (subject_id) REFERENCES entities(id),
            FOREIGN KEY (object_id)  REFERENCES entities(id)
        );

        CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id  INTEGER,
            key        TEXT NOT NULL,
            value      TEXT NOT NULL,
            valid_from TEXT NOT NULL,
            valid_until TEXT,
            source     TEXT,
            FOREIGN KEY (entity_id) REFERENCES entities(id)
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_entity_name_type ON entities(name, type);
    """)
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO entities (name, type, attributes, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        ("User", "person", "{}", now, now),
    )


def add_entity(name: str, type: str = "thing", attributes: dict | None = None) -> int:
    """Add or get an entity. Deduplicates by name+type. Returns entity id."""
    if not name:
        return 0
    conn = _get_conn()
    now = datetime.now().isoformat()
    attrs = json.dumps(attributes or {}, ensure_ascii=False)
    with _lock:
        cur = conn.execute("SELECT id FROM entities WHERE name = ? AND type = ?", (name, type))
        row = cur.fetchone()
        if row:
            conn.execute("UPDATE entities SET updated_at = ? WHERE id = ?", (now, row["id"]))
            return row["id"]
        cur = conn.execute(
            "INSERT INTO entities (name, type, attributes, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (name, type, attrs, now, now),
        )
        return cur.lastrowid


def add_relationship(subject: str, predicate: str, object: str, source: str = "conversation") -> int:
    """Add a relationship between named entities. Creates entities if they don't exist."""
    if not subject or not predicate or not object:
        return 0
    sid = add_entity(subject, "person" if subject == "User" else "thing")
    oid = add_entity(object, "thing")
    today = date.today().isoformat()
    conn = _get_conn()
    with _lock:
        # Don't duplicate active edges.
        cur = conn.execute(
            "SELECT id FROM relationships WHERE subject_id = ? AND predicate = ? AND object_id = ? AND valid_until IS NULL",
            (sid, predicate, oid),
        )
        if cur.fetchone():
            return 0
        cur = conn.execute(
            "INSERT INTO relationships (subject_id, predicate, object_id, valid_from, source) VALUES (?, ?, ?, ?, ?)",
            (sid, predicate, oid, today, source),
        )
        return cur.lastrowid


def invalidate_relationship(subject: str, predicate: str, object: str) -> None:
    """Sets valid_until to today for a relationship."""
    conn = _get_conn()
    today = date.today().isoformat()
    with _lock:
        conn.execute("""
            UPDATE relationships SET valid_until = ?
            WHERE valid_until IS NULL
              AND subject_id = (SELECT id FROM entities WHERE name = ?)
              AND predicate  = ?
              AND object_id  = (SELECT id FROM entities WHERE name = ?)
        """, (today, subject, predicate, object))


def query_entity(name: str) -> dict:
    """Returns entity with all its current relationships and facts."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM entities WHERE name = ?", (name,)).fetchone()
    if not row:
        return {}
    entity_id = row["id"]
    rels = conn.execute("""
        SELECT r.predicate, o.name AS object_name, r.valid_from, r.valid_until
        FROM relationships r JOIN entities o ON r.object_id = o.id
        WHERE r.subject_id = ? AND r.valid_until IS NULL
        ORDER BY r.id DESC
    """, (entity_id,)).fetchall()
    facts = conn.execute("""
        SELECT key, value, valid_from FROM facts
        WHERE entity_id = ? AND valid_until IS NULL
        ORDER BY id DESC
    """, (entity_id,)).fetchall()
    return {
        "id": entity_id,
        "name": row["name"],
        "type": row["type"],
        "attributes": json.loads(row["attributes"] or "{}"),
        "relationships": [dict(r) for r in rels],
        "facts": [dict(f) for f in facts],
    }


def get_user_node() -> dict:
    """Returns everything known about the User entity."""
    return query_entity("User")


def add_fact(entity_name: str, key: str, value: str, source: str = "conversation") -> int:
    """Add a timestamped fact to an entity."""
    if not entity_name or not key:
        return 0
    eid = add_entity(entity_name, "person" if entity_name == "User" else "thing")
    today = date.today().isoformat()
    conn = _get_conn()
    with _lock:
        # Invalidate any previous fact with the same key.
        conn.execute("UPDATE facts SET valid_until = ? WHERE entity_id = ? AND key = ? AND valid_until IS NULL",
                     (today, eid, key))
        cur = conn.execute(
            "INSERT INTO facts (entity_id, key, value, valid_from, source) VALUES (?, ?, ?, ?, ?)",
            (eid, key, str(value), today, source),
        )
        return cur.lastrowid


_MAX_CONTEXT_CHARS  = 500
_CONTEXT_REL_LIMIT  = 10


def get_context_block(query: str | None = None) -> str:
    """Return a compact summary of the most important graph nodes for prompt injection.

    If `query` is provided, edges whose predicate/object literally match a query
    token bubble to the top; otherwise the N most-recent edges are returned.
    """
    try:
        conn = _get_conn()
    except Exception:
        return ""
    rows = conn.execute("""
        SELECT s.name AS subj, r.predicate, o.name AS obj, r.id
        FROM relationships r
        JOIN entities s ON r.subject_id = s.id
        JOIN entities o ON r.object_id  = o.id
        WHERE r.valid_until IS NULL
        ORDER BY r.id DESC
        LIMIT 50
    """).fetchall()
    if not rows:
        return ""

    if query:
        toks = [t for t in (query or "").lower().split() if len(t) > 2]
        def score(r):
            txt = f"{r['predicate']} {r['obj']}".lower()
            return sum(1 for t in toks if t in txt)
        rows = sorted(rows, key=score, reverse=True)

    rows = rows[:_CONTEXT_REL_LIMIT]
    lines = [f"  - {r['subj']} {r['predicate']} {r['obj']}" for r in rows]
    out = "Known facts (graph):\n" + "\n".join(lines)
    return out[:_MAX_CONTEXT_CHARS]


def clear() -> None:
    """Delete all graph data."""
    conn = _get_conn()
    with _lock:
        conn.executescript("""
            DELETE FROM relationships;
            DELETE FROM facts;
            DELETE FROM entities;
        """)
        # Re-seed user node.
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO entities (name, type, attributes, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("User", "person", "{}", now, now),
        )
