"""Cheap signal extractors for the proactive observation gate.

Pure local code — no model calls, no network. The context engine collects
these every ~10s and feeds them to a tiny local-Gemma classifier that
decides SPEAK / WATCH / IGNORE. Keeping signal extraction fast and cost-free
is what lets the proactive loop run often enough to feel alive without
burning tokens or CPU.
"""

from __future__ import annotations
import re
import time
from dataclasses import dataclass, field

_CATEGORY_PATTERNS: "list[tuple[str, tuple[str, ...]]]" = [
    ("editor",   ("visual studio code", "vscode", " - code", "intellij", "pycharm", "webstorm",
                  "rider", "clion", "android studio", "sublime text", "notepad++", "neovim",
                  "vim", "emacs", "cursor", "zed", "xcode", "rstudio", "spyder", "jupyter")),
    ("terminal", ("powershell", "command prompt", "cmd.exe", "windows terminal", "bash", "zsh",
                  "wsl", "git bash", "conemu", "alacritty", "tabby", "hyper", "gnome-terminal",
                  "konsole", "xterm", "kitty", "wezterm", "terminator")),
    ("browser",  ("chrome", "firefox", "edge", "brave", "opera", "vivaldi", "safari", "arc",
                  "tor browser", "chromium")),
    ("chat",     ("discord", "slack", "microsoft teams", "telegram", "whatsapp", "signal",
                  "messenger", "zoom", "google meet")),
    ("media",    ("youtube", "spotify", "netflix", "vlc", "media player", "twitch", "obs",
                  "premiere pro", "after effects", "davinci resolve", "audacity", "mpv")),
    ("creative", ("photoshop", "illustrator", "figma", "blender", "touchdesigner", "fl studio",
                  "ableton", "logic pro", "krita", "gimp", "procreate", "sketch", "inkscape")),
    ("game",     ("steam", "epic games", "minecraft", "league of legends", "valorant", "fortnite",
                  "counter-strike", "dota", "overwatch", "lutris")),
    ("system",   ("settings", "control panel", "task manager", "file explorer", "system32",
                  "cmd ", "nautilus", "dolphin", "gnome-control-center")),
]


@dataclass
class WindowSignal:
    """Cheap snapshot of the active window for the observation classifier."""
    title: str = ""
    process: str = ""
    category: str = "unknown"
    ts: float = field(default_factory=time.time)


def classify_title(title: str) -> str:
    """Bucket the window's title into one of the categories above. Defaults to 'unknown'."""
    if not title:
        return "unknown"
    low = title.lower()
    for cat, needles in _CATEGORY_PATTERNS:
        for n in needles:
            if n in low:
                return cat
    return "unknown"


def signal_from_active_window(title: str, process: str = "") -> WindowSignal:
    return WindowSignal(
        title=title or "",
        process=process or "",
        category=classify_title(title or process),
    )
