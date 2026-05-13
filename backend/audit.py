"""Tool-invocation audit log.

Writes one JSON line per tool call to ~/.ame/security/tool_audit.jsonl
with daily rotation. Sensitive values (API keys, tokens, absolute paths)
are redacted before write.

Consumed by journal.py for "what did you do yesterday?" summaries and
by /diagnostics for live operator view.
"""

from __future__ import annotations
import hashlib
import json
import os
import re
import threading
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator


_AUDIT_DIR = Path.home() / ".ame" / "security"
_AUDIT_DIR.mkdir(parents=True, exist_ok=True)
_lock = threading.Lock()

_KEY_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"gho_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9_\-\.=]{20,}", re.IGNORECASE),
    re.compile(r"\b[A-Fa-f0-9]{32,}\b"),
]
_ABS_PATH_PATTERN = re.compile(r"([A-Za-z]:[\\/][^\s\"'<>|?*]+|/[^\s\"'<>|?*]+)")


def _hash_tail(s: str, n: int = 8) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()[:n]


def _redact_string(s: str) -> str:
    if not s:
        return s
    for pat in _KEY_PATTERNS:
        s = pat.sub(lambda m: f"[REDACTED_KEY:{_hash_tail(m.group(0))}]", s)

    def _path_sub(m: re.Match) -> str:
        raw = m.group(0)
        if len(raw) < 8:
            return raw
        parent = os.path.dirname(raw)
        leaf   = os.path.basename(raw) or raw
        parent_tail = _hash_tail(parent) if parent else ""
        return f"[PATH:{parent_tail}]/{leaf}"

    return _ABS_PATH_PATTERN.sub(_path_sub, s)


def _redact(value):
    if isinstance(value, str):
        return _redact_string(value)
    if isinstance(value, dict):
        return {k: _redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def _path_for_today() -> Path:
    """Today's audit file. Filename carries the ISO date so each day gets its
    own file and the directory self-rotates."""
    today = date.today().isoformat()
    return _AUDIT_DIR / f"tool_audit_{today}.jsonl"


def _legacy_path() -> Path:
    """Pre-rotation filename. Still read on iter_records for back-compat."""
    return _AUDIT_DIR / "tool_audit.jsonl"


def _dated_log_files() -> list[Path]:
    """All rotated audit files, oldest first."""
    files: list[Path] = []
    legacy = _legacy_path()
    if legacy.exists():
        files.append(legacy)
    dated = sorted(_AUDIT_DIR.glob("tool_audit_*.jsonl"))
    files.extend(dated)
    return files


def log_tool(name: str,
             args: dict | None = None,
             level: str = "low",
             outcome: str = "ok",
             duration_ms: float = 0.0,
             turn_id: str | None = None,
             extra: dict | None = None) -> None:
    """Append a single audit record. Never raises."""
    try:
        record: dict = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "tool": name,
            "level": level,
            "outcome": outcome,
            "duration_ms": round(float(duration_ms or 0), 1),
            "args": _redact(args or {}),
        }
        if turn_id:
            record["turn"] = turn_id
        if extra:
            record["extra"] = _redact(extra)
        line = json.dumps(record, ensure_ascii=False) + "\n"
        path = _path_for_today()
        with _lock:
            with path.open("a", encoding="utf-8") as f:
                f.write(line)
    except Exception:
        # Never let auditing crash the tool path.
        pass


def iter_records(since_iso: str | None = None) -> Iterator[dict]:
    """Yield audit records across all rotated daily files, oldest first.
    Optionally filter by ts >= since_iso."""
    for path in _dated_log_files():
        try:
            with path.open("r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    if since_iso and rec.get("ts", "") < since_iso:
                        continue
                    yield rec
        except FileNotFoundError:
            continue


def tail_records(limit: int = 50) -> list[dict]:
    """Up to `limit` most recent records, newest-first."""
    if limit <= 0:
        return []
    collected: list[dict] = []
    for path in reversed(_dated_log_files()):
        try:
            with path.open("r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except FileNotFoundError:
            continue
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                collected.append(json.loads(line))
            except Exception:
                continue
            if len(collected) >= limit:
                return collected
    return collected
