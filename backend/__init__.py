"""Backend package — shared helpers.

`get_env_path()` resolves where Amé's wizard-managed `.env` lives:

  - dev (running from source): repo-root .env (unchanged)
  - packaged (PyInstaller frozen): per-user app-data dir, because the
    install location (typically Program Files) isn't writable for a
    non-admin user. This is what the /setup wizard writes to and what
    every module's load_dotenv() reads from.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_env_path() -> Path:
    if _is_frozen():
        if sys.platform == "win32":
            base = os.environ.get("APPDATA")
            if base:
                return Path(base) / "ame" / ".env"
            return Path.home() / "AppData" / "Roaming" / "ame" / ".env"
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "ame" / ".env"
        xdg = os.environ.get("XDG_CONFIG_HOME")
        base = Path(xdg) if xdg else Path.home() / ".config"
        return base / "ame" / ".env"
    # Dev: repo-root .env (parent of the backend/ package)
    return Path(__file__).parent.parent / ".env"


def get_cache_dir() -> Path:
    """Per-user, writable directory for Amé's runtime cache files
    (Spotify token cache, future cache artifacts).

    Same resolution rules as get_env_path() — packaged builds use the
    OS app-data dir, dev runs use the repo root — but returns the
    *directory*, not a specific filename.
    """
    return get_env_path().parent


def load_env() -> None:
    """Load Amé's .env into os.environ from the resolved path. No-op if absent."""
    p = get_env_path()
    if p.exists():
        load_dotenv(dotenv_path=p)
