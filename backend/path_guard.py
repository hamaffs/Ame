"""Filesystem allowlist / blocklist for scan and read operations — Linux edition.

Goal: prevent Amé from wandering into places she has no business scanning
(system dirs, credentials, browser cookies, .ssh/.aws/.azure/.gcloud), while
still letting her help with Desktop, Documents, Downloads, and project dirs
the user configures.

Tools that accept a user-supplied path should call `is_allowed(path, mode)`
at the top and bail out with a friendly refusal on False.
"""

from __future__ import annotations
import os
from pathlib import Path


_HOME = Path.home().resolve()


# ── Blocklists ─────────────────────────────────────────────────────────────
# Substring tests against the *posix-lower* form of the resolved path.

_BLOCKED_SUBPATHS: tuple[str, ...] = (
    # Browser / OS credential stores
    "/.ssh",
    "/.gnupg",
    "/.aws",
    "/.gcloud",
    "/.azure",
    "/.config/gcloud",
    "/.config/google-chrome",
    "/.config/chromium",
    "/.mozilla/firefox",
    "/.thunderbird",
    "/.local/share/keyrings",
    # System dirs
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

# ── Allow-lists under $HOME ────────────────────────────────────────────────

_READ_ALLOWED_HOME_DIRS = {
    "Desktop", "Documents", "Downloads", "Pictures", "Music", "Videos",
    "Projects", "Code", "Dev", "Work",
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


# ── Public API ─────────────────────────────────────────────────────────────

def is_blocked(path) -> tuple[bool, str]:
    """Return (blocked, reason) for absolute blocks that apply in every mode."""
    try:
        p = _norm(path)
    except Exception as e:
        return True, f"Unresolvable path: {e}"

    low = _lower_posix(p)
    for needle in _BLOCKED_SUBPATHS:
        if needle in low:
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

    # Inside $HOME: validate against the curated read/write subdir set.
    if _under(p, _HOME):
        try:
            rel = p.relative_to(_HOME)
        except ValueError:
            return False, "Outside home"
        first = rel.parts[0] if rel.parts else ""
        if not first:
            # The home dir itself.
            return (mode == "read"), "Home root is read-only"
        if mode == "write":
            if first in _WRITE_ALLOWED_HOME_DIRS:
                return True, ""
            return False, f"Writing under ~/{first} is not allowed"
        # read
        if first in _READ_ALLOWED_HOME_DIRS:
            return True, ""
        # Allow any non-hidden top-level home dir (already blocked credentials
        # are filtered above via is_blocked).
        if not first.startswith("."):
            return True, ""
        return False, f"Reading under ~/{first} is not allowed"

    # Outside $HOME: allow removable / mount points only.
    for mount in ("/media", "/mnt", "/run/media"):
        try:
            if _under(p, Path(mount)):
                return True, ""
        except Exception:
            continue
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
