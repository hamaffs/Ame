"""
Amé Smart File Agent — disk usage, large files, duplicates, temp cleanup.

All destructive operations (cleanup) return a preview first.
Actual deletion only happens via cleanup_temp_execute after user confirmation.
"""

from __future__ import annotations
import hashlib
import os
import shutil
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from backend import path_guard


def _human_size(nbytes: float) -> str:
    """Convert bytes to human-readable string."""
    n = float(nbytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def disk_usage_report(path: str | None = None) -> dict:
    """Report disk usage for a directory or the user's home by default."""
    target = Path(path).expanduser().resolve() if path else Path.home()
    if not target.is_dir():
        return {"success": False, "error": f"Not a directory: {target}"}
    blocked = path_guard.guard_or_error(target, mode="read")
    if blocked is not None:
        return blocked

    try:
        usage = shutil.disk_usage(target)
    except Exception as e:
        return {"success": False, "error": f"disk_usage failed: {e}"}

    top_dirs: list[dict] = []
    try:
        for child in target.iterdir():
            if not child.is_dir():
                continue
            total = 0
            try:
                for root, _dirs, files in os.walk(child, onerror=lambda _e: None):
                    for f in files:
                        try:
                            total += os.path.getsize(os.path.join(root, f))
                        except OSError:
                            continue
            except Exception:
                continue
            top_dirs.append({"path": str(child), "size": total, "human": _human_size(total)})
    except Exception as e:
        return {"success": False, "error": f"directory scan failed: {e}"}

    top_dirs.sort(key=lambda d: d["size"], reverse=True)
    return {
        "success": True,
        "target": str(target),
        "total":  {"bytes": usage.total, "human": _human_size(usage.total)},
        "used":   {"bytes": usage.used,  "human": _human_size(usage.used)},
        "free":   {"bytes": usage.free,  "human": _human_size(usage.free)},
        "top_dirs": top_dirs[:10],
    }


def find_large_files(path: str, min_mb: int = 100, limit: int = 25) -> dict:
    """Find the largest files in a directory tree."""
    target = Path(path).expanduser().resolve()
    if not target.is_dir():
        return {"success": False, "error": f"Not a directory: {target}"}
    blocked = path_guard.guard_or_error(target, mode="read")
    if blocked is not None:
        return blocked

    threshold = int(min_mb) * 1024 * 1024
    found: list[dict] = []
    try:
        for root, _dirs, files in os.walk(target, onerror=lambda _e: None):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    sz = os.path.getsize(fp)
                except OSError:
                    continue
                if sz >= threshold:
                    found.append({"path": fp, "size": sz, "human": _human_size(sz)})
    except Exception as e:
        return {"success": False, "error": f"walk failed: {e}"}

    found.sort(key=lambda d: d["size"], reverse=True)
    return {"success": True, "min_mb": min_mb, "files": found[:limit]}


def find_duplicates(path: str, limit: int = 25) -> dict:
    """Find duplicate files by content hash in a directory tree."""
    target = Path(path).expanduser().resolve()
    if not target.is_dir():
        return {"success": False, "error": f"Not a directory: {target}"}
    blocked = path_guard.guard_or_error(target, mode="read")
    if blocked is not None:
        return blocked

    # Two-pass: bucket by size first, then hash only same-size candidates.
    by_size: dict[int, list[str]] = defaultdict(list)
    for root, _dirs, files in os.walk(target, onerror=lambda _e: None):
        for f in files:
            fp = os.path.join(root, f)
            try:
                sz = os.path.getsize(fp)
            except OSError:
                continue
            if sz > 0:
                by_size[sz].append(fp)

    groups: list[dict] = []
    for sz, paths in by_size.items():
        if len(paths) < 2:
            continue
        by_hash: dict[str, list[str]] = defaultdict(list)
        for p in paths:
            try:
                h = hashlib.sha1()
                with open(p, "rb") as f:
                    for chunk in iter(lambda: f.read(1 << 20), b""):
                        h.update(chunk)
                by_hash[h.hexdigest()].append(p)
            except OSError:
                continue
        for digest, dupes in by_hash.items():
            if len(dupes) >= 2:
                groups.append({"hash": digest, "size": sz, "human": _human_size(sz), "files": dupes})

    groups.sort(key=lambda d: d["size"] * (len(d["files"]) - 1), reverse=True)
    return {"success": True, "groups": groups[:limit]}


# ── Temp cleanup ───────────────────────────────────────────────────────────

def _candidate_temp_dirs() -> list[Path]:
    dirs = [Path(tempfile.gettempdir())]
    home = Path.home()
    if sys.platform == "win32":
        local = home / "AppData" / "Local"
        dirs += [local / "Temp", local / "Microsoft" / "Windows" / "INetCache"]
    else:
        dirs += [home / ".cache"]
    return [d for d in dirs if d.is_dir()]


def cleanup_temp_preview() -> dict:
    """Preview temp files that could be cleaned up. Does NOT delete anything."""
    total_bytes = 0
    target_count = 0
    for d in _candidate_temp_dirs():
        try:
            for entry in d.iterdir():
                try:
                    if entry.is_file():
                        total_bytes += entry.stat().st_size
                        target_count += 1
                    elif entry.is_dir():
                        for root, _ds, files in os.walk(entry, onerror=lambda _e: None):
                            for f in files:
                                try:
                                    total_bytes += os.path.getsize(os.path.join(root, f))
                                    target_count += 1
                                except OSError:
                                    continue
                except OSError:
                    continue
        except OSError:
            continue
    return {
        "success": True,
        "preview": True,
        "candidate_dirs": [str(d) for d in _candidate_temp_dirs()],
        "files": target_count,
        "total_bytes": total_bytes,
        "human": _human_size(total_bytes),
    }


def cleanup_temp_execute() -> dict:
    """Actually delete temp files. Only call after user confirms the preview."""
    deleted = 0
    freed = 0
    errors = 0
    for d in _candidate_temp_dirs():
        try:
            for entry in d.iterdir():
                try:
                    if entry.is_file():
                        sz = entry.stat().st_size
                        entry.unlink(missing_ok=True)
                        deleted += 1
                        freed += sz
                    elif entry.is_dir():
                        for root, _ds, files in os.walk(entry, onerror=lambda _e: None):
                            for f in files:
                                fp = os.path.join(root, f)
                                try:
                                    sz = os.path.getsize(fp)
                                    os.remove(fp)
                                    deleted += 1
                                    freed += sz
                                except OSError:
                                    errors += 1
                except OSError:
                    errors += 1
        except OSError:
            errors += 1
    return {
        "success": True,
        "deleted_files": deleted,
        "bytes_freed": freed,
        "human": _human_size(freed),
        "errors": errors,
    }
