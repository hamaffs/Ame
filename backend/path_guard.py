"""Filesystem allowlist / blocklist for scan and read operations.

Goal: prevent Amé from wandering into places she has no business scanning
(System32, credentials, browser cookies, .ssh/.aws/.azure/.gcloud), while
still letting her help with Desktop, Documents, Downloads, and project dirs
the user configures.

Cross-platform: the blocklist branches on `sys.platform`. The user's home
directory is always allowed for *read* in the curated subdirs below, and
for *write* in the narrower writable set.

Tools that accept a user-supplied path should call `is_allowed(path, mode)`
at the top and bail out with a friendly refusal on False.
"""

from __future__ import annotations
import os
import sys
from pathlib import Path
from typing import Iterable

_HOME = Path.home().resolve()


# ── Blocklists ─────────────────────────────────────────────────────────────
# Paths that are always off-limits regardless of mode. The lists below are
# substrings tested against the *posix-lower* path (so "C:\Windows\..." and
# "/windows/..." both match).

_BLOCKED_SUBPATHS_COMMON: tuple[str, ...] = (
    ".ssh",
    ".gnupg",
    ".aws",
    ".gcloud",
    ".azure",
    ".config/gcloud",
    ".config/google-chrome",
    ".config/chromium",
    ".mozilla/firefox",
    "library/keychains",
    "appdata/local/google/chrome/user data",
    "appdata/local/microsoft/edge/user data",
    "appdata/roaming/mozilla/firefox",
    "appdata/roaming/microsoft/credentials",
    "appdata/roaming/microsoft/protect",
    "appdata/local/microsoft/credentials",
    "appdata/local/microsoft/vault",
)
_BLOCKED_SUBPATHS_LINUX: tuple[str, ...] = (
    "/etc",
    "/root",
    "/var",
    "/proc",
    "/sys",
    "/dev",
    "/boot",
    "/run",
    "/usr/sbin",
)
_BLOCKED_SUBPATHS_WINDOWS: tuple[str, ...] = (
    "windows",
    "windows/system32",
    "windows/syswow64",
    "program files",
    "program files (x86)",
    "programdata",
)
_BLOCKED_SUBPATHS_DARWIN: tuple[str, ...] = (
    "/system/library",
    "/private",
)

# ── Allow-lists under $HOME ────────────────────────────────────────────────

_READ_ALLOWED_HOME_DIRS = {
    "Desktop", "Documents", "Downloads", "Pictures", "Music", "Videos",
    "Projects", "Code", "Dev", "Work",
    "OneDrive", "OneDrive - Personal",
}
_WRITE_ALLOWED_HOME_DIRS = {
    "Desktop", "Documents", "Downloads",
}


# ── Internals ──────────────────────────────────────────────────────────────

def _norm(p: str | os.PathLike) -> Path:
    return Path(p).expanduser().resolve()


def _lower_posix(p: Path) -> str:
    return p.as_posix().lower()


def _under(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _platform_blocked_subpaths() -> tuple[str, ...]:
    if sys.platform == "win32":
        return _BLOCKED_SUBPATHS_COMMON + _BLOCKED_SUBPATHS_WINDOWS
    if sys.platform == "darwin":
        return _BLOCKED_SUBPATHS_COMMON + _BLOCKED_SUBPATHS_DARWIN
    return _BLOCKED_SUBPATHS_COMMON + _BLOCKED_SUBPATHS_LINUX


# ── Public API ─────────────────────────────────────────────────────────────

def is_blocked(path) -> tuple[bool, str]:
    """Return (blocked, reason) for absolute blocks that apply in every mode."""
    raw = str(path).strip()
    if raw.startswith("\\\\.\\") or raw.startswith("\\\\?\\"):
        return True, "Raw device path"

    try:
        p = _norm(path)
    except Exception as e:
        return True, f"Unresolvable path: {e}"

    low = _lower_posix(p)

    # System dirs from platform env vars (Windows).
    if sys.platform == "win32":
        for env_var, label in (
            ("WINDIR", "Windows system directory"),
            ("ProgramFiles", "Protected program directory"),
            ("ProgramFiles(x86)", "Protected program directory"),
            ("ProgramData", "Protected program directory"),
        ):
            base = os.environ.get(env_var, "")
            if base:
                try:
                    if _under(p, _norm(base)):
                        return True, label
                except Exception:
                    pass

    for needle in _platform_blocked_subpaths():
        if needle and needle in low:
            return True, f"Blocked path segment: {needle}"

    return False, ""


def is_allowed(path, mode: str = "read") -> tuple[bool, str]:
    """Return (allowed, reason_if_not).

    mode: "read" for scans / file reads, "write" for file writes / deletes.
    """
    if not path:
        return False, "Empty path"
    try:
        p = _norm(path)
    except Exception as e:
        return False, f"Unresolvable path: {e}"

    blocked, reason = is_blocked(p)
    if blocked:
        return False, reason

    # Under $HOME: validate against the curated read/write subdir set.
    if _under(p, _HOME):
        try:
            rel = p.relative_to(_HOME)
        except ValueError:
            return False, "Outside home"
        first = rel.parts[0] if rel.parts else ""
        if not first:
            # The home dir itself
            return (mode == "read"), "Home root is read-only"
        if mode == "write":
            if first in _WRITE_ALLOWED_HOME_DIRS:
                return True, ""
            return False, f"Writing under ~/{first} is not allowed"
        # read
        if first in _READ_ALLOWED_HOME_DIRS or first.startswith("."):
            # dotfiles already filtered by is_blocked for credentials dirs
            return True, ""
        # Allow read of any visible top-level home dir not already blocked.
        if not first.startswith("."):
            return True, ""
        return False, f"Reading under ~/{first} is not allowed"

    # Outside $HOME: allow common removable / mount points on POSIX, deny others.
    if sys.platform != "win32":
        for mount in ("/media", "/mnt", "/run/media"):
            try:
                if _under(p, Path(mount)):
                    return True, ""
            except Exception:
                continue
        return False, "Path is outside the home directory"
    # Windows: allow other drive roots not already blocked.
    drive = p.drive
    if drive and drive.upper() != "C:":
        return True, ""
    return False, "Path is outside the home directory"


def guard_or_error(path, mode: str = "read") -> dict | None:
    """Convenience for tool handlers: return a `{success: False, ...}` dict
    when the path is refused, or None when allowed."""
    ok, reason = is_allowed(path, mode=mode)
    if ok:
        return None
    return {
        "success": False,
        "error": f"Path blocked by guard: {reason}",
        "blocked": True,
        "reason": reason,
    }
