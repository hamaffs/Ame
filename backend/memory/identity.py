"""
Layer 1 — Identity store for Amé.
Fast structured facts about the user, stored at ~/.ame/memory/identity.json.
Loaded into every session prompt. Capped at ~500 tokens.
"""

from __future__ import annotations
import json
import threading
from datetime import date
from pathlib import Path

from backend.memory.crypto import encrypt_json, decrypt_json, is_available as _crypto_available


MEMORY_DIR    = Path.home() / ".ame" / "memory"
IDENTITY_FILE = MEMORY_DIR / "identity.json"

CATEGORIES = [
    "identity", "personality", "preferences", "projects", "relationships",
    "digital_life", "health", "finances", "wishes", "active_tasks", "notes",
]

_LEGACY_MAP: dict[str, str] = {}
_lock = threading.Lock()

_NAME_COMMON_WORDS = {
    "hi", "is", "my", "uh", "um", "hey", "the", "cyxa", "like", "name",
    "okay", "test", "user", "yeah", "damen", "hello",
}


def validate_name(name: str) -> bool:
    """Return True only if `name` looks like a real human name."""
    if not isinstance(name, str):
        return False
    n = name.strip()
    if len(n) < 2 or len(n) > 20:
        return False
    if not n.replace("-", "").replace("'", "").replace(" ", "").isalpha():
        return False
    if n.lower() in _NAME_COMMON_WORDS:
        return False
    return True


_is_valid_name = validate_name


def _ensure_dir() -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)


def _default_data() -> dict:
    return {c: {} for c in CATEGORIES}


def load_identity() -> dict:
    """Load the identity store from disk. Transparently decrypts if available."""
    _ensure_dir()
    if not IDENTITY_FILE.exists():
        d = _default_data()
        save_identity(d)
        return d
    try:
        with IDENTITY_FILE.open("r", encoding="utf-8") as f:
            raw = f.read().strip()
        if not raw:
            return _default_data()
        # First try as an envelope, fall back to plain JSON for older files.
        try:
            data = decrypt_json(raw)
        except Exception:
            try:
                data = json.loads(raw)
            except Exception:
                return _default_data()
        if not isinstance(data, dict):
            return _default_data()
        # Ensure all categories present.
        for c in CATEGORIES:
            data.setdefault(c, {})
        return data
    except Exception as e:
        print(f"[memory:identity] load failed: {e}")
        return _default_data()


def save_identity(data: dict) -> None:
    """Save the identity store to disk. Encrypts when crypto is available."""
    _ensure_dir()
    try:
        try:
            payload = encrypt_json(data)
        except Exception:
            # No encryption available — fall back to plaintext (dev mode).
            payload = json.dumps(data, ensure_ascii=False, indent=2)
        tmp = IDENTITY_FILE.with_suffix(IDENTITY_FILE.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            f.write(payload)
        tmp.replace(IDENTITY_FILE)
    except Exception as e:
        print(f"[memory:identity] save failed: {e}")


def update_fact(category: str, key: str, value, source: str = "conversation") -> None:
    """Thread-safe update of a single fact."""
    if category == "identity" and key == "name" and not _is_valid_name(str(value)):
        print(f"[memory:identity] Rejected invalid name: {value!r}")
        return
    if category not in CATEGORIES:
        category = _LEGACY_MAP.get(category, "notes")
    today = date.today().isoformat()
    with _lock:
        data = load_identity()
        data.setdefault(category, {})
        data[category][key] = {"value": str(value), "updated": today, "source": source}
        save_identity(data)


def update_from_patch(data: dict, patch: dict) -> dict:
    """Apply a structured_facts-format patch dict. Returns updated data. Caller must save."""
    if not isinstance(patch, dict):
        return data
    today = date.today().isoformat()
    for cat, keys in patch.items():
        if cat not in CATEGORIES:
            cat = _LEGACY_MAP.get(cat, "notes")
        data.setdefault(cat, {})
        if not isinstance(keys, dict):
            continue
        for k, v in keys.items():
            if cat == "identity" and k == "name":
                val = v.get("value", v) if isinstance(v, dict) else str(v)
                if not _is_valid_name(str(val)):
                    print(f"[memory:identity] Rejected invalid name from patch: {val!r}")
                    continue
            if isinstance(v, dict):
                v.setdefault("source", "conversation")
                v.setdefault("updated", today)
                data[cat][k] = v
            else:
                data[cat][k] = {"value": str(v), "updated": today, "source": "conversation"}
    return data


_MAX_PROMPT_CHARS = 1000


def get_prompt_block(data: dict | None = None) -> str:
    """Return formatted string for injection into system prompt, capped at ~500 tokens."""
    if data is None:
        data = load_identity()
    lines: list[str] = []
    for cat in CATEGORIES:
        keys = data.get(cat, {})
        if not keys:
            continue
        bits: list[str] = []
        for k, v in keys.items():
            if isinstance(v, dict):
                val = v.get("value")
            else:
                val = v
            if val:
                bits.append(f"{k}: {val}")
        if bits:
            lines.append(f"[{cat}] " + "; ".join(bits))
    out = "\n".join(lines)
    if len(out) > _MAX_PROMPT_CHARS:
        out = out[:_MAX_PROMPT_CHARS - 12] + "\n[truncated]"
    return out


def _trim_if_needed(data: dict) -> dict:
    """If the prompt block exceeds the cap, drop oldest entries from low-priority categories."""
    priorities = ["notes", "active_tasks", "wishes", "finances", "health", "digital_life",
                  "relationships", "projects", "preferences", "personality", "identity"]
    while len(get_prompt_block(data)) > _MAX_PROMPT_CHARS:
        for cat in priorities:
            entries = data.get(cat, {})
            if not entries:
                continue
            oldest_key = min(entries.keys(),
                             key=lambda k: (entries[k].get("updated", "") if isinstance(entries[k], dict) else ""))
            del entries[oldest_key]
            break
        else:
            break
    return data


_MAX_ACTIVE_TASKS = 5


def set_active_task(description: str, source: str = "conversation") -> None:
    """Save what the user is currently working on. Keeps the last N tasks."""
    if not description:
        return
    today = date.today().isoformat()
    with _lock:
        data = load_identity()
        tasks = data.setdefault("active_tasks", {})
        # Key by timestamp so newest sorts last.
        from datetime import datetime
        key = datetime.utcnow().isoformat(timespec="seconds")
        tasks[key] = {"value": description, "updated": today, "source": source}
        # Trim to N most recent.
        if len(tasks) > _MAX_ACTIVE_TASKS:
            for k in sorted(tasks.keys())[:-_MAX_ACTIVE_TASKS]:
                del tasks[k]
        save_identity(data)


def get_active_tasks() -> list[str]:
    """Return list of active task descriptions, most recent first."""
    data = load_identity()
    tasks = data.get("active_tasks", {})
    if not tasks:
        return []
    sorted_items = sorted(tasks.items(), key=lambda kv: kv[0], reverse=True)
    return [v.get("value") if isinstance(v, dict) else str(v) for _, v in sorted_items]


def clear_active_tasks() -> None:
    """Clear all active tasks."""
    with _lock:
        data = load_identity()
        data["active_tasks"] = {}
        save_identity(data)


def get_task_prompt_block() -> str:
    """Return a prompt block about what the user was working on last session."""
    tasks = get_active_tasks()
    if not tasks:
        return ""
    lines = ["Last session you were working on:"]
    for t in tasks[:3]:
        lines.append(f"  - {t}")
    lines.append("If appropriate, ask if they want to continue where they left off.")
    return "\n".join(lines)
