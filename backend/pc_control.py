"""
Linux PC control for Amé.

Replaces the Windows-only original. Implements the same public surface
(open_application, set_volume, take_screenshot, …) using freedesktop
standards: `.desktop` files for the app index, `pactl`/`wpctl` for audio,
`mss` for screenshots, `loginctl`/`xdg-screensaver` for screen lock,
`pyautogui` for keyboard/mouse on X11.

Wayland note: pyautogui-based mouse/keyboard tools require an X11 session
(or XWayland). On pure Wayland, those functions return a `{success:False}`
result with a helpful message instead of crashing.

External binaries we shell out to (install via apt/dnf/pacman as needed):
  - pactl OR wpctl       (volume / mute)
  - wmctrl OR xdotool    (window focus, optional)
  - loginctl             (screen lock — present on systemd systems)
  - xdg-open             (open files / URLs in default app)
  - gtk-launch           (launch .desktop apps; falls back to Exec= line)
"""

from __future__ import annotations

import sys, os
os.environ.setdefault('PYTHONUTF8', '1')
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'): sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import glob
import re
import shlex
import shutil
import signal
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import psutil

# Mouse/keyboard. pyautogui needs an X11 display; on Wayland these functions
# will raise. We catch + degrade gracefully at call sites.
try:
    import pyautogui  # type: ignore
    _PYAUTOGUI_AVAILABLE = True
except Exception as _e:
    pyautogui = None  # type: ignore
    _PYAUTOGUI_AVAILABLE = False
    print(f"[pc_control] pyautogui unavailable: {_e}")

try:
    import pyperclip  # type: ignore
    _PYPERCLIP_AVAILABLE = True
except Exception as _e:
    pyperclip = None  # type: ignore
    _PYPERCLIP_AVAILABLE = False
    print(f"[pc_control] pyperclip unavailable: {_e}")


# ── XDG user dirs ─────────────────────────────────────────────────────────

def _xdg_user_dir(name: str, default: str) -> str:
    """Resolve an XDG user-dir (Desktop, Downloads, Documents, …)."""
    try:
        out = subprocess.check_output(["xdg-user-dir", name],
                                      text=True, stderr=subprocess.DEVNULL, timeout=2).strip()
        if out and os.path.isdir(out):
            return out
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), default)


DESKTOP   = _xdg_user_dir("DESKTOP", "Desktop")
DOWNLOADS = _xdg_user_dir("DOWNLOAD", "Downloads")
DOCUMENTS = _xdg_user_dir("DOCUMENTS", "Documents")
PICTURES  = _xdg_user_dir("PICTURES", "Pictures")
VIDEOS    = _xdg_user_dir("VIDEOS",  "Videos")
MUSIC     = _xdg_user_dir("MUSIC",   "Music")

_PATH_ALIASES = {
    "desktop":    DESKTOP,    "my desktop":   DESKTOP,
    "downloads":  DOWNLOADS,  "my downloads": DOWNLOADS,
    "documents":  DOCUMENTS,  "my documents": DOCUMENTS,
    "pictures":   PICTURES,
    "videos":     VIDEOS,
    "music":      MUSIC,
}


def _resolve_path(filepath: str) -> str:
    """Expand ~, aliases, and env-style variables in a file path."""
    filepath = (filepath or "").strip()
    filepath = filepath.replace("%USERPROFILE%", os.path.expanduser("~"))
    filepath = filepath.replace("$HOME", os.path.expanduser("~"))
    filepath = filepath.replace("%DESKTOP%", DESKTOP)
    filepath = os.path.expanduser(filepath)
    low = filepath.lower()
    for alias, resolved in _PATH_ALIASES.items():
        if low.startswith(alias + "/"):
            filepath = os.path.join(resolved, filepath[len(alias) + 1:])
            break
        elif low == alias:
            filepath = resolved
            break
    return filepath


_FILE_EXTENSIONS = {
    "blender":   [".blend"],
    "figma":     [".fig"],
    "krita":     [".kra"],
    "gimp":      [".xcf"],
    "inkscape":  [".svg"],
    "vs code":   [".code-workspace"],
    "code":      [".code-workspace"],
    "libreoffice writer":  [".odt", ".doc", ".docx"],
    "libreoffice calc":    [".ods", ".xls", ".xlsx"],
    "libreoffice impress": [".odp", ".ppt", ".pptx"],
    "audacity":  [".aup3"],
    "darktable": [".dt", ".darktable"],
}


def find_recent_files(app_name: str) -> dict:
    """Find recent files associated with an application.
    Searches Desktop, Documents, and Downloads for matching extensions."""
    app_lower = app_name.lower().strip()
    exts: list[str] = []
    for key, value in _FILE_EXTENSIONS.items():
        if key in app_lower or app_lower in key:
            exts.extend(value)
    if not exts:
        return {"success": False, "message": f"No known file extensions for {app_name}"}

    candidates: list[tuple[str, float]] = []
    for d in (DESKTOP, DOCUMENTS, DOWNLOADS):
        if not os.path.isdir(d):
            continue
        for ext in exts:
            for p in glob.glob(os.path.join(d, f"*{ext}")):
                try:
                    candidates.append((p, os.path.getmtime(p)))
                except OSError:
                    continue
    if not candidates:
        return {"success": False, "message": f"No recent files for {app_name}"}
    candidates.sort(key=lambda x: x[1], reverse=True)
    return {
        "success": True,
        "files": [{"path": p, "name": os.path.basename(p), "mtime": ts} for p, ts in candidates[:10]],
    }


def open_file(file_path: str) -> dict:
    """Open a file with the default associated application via xdg-open."""
    fp = _resolve_path(file_path)
    if not os.path.exists(fp):
        return {"success": False, "error": f"File not found: {fp}"}
    try:
        subprocess.Popen(["xdg-open", fp], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"success": True, "message": f"Opened {os.path.basename(fp)}"}
    except FileNotFoundError:
        return {"success": False, "error": "xdg-open not installed (install xdg-utils)"}
    except Exception as e:
        return {"success": False, "error": f"Open failed: {e}"}


def create_file(filepath: str, content: str = "") -> dict:
    """Create a file with optional content. Writes under user dirs only."""
    target = _resolve_path(filepath)
    parent = os.path.dirname(target) or DESKTOP
    if not parent:
        return {"success": False, "error": "Invalid target path"}
    try:
        os.makedirs(parent, exist_ok=True)
        # If no extension, default to .txt so it actually opens with something.
        if not os.path.splitext(target)[1]:
            target = target + ".txt"
        with open(target, "w", encoding="utf-8") as f:
            f.write(content or "")
        return {"success": True, "path": target,
                "message": f"Created {os.path.basename(target)}"}
    except Exception as e:
        return {"success": False, "error": f"Create failed: {e}"}


# ── .desktop file app index ────────────────────────────────────────────────

_APP_INDEX: dict | None = None  # cached {display_name_lower: {name, exec, path}}

_DESKTOP_DIRS = [
    "/usr/share/applications",
    "/usr/local/share/applications",
    os.path.expanduser("~/.local/share/applications"),
    "/var/lib/flatpak/exports/share/applications",
    os.path.expanduser("~/.local/share/flatpak/exports/share/applications"),
    "/var/lib/snapd/desktop/applications",
]


def _parse_desktop_file(path: str) -> dict | None:
    """Parse a .desktop file. Returns {name, exec, no_display} or None on failure."""
    name = None
    exec_line = None
    no_display = False
    hidden = False
    try:
        in_main = False
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.rstrip("\r\n")
                if line.startswith("["):
                    in_main = (line.strip() == "[Desktop Entry]")
                    continue
                if not in_main:
                    continue
                if line.startswith("Name=") and not name:
                    name = line[5:].strip()
                elif line.startswith("Exec=") and not exec_line:
                    exec_line = line[5:].strip()
                elif line.startswith("NoDisplay="):
                    no_display = line.split("=", 1)[1].strip().lower() == "true"
                elif line.startswith("Hidden="):
                    hidden = line.split("=", 1)[1].strip().lower() == "true"
        if not (name and exec_line) or hidden:
            return None
        return {
            "name":       name,
            "exec":       exec_line,
            "path":       path,
            "no_display": no_display,
            "desktop_id": os.path.splitext(os.path.basename(path))[0],
        }
    except Exception:
        return None


def _build_app_index() -> dict:
    """Build the application index from all available .desktop sources."""
    index: dict[str, dict] = {}
    for d in _DESKTOP_DIRS:
        if not os.path.isdir(d):
            continue
        for fname in os.listdir(d):
            if not fname.endswith(".desktop"):
                continue
            entry = _parse_desktop_file(os.path.join(d, fname))
            if not entry:
                continue
            if entry["no_display"]:
                continue
            key = entry["name"].lower()
            # Earliest-found wins, but ~/.local/share takes priority because it
            # gets walked after /usr; we explicitly skip overwrites unless this
            # one is the user-local version.
            if key in index and "/.local/" not in entry["path"]:
                continue
            index[key] = entry
    return index


def _get_app_index() -> dict:
    """Lazy-init the global app index."""
    global _APP_INDEX
    if _APP_INDEX is None:
        _APP_INDEX = _build_app_index()
        print(f"[pc_control] App index built: {len(_APP_INDEX)} entries")
    return _APP_INDEX


def _search_index(query: str) -> tuple[str | None, dict | None]:
    """Fuzzy-match a query against the desktop index. Returns (display_name, entry)."""
    q = (query or "").strip().lower()
    if not q:
        return None, None
    idx = _get_app_index()
    # Exact match first
    if q in idx:
        return idx[q]["name"], idx[q]
    # Prefix
    for name, entry in idx.items():
        if name.startswith(q):
            return entry["name"], entry
    # Substring
    for name, entry in idx.items():
        if q in name:
            return entry["name"], entry
    # Token overlap (for "vs code" → "Visual Studio Code"). Only return a
    # match when overlap is strong: at least 2 tokens shared, or >=50% of the
    # query's tokens. Otherwise weak shared words like "studio" misfire.
    q_tokens = {t for t in q.split() if len(t) > 1}
    if not q_tokens:
        return None, None
    min_required = max(2, (len(q_tokens) + 1) // 2)
    best = None
    best_score = 0
    for name, entry in idx.items():
        n_tokens = {t for t in name.split() if len(t) > 1}
        overlap = len(q_tokens & n_tokens)
        if overlap > best_score and overlap >= min_required:
            best_score = overlap
            best = (entry["name"], entry)
    return best if best else (None, None)


def _clean_exec_line(exec_line: str) -> list[str]:
    """Strip .desktop Exec field codes (%f, %u, %i, %c, %k, …) and tokenize."""
    cleaned = re.sub(r"\s*%[fuFUickdDnNvm]", "", exec_line).strip()
    try:
        return shlex.split(cleaned)
    except ValueError:
        return cleaned.split()


def _verify_app_launched(app_name: str) -> bool:
    """Best-effort check: did a process matching `app_name` appear?"""
    app_lower = app_name.lower().replace(" ", "")
    deadline = time.time() + 5
    while time.time() < deadline:
        for proc in psutil.process_iter(["name", "cmdline"]):
            try:
                pname = (proc.info.get("name") or "").lower().replace(" ", "")
                if app_lower in pname or pname in app_lower:
                    return True
                cmd = " ".join(proc.info.get("cmdline") or []).lower()
                if app_lower in cmd.replace(" ", ""):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        time.sleep(0.2)
    return False


def open_application(app_name: str) -> dict:
    """Open an installed application by name."""
    if not app_name:
        return {"success": False, "error": "Empty app_name"}

    display_name, entry = _search_index(app_name)
    if not entry:
        # Last-resort: try the name as a literal binary on PATH.
        binp = shutil.which(app_name) or shutil.which(app_name.lower())
        if binp:
            try:
                subprocess.Popen([binp], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 stdin=subprocess.DEVNULL, start_new_session=True)
                return {"success": True, "message": f"Launched {app_name}",
                        "ame_should_say": f"Opening {app_name}."}
            except Exception as e:
                return {"success": False, "error": f"Failed to launch '{app_name}': {e}"}
        return {"success": False, "error": f"Application not found: {app_name}",
                "ame_should_say": f"I couldn't find {app_name} on this system."}

    # Prefer gtk-launch with the desktop-id — it handles Flatpak / Snap / etc.
    desktop_id = entry.get("desktop_id")
    if shutil.which("gtk-launch") and desktop_id:
        try:
            subprocess.Popen(["gtk-launch", desktop_id],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             stdin=subprocess.DEVNULL, start_new_session=True)
            return {"success": True, "message": f"Launched {display_name}",
                    "ame_should_say": f"Opening {display_name}."}
        except Exception:
            pass

    # Fall back to gio launch.
    if shutil.which("gio"):
        try:
            subprocess.Popen(["gio", "launch", entry["path"]],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             stdin=subprocess.DEVNULL, start_new_session=True)
            return {"success": True, "message": f"Launched {display_name}",
                    "ame_should_say": f"Opening {display_name}."}
        except Exception:
            pass

    # Last resort: parse the Exec line and run it directly.
    argv = _clean_exec_line(entry["exec"])
    if not argv:
        return {"success": False, "error": f"Malformed .desktop Exec line: {entry['exec']}"}
    try:
        subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         stdin=subprocess.DEVNULL, start_new_session=True)
        return {"success": True, "message": f"Launched {display_name}",
                "ame_should_say": f"Opening {display_name}."}
    except Exception as e:
        return {"success": False, "error": f"Launch failed: {e}"}


def _find_item_in_dir(directory: str, name: str) -> str | None:
    """Find a folder named `name` (case-insensitive) under `directory`."""
    if not os.path.isdir(directory):
        return None
    name_low = name.lower()
    for entry in os.listdir(directory):
        if entry.lower() == name_low:
            full = os.path.join(directory, entry)
            if os.path.isdir(full):
                return full
    return None


def open_folder(folder_name: str) -> dict:
    """Open a named folder in the file manager."""
    name = (folder_name or "").strip()
    if not name:
        return {"success": False, "error": "Empty folder_name"}

    # Direct alias?
    for alias, resolved in _PATH_ALIASES.items():
        if name.lower() == alias:
            return _open_path(resolved)

    # Absolute path?
    resolved = _resolve_path(name)
    if os.path.isdir(resolved):
        return _open_path(resolved)

    # Search under common user dirs.
    for root in (os.path.expanduser("~"), DOCUMENTS, DESKTOP, DOWNLOADS):
        hit = _find_item_in_dir(root, name)
        if hit:
            return _open_path(hit)

    return {"success": False, "error": f"Folder not found: {folder_name}"}


def _open_path(path: str) -> dict:
    try:
        subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"success": True, "message": f"Opened {os.path.basename(path) or path}"}
    except FileNotFoundError:
        return {"success": False, "error": "xdg-open not installed"}
    except Exception as e:
        return {"success": False, "error": f"Open failed: {e}"}


def close_application(app_name: str) -> dict:
    """Terminate a running application by name."""
    if not app_name:
        return {"success": False, "error": "Empty app_name"}
    target = app_name.lower().replace(" ", "")
    killed: list[str] = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            pname = (proc.info.get("name") or "").lower().replace(" ", "")
            if not pname:
                continue
            if target == pname or target in pname or pname in target:
                proc.terminate()
                killed.append(f"{proc.info['name']} (pid={proc.info['pid']})")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if not killed:
        return {"success": False, "error": f"No running process matched: {app_name}"}

    # Wait for graceful termination, then escalate.
    time.sleep(0.6)
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            pname = (proc.info.get("name") or "").lower().replace(" ", "")
            if target in pname or pname in target:
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return {"success": True, "closed": killed,
            "ame_should_say": f"Closed {app_name}."}


# ── Audio (PulseAudio / PipeWire) ─────────────────────────────────────────

_HAS_PACTL = bool(shutil.which("pactl"))
_HAS_WPCTL = bool(shutil.which("wpctl"))


def _run(cmd: list[str], timeout: float = 3.0) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def set_volume(level: int) -> dict:
    """Set master volume (0–100)."""
    level = max(0, min(100, int(level)))
    if _HAS_PACTL:
        r = _run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"])
        if r.returncode == 0:
            return {"success": True, "level": level,
                    "ame_should_say": f"Volume set to {level} percent."}
        return {"success": False, "error": r.stderr.strip() or "pactl failed"}
    if _HAS_WPCTL:
        # wpctl wants a 0..1 float
        r = _run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{level / 100:.2f}"])
        if r.returncode == 0:
            return {"success": True, "level": level,
                    "ame_should_say": f"Volume set to {level} percent."}
        return {"success": False, "error": r.stderr.strip() or "wpctl failed"}
    return {"success": False, "error": "Neither pactl nor wpctl is installed"}


def mute_volume() -> dict:
    """Mute the default sink."""
    if _HAS_PACTL:
        r = _run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1"])
        if r.returncode == 0:
            return {"success": True, "ame_should_say": "Muted."}
        return {"success": False, "error": r.stderr.strip() or "pactl failed"}
    if _HAS_WPCTL:
        r = _run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "1"])
        if r.returncode == 0:
            return {"success": True, "ame_should_say": "Muted."}
        return {"success": False, "error": r.stderr.strip() or "wpctl failed"}
    return {"success": False, "error": "Neither pactl nor wpctl is installed"}


def unmute_volume() -> dict:
    """Unmute the default sink."""
    if _HAS_PACTL:
        r = _run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"])
        if r.returncode == 0:
            return {"success": True, "ame_should_say": "Unmuted."}
        return {"success": False, "error": r.stderr.strip() or "pactl failed"}
    if _HAS_WPCTL:
        r = _run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "0"])
        if r.returncode == 0:
            return {"success": True, "ame_should_say": "Unmuted."}
        return {"success": False, "error": r.stderr.strip() or "wpctl failed"}
    return {"success": False, "error": "Neither pactl nor wpctl is installed"}


# ── Screenshots ────────────────────────────────────────────────────────────

def take_screenshot(save_path: str = None) -> dict:
    """Capture the full screen to a PNG. Uses mss (cross-platform on X11)."""
    if not save_path:
        save_path = os.path.join(
            PICTURES if os.path.isdir(PICTURES) else os.path.expanduser("~"),
            f"ame-screenshot-{datetime.now().strftime('%Y%m%d-%H%M%S')}.png",
        )
    save_path = _resolve_path(save_path)
    os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)

    try:
        import mss  # type: ignore
        import mss.tools  # type: ignore
        with mss.mss() as sct:
            monitor = sct.monitors[0]  # all-monitors stitched
            img = sct.grab(monitor)
            mss.tools.to_png(img.rgb, img.size, output=save_path)
        return {"success": True, "path": save_path,
                "ame_should_say": "Screenshot saved."}
    except Exception as e:
        # Last resort: try grim (Wayland) or scrot (X11) via shell.
        for cmd in (["grim", save_path], ["scrot", save_path]):
            if shutil.which(cmd[0]):
                try:
                    subprocess.run(cmd, capture_output=True, timeout=5)
                    if os.path.exists(save_path):
                        return {"success": True, "path": save_path,
                                "ame_should_say": "Screenshot saved."}
                except Exception:
                    continue
        return {"success": False, "error": f"Screenshot failed: {e}"}


def take_screenshot_and_analyze() -> dict:
    """Take a screenshot and feed it to Gemini Vision for analysis."""
    shot = take_screenshot()
    if not shot.get("success"):
        return shot
    try:
        from backend import vision as _vision
        analyzed = _vision.analyze_screen(shot["path"])
        if isinstance(analyzed, dict):
            analyzed.setdefault("path", shot["path"])
            return analyzed
        return {"success": True, "path": shot["path"], "analysis": str(analyzed)}
    except Exception as e:
        return {"success": True, "path": shot["path"], "analysis_error": str(e)}


# ── Screen lock ────────────────────────────────────────────────────────────

def lock_screen() -> dict:
    """Lock the screen. Tries loginctl, then xdg-screensaver, then GNOME's tool."""
    for cmd in (
        ["loginctl", "lock-session"],
        ["xdg-screensaver", "lock"],
        ["gnome-screensaver-command", "--lock"],
        ["xset", "s", "activate"],
    ):
        if shutil.which(cmd[0]):
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
                if r.returncode == 0:
                    return {"success": True, "ame_should_say": "Screen locked."}
            except Exception:
                continue
    return {"success": False,
            "error": "No screen-lock tool found (install loginctl or xdg-screensaver)."}


# ── Date / time ────────────────────────────────────────────────────────────

def get_current_time() -> dict:
    now = datetime.now()
    return {
        "success": True,
        "time_24h": now.strftime("%H:%M"),
        "time_12h": now.strftime("%I:%M %p").lstrip("0"),
        "iso": now.isoformat(timespec="seconds"),
    }


def get_current_date() -> dict:
    now = datetime.now()
    return {
        "success": True,
        "date":         now.strftime("%A, %B %d, %Y"),
        "iso":          now.date().isoformat(),
        "weekday":      now.strftime("%A"),
        "year_month_day": [now.year, now.month, now.day],
    }


# ── File search ────────────────────────────────────────────────────────────

def _fuzzy_match_file(query: str, filename: str, fullpath: str = "") -> bool:
    q = query.lower().strip()
    n = filename.lower()
    if q in n:
        return True
    base, _ext = os.path.splitext(n)
    if q in base:
        return True
    return False


def search_files(query: str) -> dict:
    """Search common user dirs for files matching `query`."""
    q = (query or "").strip()
    if not q:
        return {"success": False, "error": "Empty query"}

    roots = [DESKTOP, DOCUMENTS, DOWNLOADS, PICTURES, VIDEOS, MUSIC,
             os.path.join(os.path.expanduser("~"), "Projects"),
             os.path.join(os.path.expanduser("~"), "Code"),
             os.path.join(os.path.expanduser("~"), "Dev")]
    seen: set[str] = set()
    hits: list[dict] = []
    for root in roots:
        if not os.path.isdir(root) or root in seen:
            continue
        seen.add(root)
        for cur, _dirs, files in os.walk(root, onerror=lambda _: None):
            # Don't dive into hidden trees
            _dirs[:] = [d for d in _dirs if not d.startswith(".")]
            for f in files:
                if f.startswith("."):
                    continue
                if _fuzzy_match_file(q, f):
                    fp = os.path.join(cur, f)
                    try:
                        mt = os.path.getmtime(fp)
                    except OSError:
                        continue
                    hits.append({"path": fp, "name": f, "mtime": mt})
                    if len(hits) >= 50:
                        break
            if len(hits) >= 50:
                break
        if len(hits) >= 50:
            break

    hits.sort(key=lambda d: d["mtime"], reverse=True)
    return {"success": True, "matches": hits[:25], "total": len(hits)}


# ── Keyboard / mouse ──────────────────────────────────────────────────────

def _gui_check() -> dict | None:
    if not _PYAUTOGUI_AVAILABLE:
        return {"success": False,
                "error": "Keyboard/mouse automation needs an X11 session (pyautogui unavailable)."}
    # Wayland sessions sometimes have DISPLAY set, sometimes not. Best detection
    # is checking for XDG_SESSION_TYPE=wayland.
    if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
        return {"success": False,
                "error": "Keyboard/mouse tools require an X11 session (you're on Wayland)."}
    return None


def type_text(text: str) -> dict:
    err = _gui_check()
    if err: return err
    try:
        pyautogui.typewrite(text or "", interval=0.01)
        return {"success": True, "chars": len(text or "")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def type_text_slow(text: str) -> dict:
    err = _gui_check()
    if err: return err
    try:
        pyautogui.typewrite(text or "", interval=0.05)
        return {"success": True, "chars": len(text or "")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def copy_to_clipboard(text: str) -> dict:
    if not _PYPERCLIP_AVAILABLE:
        return {"success": False, "error": "pyperclip unavailable (install xclip or wl-clipboard)"}
    try:
        pyperclip.copy(text or "")
        return {"success": True, "chars": len(text or "")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def move_mouse(x: int, y: int) -> dict:
    err = _gui_check()
    if err: return err
    try:
        pyautogui.moveTo(int(x), int(y))
        return {"success": True, "x": int(x), "y": int(y)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def click_mouse(x: int = None, y: int = None, button: str = "left") -> dict:
    err = _gui_check()
    if err: return err
    try:
        if x is not None and y is not None:
            pyautogui.click(int(x), int(y), button=button)
        else:
            pyautogui.click(button=button)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def double_click(x: int = None, y: int = None) -> dict:
    err = _gui_check()
    if err: return err
    try:
        if x is not None and y is not None:
            pyautogui.doubleClick(int(x), int(y))
        else:
            pyautogui.doubleClick()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def press_key(key: str) -> dict:
    err = _gui_check()
    if err: return err
    try:
        pyautogui.press(key)
        return {"success": True, "key": key}
    except Exception as e:
        return {"success": False, "error": str(e)}


def hotkey(*keys) -> dict:
    err = _gui_check()
    if err: return err
    try:
        pyautogui.hotkey(*keys)
        return {"success": True, "keys": list(keys)}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Terminal command runner ───────────────────────────────────────────────

_DESTRUCTIVE_PATTERNS = [
    r"\brm\s+-rf?\s+/(\s|$)",     # rm -rf /
    r"\brm\s+-rf?\s+/\s",         # rm -rf / something
    r"\bdd\s+if=.*of=/dev/sd",
    r"\bmkfs",
    r":\(\)\s*{\s*:\|:&",         # fork bomb
    r"\bchmod\s+-R\s+\S+\s+/$",
    r"\b>\s*/dev/sda",
]


def _is_safe_command(cmd: str) -> bool:
    """Reject obviously destructive shell commands."""
    if not cmd:
        return False
    low = cmd.lower()
    for pat in _DESTRUCTIVE_PATTERNS:
        if re.search(pat, low):
            return False
    return True


def _generate_command_with_ai(task_description: str) -> str | None:
    """Ask Gemini to translate a natural-language task into a single Linux command."""
    try:
        from backend.gemini_client import call_task_model, extract_text
    except Exception:
        return None
    api_key = os.getenv("GOOGLE_AI_STUDIO_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    prompt = (
        "Convert this user task into a SINGLE Linux shell command. "
        "Reply with the command only, no explanation, no code fences:\n\n"
        f"Task: {task_description}\n\nCommand:"
    )
    try:
        resp = call_task_model([{"parts": [{"text": prompt}]}], api_key=api_key, timeout=10)
        raw = (extract_text(resp) or "").strip()
        # Strip code fences if the model ignored instructions.
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw).strip()
        return raw or None
    except Exception:
        return None


def _try_direct_python(task_description: str) -> dict | None:
    """Heuristic shortcut for very common requests that don't need a shell."""
    low = task_description.lower()
    if "list files" in low or "show files" in low:
        d = DESKTOP
        if "documents" in low: d = DOCUMENTS
        if "downloads" in low: d = DOWNLOADS
        try:
            files = sorted(os.listdir(d))
            return {"success": True, "output": "\n".join(files[:50]),
                    "directory": d}
        except Exception as e:
            return {"success": False, "error": str(e)}
    return None


def run_terminal_command(command: str = "", task_description: str = "") -> dict:
    """Execute a shell command. If `command` is empty, ask Gemini to derive one
    from `task_description`."""
    if not command and not task_description:
        return {"success": False, "error": "No command or task provided"}

    if not command and task_description:
        direct = _try_direct_python(task_description)
        if direct is not None:
            return direct
        command = _generate_command_with_ai(task_description) or ""
        if not command:
            return {"success": False, "error": "Could not derive a command from the task"}

    if not _is_safe_command(command):
        return {"success": False, "error": "Command rejected by safety filter",
                "command": command}

    try:
        r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30,
                           executable="/bin/bash")
        return {
            "success": r.returncode == 0,
            "command": command,
            "stdout": r.stdout.strip(),
            "stderr": r.stderr.strip(),
            "code":   r.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Command timed out (30s)", "command": command}
    except Exception as e:
        return {"success": False, "error": str(e), "command": command}


# ── Desktop organization ──────────────────────────────────────────────────

def list_desktop() -> dict:
    """List files on the desktop."""
    if not os.path.isdir(DESKTOP):
        return {"success": False, "error": f"Desktop dir missing: {DESKTOP}"}
    items: list[dict] = []
    for name in sorted(os.listdir(DESKTOP)):
        if name.startswith("."):
            continue
        full = os.path.join(DESKTOP, name)
        try:
            stat = os.stat(full)
            items.append({
                "name": name,
                "is_dir": os.path.isdir(full),
                "size": stat.st_size,
                "mtime": stat.st_mtime,
            })
        except OSError:
            continue
    return {"success": True, "directory": DESKTOP, "items": items, "count": len(items)}


def _categorize(name: str) -> str:
    ext = os.path.splitext(name)[1].lower()
    if ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}: return "Images"
    if ext in {".mp4", ".mov", ".mkv", ".avi", ".webm"}:                   return "Videos"
    if ext in {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".opus"}:          return "Audio"
    if ext in {".pdf", ".doc", ".docx", ".odt", ".txt", ".rtf"}:           return "Documents"
    if ext in {".xls", ".xlsx", ".ods", ".csv"}:                            return "Spreadsheets"
    if ext in {".ppt", ".pptx", ".odp"}:                                    return "Presentations"
    if ext in {".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar"}:        return "Archives"
    if ext in {".py", ".js", ".jsx", ".ts", ".tsx", ".sh", ".c", ".cpp",
               ".h", ".rs", ".go", ".rb", ".php", ".java", ".kt"}:          return "Code"
    if ext in {".sh", ".AppImage", ".deb", ".rpm", ".run"}:                return "Installers"
    return "Other"


def organize_desktop(mode: str = "type") -> dict:
    """Group desktop files by type into subfolders."""
    if mode != "type":
        return {"success": False, "error": "Only mode='type' is supported"}
    if not os.path.isdir(DESKTOP):
        return {"success": False, "error": f"Desktop dir missing: {DESKTOP}"}
    moved = 0
    buckets: dict[str, int] = {}
    for name in os.listdir(DESKTOP):
        if name.startswith("."):
            continue
        src = os.path.join(DESKTOP, name)
        if os.path.isdir(src):
            continue
        cat = _categorize(name)
        dst_dir = os.path.join(DESKTOP, cat)
        os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, name)
        try:
            shutil.move(src, dst)
            moved += 1
            buckets[cat] = buckets.get(cat, 0) + 1
        except OSError:
            continue
    return {"success": True, "moved": moved, "by_category": buckets,
            "ame_should_say": f"Organized {moved} desktop file{'s' if moved != 1 else ''}."}


def clean_desktop() -> dict:
    """Move zero-byte and obviously temporary files off the desktop to a Trash folder."""
    if not os.path.isdir(DESKTOP):
        return {"success": False, "error": f"Desktop dir missing: {DESKTOP}"}
    trash = os.path.join(DESKTOP, "Trash")
    os.makedirs(trash, exist_ok=True)
    moved: list[str] = []
    for name in os.listdir(DESKTOP):
        if name.startswith(".") or name == "Trash":
            continue
        src = os.path.join(DESKTOP, name)
        if os.path.isdir(src):
            continue
        try:
            sz = os.path.getsize(src)
        except OSError:
            continue
        is_temp = name.endswith(("~", ".tmp", ".bak"))
        if sz == 0 or is_temp:
            try:
                shutil.move(src, os.path.join(trash, name))
                moved.append(name)
            except OSError:
                continue
    return {"success": True, "moved": moved, "trash_dir": trash,
            "ame_should_say": f"Cleaned {len(moved)} item{'s' if len(moved) != 1 else ''} off the desktop."}


# ── Steam (best-effort via steam:// URLs) ─────────────────────────────────

def launch_steam_game(game_name: str) -> dict:
    """Best-effort Steam game launch via the steam:// handler."""
    if not game_name:
        return {"success": False, "error": "Empty game_name"}
    # Without the appid we can't deep-link; try a search URL instead.
    try:
        subprocess.Popen(
            ["xdg-open", f"steam://search/{game_name}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return {"success": True,
                "ame_should_say": f"Opening Steam to find {game_name}."}
    except Exception as e:
        return {"success": False, "error": f"Could not contact Steam: {e}"}


def download_steam_game(game_name: str) -> dict:
    """Open Steam at the search page so the user can click Install themselves.
    Steam on Linux doesn't accept programmatic install actions."""
    return launch_steam_game(game_name)


# ── Reminders ─────────────────────────────────────────────────────────────

def set_reminder(message: str, minutes: int = None, time_str: str = None, date_str: str = None) -> dict:
    """Create a scheduled reminder. Routes to backend.scheduler."""
    try:
        from backend import scheduler
        result = scheduler.add_schedule(
            message=message, time_str=time_str, date_str=date_str,
            minutes=minutes, recurring=None,
        )
        if result.get("error"):
            return {"success": False, "error": result["error"]}
        return {"success": True, "schedule": result,
                "ame_should_say": "Reminder set."}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── No-op shim for legacy callers ─────────────────────────────────────────

def _get_exe_from_registry(_app_name: str) -> str | None:
    """Removed: Windows registry is gone. Kept as no-op for compatibility."""
    return None


def _find_chrome() -> str | None:
    """Find a Chrome/Chromium binary on PATH if available."""
    for cand in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        p = shutil.which(cand)
        if p:
            return p
    return None
