"""
Windows PC control functions for Ame AI assistant.
Handles application management, volume, screenshots, clipboard, etc.
"""

import sys, os
os.environ.setdefault('PYTHONUTF8', '1')
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'): sys.stderr.reconfigure(encoding='utf-8', errors='replace')


import subprocess
import ctypes
import time
import winreg
from pathlib import Path
from datetime import datetime
import re

import psutil
import pyautogui
import pyperclip

from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL


DESKTOP   = os.path.join(os.path.expanduser('~'), 'Desktop')
DOWNLOADS = os.path.join(os.path.expanduser('~'), 'Downloads')
DOCUMENTS = os.path.join(os.path.expanduser('~'), 'Documents')

_PATH_ALIASES = {
    'desktop':   DESKTOP,
    'downloads': DOWNLOADS,
    'documents': DOCUMENTS,
    'my desktop':   DESKTOP,
    'my downloads': DOWNLOADS,
    'my documents': DOCUMENTS,
}


def _resolve_path(filepath: str) -> str:
    """Expand ~, %USERPROFILE%, and common alias words in a file path."""
    filepath = filepath.strip()
    filepath = filepath.replace('%USERPROFILE%', os.path.expanduser('~'))
    filepath = filepath.replace('%DESKTOP%', DESKTOP)
    filepath = os.path.expanduser(filepath)
    # If the path starts with an alias word, expand it
    lower = filepath.lower()
    for alias, resolved in _PATH_ALIASES.items():
        if lower.startswith(alias + '/') or lower.startswith(alias + '\\'):
            filepath = os.path.join(resolved, filepath[len(alias)+1:])
            break
        elif lower == alias:
            filepath = resolved
            break
    return filepath


_FILE_EXTENSIONS = {
    'premiere pro': ['.prproj'],
    'photoshop': ['.psd'],
    'after effects': ['.aep'],
    'illustrator': ['.ai'],
    'word': ['.docx', '.doc'],
    'excel': ['.xlsx', '.xls'],
    'powerpoint': ['.pptx', '.ppt'],
    'vs code': ['.code-workspace'],
    'audition': ['.sesx'],
    'blender': ['.blend'],
    'figma': ['.fig'],
}


def find_recent_files(app_name: str) -> dict:
    """Find recent files associated with an application.
    Searches Desktop, Documents, and Downloads for matching extensions."""
    import glob as _glob
    app_lower = app_name.lower()

    extensions = []
    for key, exts in _FILE_EXTENSIONS.items():
        if key in app_lower or any(word in app_lower for word in key.split()):
            extensions.extend(exts)

    if not extensions:
        return {"success": False, "message": f"No known file types for '{app_name}'", "files": []}

    search_paths = [DESKTOP, DOCUMENTS, DOWNLOADS, os.path.expanduser("~")]
    found = []
    for base in search_paths:
        if not os.path.exists(base):
            continue
        for ext in extensions:
            found.extend(_glob.glob(os.path.join(base, f"*{ext}")))

    # Deduplicate and sort by most recently modified
    found = list(dict.fromkeys(found))
    found.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    found = found[:5]

    if not found:
        return {"success": False, "message": f"No {app_name} files found on Desktop, Documents, or Downloads", "files": []}

    file_names = [os.path.basename(f) for f in found]
    return {"success": True, "files": found, "names": file_names, "count": len(found)}


def open_file(file_path: str) -> dict:
    """Open a specific file with its default application."""
    try:
        file_path = _resolve_path(file_path)
        if not os.path.exists(file_path):
            return {"success": False, "message": f"File not found: {file_path}"}
        os.startfile(file_path)
        return {"success": True, "message": f"Opened {os.path.basename(file_path)}"}
    except Exception as e:
        return {"success": False, "message": f"Could not open file: {e}"}


def create_file(filepath: str, content: str = '') -> dict:
    """Create a file at the given path with optional content.
    Always verifies the file actually exists after writing."""
    try:
        filepath = _resolve_path(filepath)
        directory = os.path.dirname(filepath)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            return {
                'success': True,
                'path': filepath,
                'size': size,
                'message': f'File created at {filepath}',
            }
        else:
            return {
                'success': False,
                'message': 'File write appeared to succeed but file not found after writing.',
            }
    except PermissionError:
        return {'success': False, 'message': f'Permission denied writing to {filepath}'}
    except Exception as e:
        return {'success': False, 'message': f'Error creating file: {e}'}


# ── Built-in Windows commands (no path needed) ─────────────────────────────
BUILTIN_APPS = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "task manager": "taskmgr.exe",
    "taskmgr": "taskmgr.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
    "settings": "ms-settings:",
    "windows settings": "ms-settings:",
    "paint": "mspaint.exe",
    "wordpad": "wordpad.exe",
    "snipping tool": "snippingtool.exe",
    "control panel": "control.exe",
}


# ── Universal App Index ─────────────────────────────────────────────────────
_APP_INDEX: dict | None = None
_APP_INDEX_TIME: float = 0


def _build_app_index() -> dict:
    """Scan the entire system for launchable apps. Returns {display_name_lower: path}.
    Sources: Start Menu, Desktop shortcuts, Registry App Paths, PATH,
    Program Files tree, AppData, VirtualBox VMs."""
    index = {}

    # 1. Start Menu shortcuts (system + user)
    sm_dirs = [
        r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
        os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
    ]
    for base in sm_dirs:
        if not os.path.isdir(base):
            continue
        for root, _, files in os.walk(base):
            for f in files:
                if f.lower().endswith(".lnk"):
                    display = os.path.splitext(f)[0]
                    index[display.lower()] = os.path.join(root, f)

    # 2. Desktop shortcuts
    desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
    if os.path.isdir(desktop_dir):
        try:
            for f in os.listdir(desktop_dir):
                if f.lower().endswith(".lnk"):
                    display = os.path.splitext(f)[0]
                    index[display.lower()] = os.path.join(desktop_dir, f)
        except PermissionError:
            pass

    # 3. Public Desktop shortcuts
    pub_desktop = r"C:\Users\Public\Desktop"
    if os.path.isdir(pub_desktop):
        try:
            for f in os.listdir(pub_desktop):
                if f.lower().endswith(".lnk"):
                    display = os.path.splitext(f)[0]
                    index[display.lower()] = os.path.join(pub_desktop, f)
        except PermissionError:
            pass

    # 4. Registry App Paths
    reg_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive, reg_key) as key:
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, subkey_name) as subkey:
                            try:
                                value, _ = winreg.QueryValueEx(subkey, "")
                                if value and os.path.exists(value):
                                    display = subkey_name.replace(".exe", "")
                                    index[display.lower()] = value
                            except (OSError, FileNotFoundError):
                                pass
                        i += 1
                    except OSError:
                        break
        except (OSError, FileNotFoundError):
            pass

    # 5. Scan Program Files, AppData for exe files (depth-limited to 4 levels)
    scan_roots = [
        os.environ.get('PROGRAMFILES', ''),
        os.environ.get('PROGRAMFILES(X86)', ''),
        os.environ.get('LOCALAPPDATA', ''),
        os.environ.get('APPDATA', ''),
        r'C:\Riot Games',
        r'C:\Games',
    ]
    skip_dirs = {'cache', 'temp', 'tmp', 'logs', 'log', '__pycache__', 'node_modules',
                 '.git', 'translations', 'locales', 'resources', 'icons'}
    for scan_root in scan_roots:
        if not scan_root or not os.path.isdir(scan_root):
            continue
        for root, dirs, files in os.walk(scan_root):
            # Depth limit: max 4 levels deep
            depth = root[len(scan_root):].count(os.sep)
            if depth >= 4:
                dirs.clear()
                continue
            dirs[:] = [d for d in dirs if d.lower() not in skip_dirs and not d.startswith('.')]
            for f in files:
                if f.lower().endswith('.exe') and not f.startswith('unins'):
                    display = f.replace('.exe', '').replace('.EXE', '')
                    key = display.lower()
                    # Prefer shortcuts over raw exes (shortcuts have better names)
                    if key not in index:
                        index[key] = os.path.join(root, f)

    # 6. VirtualBox VMs
    for vbox_path in [
        r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe",
        r"C:\Program Files (x86)\Oracle\VirtualBox\VBoxManage.exe",
    ]:
        if os.path.exists(vbox_path):
            try:
                result = subprocess.run(
                    [vbox_path, 'list', 'vms'],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    for line in result.stdout.splitlines():
                        if '"' in line:
                            vm_name = line.split('"')[1]
                            index[vm_name.lower()] = f"vbox://{vm_name}"
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
            break

    return index


def _get_app_index() -> dict:
    """Return cached app index, rebuilding every 5 minutes."""
    global _APP_INDEX, _APP_INDEX_TIME
    import time as _time
    if _APP_INDEX is None or (_time.monotonic() - _APP_INDEX_TIME) > 300:
        _APP_INDEX = _build_app_index()
        _APP_INDEX_TIME = _time.monotonic()
        print(f"[AppIndex] Indexed {len(_APP_INDEX)} apps/shortcuts")
    return _APP_INDEX


def _search_index(query: str) -> tuple[str | None, str | None]:
    """Search the app index with progressive fuzzy matching.
    Returns (display_name, path) or (None, None)."""
    index = _get_app_index()
    q = query.lower().strip()
    q_nospace = q.replace(' ', '').replace('-', '').replace('_', '')
    q_words = set(q.split())

    # Pass 1: exact match
    if q in index:
        return q, index[q]

    # Pass 2: query without spaces matches key without spaces
    for name, path in index.items():
        if q_nospace == name.replace(' ', '').replace('-', '').replace('_', ''):
            return name, path

    # Pass 3: query is substring of name or vice versa
    for name, path in index.items():
        if q in name or name in q:
            return name, path

    # Pass 4: no-space substring match
    for name, path in index.items():
        name_nospace = name.replace(' ', '').replace('-', '').replace('_', '')
        if q_nospace in name_nospace or name_nospace in q_nospace:
            return name, path

    # Pass 5: word-level match — best overlap wins
    best_name, best_path, best_score = None, None, 0
    for name, path in index.items():
        shared = q_words & set(name.split())
        score = len(shared)
        if score > best_score:
            best_score = score
            best_name, best_path = name, path
    if best_score >= 1:
        return best_name, best_path

    return None, None


def _get_exe_from_registry(app_name: str) -> str | None:
    """Look up an app's exe path in the Windows App Paths registry key."""
    exe_name = app_name if app_name.endswith(".exe") else f"{app_name}.exe"
    key_path = f"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\{exe_name}"
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive, key_path) as key:
                value, _ = winreg.QueryValueEx(key, "")
                if value:
                    return value
        except FileNotFoundError:
            continue
        except OSError:
            continue
    return None


def _get_volume_interface():
    """Return a pycaw IAudioEndpointVolume interface for the default audio device."""
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))


def _find_chrome() -> str | None:
    """Return the real Chrome executable path, checking common locations and registry."""
    localappdata = os.environ.get("LOCALAPPDATA", "")
    programfiles = os.environ.get("PROGRAMFILES", "C:\\Program Files")
    programfiles_x86 = os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")

    candidates = [
        os.path.join(localappdata, "Google\\Chrome\\Application\\chrome.exe"),
        os.path.join(programfiles, "Google\\Chrome\\Application\\chrome.exe"),
        os.path.join(programfiles_x86, "Google\\Chrome\\Application\\chrome.exe"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p

    reg_path = _get_exe_from_registry("chrome")
    if reg_path and os.path.exists(reg_path):
        return reg_path

    return None


def _launch_path(path: str, app_lower: str, label: str) -> dict:
    """Launch a resolved path (exe, ms- URI, or .lnk) and return result dict."""
    try:
        if path.startswith("ms-") or path.startswith("http"):
            os.startfile(path)
            return {"success": True, "message": f"Opened {label}.", "context": f"{label} is now open on the user's PC."}
        if path.lower().endswith(".lnk") or not os.path.exists(path):
            os.startfile(path)
            return {"success": True, "message": f"Opened {label}.", "context": f"{label} is now open on the user's PC."}
        # Always set cwd to the exe's own folder so apps like OBS can find
        # their locale/resource files relative to their install directory.
        exe_dir = os.path.dirname(os.path.abspath(path))
        if "discord" in app_lower:
            subprocess.Popen([path, "--processStart", "Discord.exe"], cwd=exe_dir)
        elif "teams" in app_lower:
            subprocess.Popen([path, "--processStart", "Teams.exe"], cwd=exe_dir)
        elif "valorant" in app_lower:
            subprocess.Popen([path, "--launch-product=valorant", "--launch-patchline=live"], cwd=exe_dir)
        else:
            subprocess.Popen([path], cwd=exe_dir)
        return {"success": True, "message": f"Opened {label}.", "context": f"{label} is now open on the user's PC."}
    except Exception as e:
        return {"success": False, "message": f"Found {label} but failed to launch: {e}"}


def _verify_app_launched(app_name: str) -> bool:
    """Wait 2 seconds then check if a process matching app_name appeared."""
    time.sleep(2)
    app_lower = app_name.lower().replace(' ', '')
    for proc in psutil.process_iter(['name', 'pid']):
        try:
            proc_name = proc.info['name'].lower().replace('.exe', '')
            proc_no_space = proc_name.replace(' ', '')
            if (app_lower in proc_no_space or
                    proc_no_space in app_lower or
                    any(word in proc_name for word in
                        app_name.lower().split() if len(word) > 3)):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def open_application(app_name: str) -> dict:
    app_lower = app_name.lower().strip()

    # 1. Built-in Windows commands (notepad, calc, explorer, etc.)
    builtin = BUILTIN_APPS.get(app_lower)
    if builtin:
        try:
            if builtin.startswith("ms-"):
                os.startfile(builtin)
            else:
                subprocess.Popen([builtin])
            return {"success": True, "message": f"Opened {app_name}.", "context": f"{app_name} is now open on the user's PC."}
        except Exception as e:
            return {"success": False, "message": f"Failed to open {app_name}: {e}"}

    # 2. Universal app index — searches everything on the system
    found_name, found_path = _search_index(app_lower)
    if found_path:
        # Handle VirtualBox VMs
        if found_path.startswith("vbox://"):
            vm_name = found_path[7:]
            for vbox_exe in [
                r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe",
                r"C:\Program Files (x86)\Oracle\VirtualBox\VBoxManage.exe",
            ]:
                if os.path.exists(vbox_exe):
                    subprocess.Popen([vbox_exe, 'startvm', vm_name])
                    return {"success": True, "message": f"Starting VirtualBox VM '{vm_name}'.", "context": f"VirtualBox VM '{vm_name}' is now starting."}
            return {"success": False, "message": f"Found VM '{vm_name}' but VBoxManage not found."}

        # Handle regular apps
        result = _launch_path(found_path, app_lower, found_name or app_name)
        if result["success"]:
            if _verify_app_launched(app_name):
                return {"success": True, "message": f"Opened {app_name} successfully.", "context": f"{app_name} is now open on the user's PC."}
            # Launch succeeded but process not detected — still probably fine
            # (some apps spawn under different process names)
            return {"success": True, "message": f"Opened {app_name}.", "context": f"{app_name} should be open on the user's PC."}

    # 3. PowerShell Get-StartApps — catches UWP/Store apps
    try:
        ps = (
            f'$app = Get-StartApps | Where-Object {{ $_.Name -like "*{app_name}*" }} | '
            f'Select-Object -First 1; if ($app) {{ Start-Process $app.AppID; exit 0 }} else {{ exit 1 }}'
        )
        r = subprocess.run(
            ['powershell', '-NoProfile', '-NonInteractive', '-Command', ps],
            capture_output=True, timeout=12
        )
        if r.returncode == 0:
            return {"success": True, "message": f"Opened {app_name}.", "context": f"{app_name} is now open on the user's PC."}
    except Exception:
        pass

    # 4. Deep scan — walk entire C: drive for the exe (slow but thorough)
    exe_variants = [
        app_lower.replace(" ", "") + ".exe",
        app_lower.replace(" ", "-") + ".exe",
        app_lower.replace(" ", "_") + ".exe",
        app_lower + ".exe",
    ]
    deep_roots = [
        os.environ.get('PROGRAMFILES', ''),
        os.environ.get('PROGRAMFILES(X86)', ''),
        os.environ.get('LOCALAPPDATA', ''),
        os.environ.get('APPDATA', ''),
        os.path.join(os.path.expanduser("~"), "Desktop"),
        os.path.join(os.path.expanduser("~"), "Downloads"),
        r'C:\Riot Games',
        r'C:\Games',
    ]
    for scan_root in deep_roots:
        if not scan_root or not os.path.isdir(scan_root):
            continue
        try:
            for root, dirs, files in os.walk(scan_root):
                depth = root[len(scan_root):].count(os.sep)
                if depth >= 6:
                    dirs.clear()
                    continue
                dirs[:] = [d for d in dirs if d.lower() not in
                           {'cache', 'temp', 'tmp', 'logs', '__pycache__', 'node_modules', '.git'}
                           and not d.startswith('.')]
                for f in files:
                    if f.lower() in exe_variants:
                        exe_path = os.path.join(root, f)
                        result = _launch_path(exe_path, app_lower, app_name)
                        if result["success"]:
                            # Add to index for next time
                            idx = _get_app_index()
                            idx[app_lower] = exe_path
                            return {"success": True, "message": f"Opened {app_name}.", "context": f"{app_name} is now open on the user's PC."}
        except PermissionError:
            continue

    return {"success": False, "message": f"Could not find '{app_name}' anywhere on this PC. It may not be installed."}


def _find_item_in_dir(directory: str, name: str) -> str | None:
    """Search a directory for a file or folder matching name, with progressively looser matching."""
    if not os.path.isdir(directory):
        return None

    try:
        all_items = os.listdir(directory)
    except PermissionError:
        return None

    name_nospace = name.lower().replace(' ', '').replace('_', '').replace('-', '')
    name_words = [w for w in name.lower().split() if len(w) > 2]

    # Pass 1: exact case-insensitive
    for item in all_items:
        if item.lower() == name.lower():
            return os.path.join(directory, item)

    # Pass 2: ignore spaces/dashes/underscores
    for item in all_items:
        item_nospace = item.lower().replace(' ', '').replace('_', '').replace('-', '')
        if item_nospace == name_nospace:
            return os.path.join(directory, item)

    # Pass 3: name is substring of item or vice versa (no-space versions)
    for item in all_items:
        item_nospace = item.lower().replace(' ', '').replace('_', '').replace('-', '')
        if name_nospace in item_nospace or item_nospace in name_nospace:
            return os.path.join(directory, item)

    # Pass 4: any significant word from the name appears in the item name
    for item in all_items:
        item_lower = item.lower()
        for word in name_words:
            if word in item_lower:
                return os.path.join(directory, item)

    return None


def open_folder(folder_name: str) -> dict:
    """Open a folder by name using strict priority matching."""
    folder_name = folder_name.strip()

    search_paths = [
        str(Path.home() / "Desktop"),
        str(Path.home() / "Documents"),
        str(Path.home() / "Downloads"),
        str(Path.home()),
    ]

    name_clean = folder_name.lower().strip()
    name_no_space = name_clean.replace(' ', '')

    def _try_open(path: str, item: str) -> dict:
        full = os.path.join(path, item)
        try:
            subprocess.Popen(['explorer', full])
            return {"success": True, "message": f"Opened folder: {item}", "path": full}
        except Exception as e:
            return {"success": False, "message": f"Found '{item}' but failed to open: {e}"}

    # PASS 1: Exact match (case insensitive)
    for base in search_paths:
        if not os.path.exists(base):
            continue
        for item in os.listdir(base):
            if item.lower() == name_clean:
                path = os.path.join(base, item)
                if os.path.isdir(path):
                    print(f"[open_folder] Pass 1 match: {path}")
                    return _try_open(base, item)

    # PASS 2: Exact match ignoring spaces
    for base in search_paths:
        if not os.path.exists(base):
            continue
        for item in os.listdir(base):
            if item.lower().replace(' ', '') == name_no_space:
                path = os.path.join(base, item)
                if os.path.isdir(path):
                    print(f"[open_folder] Pass 2 match: {path}")
                    return _try_open(base, item)

    # PASS 3: Folder name STARTS WITH the search term (at least 4 chars)
    if len(name_clean) >= 4:
        for base in search_paths:
            if not os.path.exists(base):
                continue
            for item in os.listdir(base):
                if item.lower().startswith(name_clean[:4]):
                    path = os.path.join(base, item)
                    if os.path.isdir(path):
                        print(f"[open_folder] Pass 3 match: {path}")
                        return _try_open(base, item)

    # PASS 4: ALL words (>2 chars) in search term appear in folder name
    name_words = [w for w in name_clean.split() if len(w) > 2]
    if name_words:
        for base in search_paths:
            if not os.path.exists(base):
                continue
            for item in os.listdir(base):
                item_lower = item.lower()
                if all(word in item_lower for word in name_words):
                    path = os.path.join(base, item)
                    if os.path.isdir(path):
                        print(f"[open_folder] Pass 4 match: {path}")
                        return _try_open(base, item)

    # Not found — list desktop folders for context
    desktop = str(Path.home() / "Desktop")
    try:
        items = os.listdir(desktop)
        dirs = [i for i in items if os.path.isdir(os.path.join(desktop, i))]
        return {
            "success": False,
            "message": f"Could not find folder named '{folder_name}'",
            "desktop_folders": dirs,
        }
    except Exception:
        return {"success": False, "message": f"Could not find folder named '{folder_name}'"}


_PROCESS_MAP = {
    'send anywhere':      ['SendAnywhere', 'sendanywhere'],
    'sendanywhere':       ['SendAnywhere', 'sendanywhere'],
    'obs studio':         ['obs64', 'obs32', 'obs'],
    'obs':                ['obs64', 'obs32', 'obs'],
    'chrome':             ['chrome'],
    'google chrome':      ['chrome'],
    'firefox':            ['firefox'],
    'edge':               ['msedge'],
    'microsoft edge':     ['msedge'],
    'spotify':            ['Spotify'],
    'discord':            ['Discord'],
    'slack':              ['slack'],
    'teams':              ['Teams'],
    'microsoft teams':    ['Teams'],
    'zoom':               ['Zoom'],
    'whatsapp':           ['WhatsApp'],
    'telegram':           ['Telegram'],
    'vscode':             ['Code'],
    'vs code':            ['Code'],
    'visual studio code': ['Code'],
    'notepad++':          ['notepad++'],
    'steam':              ['steam'],
    'valorant':           ['VALORANT'],
    'vlc':                ['vlc'],
    'vlc media player':   ['vlc'],
    'notepad':            ['notepad'],
    'calculator':         ['calculator', 'calc'],
    'calc':               ['calculator', 'calc'],
    'explorer':           ['explorer'],
    'file explorer':      ['explorer'],
    'task manager':       ['Taskmgr'],
    'taskmgr':            ['Taskmgr'],
    'word':               ['WINWORD'],
    'microsoft word':     ['WINWORD'],
    'excel':              ['EXCEL'],
    'microsoft excel':    ['EXCEL'],
    'powerpoint':         ['POWERPNT'],
    'microsoft powerpoint': ['POWERPNT'],
    'outlook':            ['OUTLOOK'],
    'premiere':           ['premiere pro'],
    'premiere pro':       ['premiere pro'],
    'after effects':      ['afterfx'],
    'photoshop':          ['photoshop'],
    'gimp':               ['gimp-2.10', 'gimp'],
}


def close_application(app_name: str) -> dict:
    """Kill all processes matching the given app name."""
    app_lower = app_name.strip().lower()

    # Get candidate process name fragments from map, or derive from raw name
    candidates = _PROCESS_MAP.get(app_lower)
    if not candidates:
        candidates = [app_lower, app_lower.replace(' ', ''), app_lower.replace(' ', '-')]

    # Normalise candidates for comparison (lowercase, no .exe)
    cand_clean = [c.lower().replace('.exe', '') for c in candidates]

    killed = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            proc_name = proc.info['name']
            if not proc_name:
                continue
            proc_clean = proc_name.lower().replace('.exe', '')

            for target in cand_clean:
                if target == proc_clean or target in proc_clean or proc_clean in target:
                    proc.kill()
                    killed.append(proc_name)
                    break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if killed:
        return {"success": True, "message": f"Closed {app_name} successfully."}
    return {"success": False, "message": f"Could not find '{app_name}' running. It may already be closed."}


def set_volume(level: int) -> dict:
    """Set the system master volume (0-100)."""
    try:
        level = max(0, min(100, int(level)))
        volume = _get_volume_interface()
        volume.SetMasterVolumeLevelScalar(level / 100.0, None)
        return {"success": True, "message": f"Volume set to {level}%."}
    except Exception as e:
        return {"success": False, "message": f"Failed to set volume: {e}"}


def mute_volume() -> dict:
    """Mute system audio."""
    try:
        volume = _get_volume_interface()
        volume.SetMute(1, None)
        return {"success": True, "message": "Volume muted."}
    except Exception as e:
        return {"success": False, "message": f"Failed to mute: {e}"}


def unmute_volume() -> dict:
    """Unmute system audio."""
    try:
        volume = _get_volume_interface()
        volume.SetMute(0, None)
        return {"success": True, "message": "Volume unmuted."}
    except Exception as e:
        return {"success": False, "message": f"Failed to unmute: {e}"}


def take_screenshot(save_path: str = None) -> dict:
    """Take a screenshot and save it to the Desktop with a timestamp."""
    try:
        import PIL.ImageGrab

        if not save_path:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            save_path = os.path.join(desktop, f"screenshot_{timestamp}.png")

        save_path = os.path.expanduser(save_path)
        save_path = os.path.normpath(save_path)

        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        screenshot = PIL.ImageGrab.grab()
        screenshot.save(save_path, 'PNG')

        if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
            return {
                "success": True,
                "path": save_path,
                "message": f"Screenshot saved to {os.path.basename(save_path)} on your desktop"
            }
        else:
            return {
                "success": False,
                "message": "Screenshot was taken but file was not saved correctly"
            }
    except Exception as e:
        return {"success": False, "message": f"Screenshot failed: {str(e)}"}


def lock_screen() -> dict:
    """Lock the Windows workstation."""
    try:
        ctypes.windll.user32.LockWorkStation()
        return {"success": True, "message": "Screen locked."}
    except Exception as e:
        return {"success": False, "message": f"Failed to lock screen: {e}"}


def get_current_time() -> dict:
    """Return the current local time."""
    try:
        now = datetime.now()
        time_str = now.strftime("%I:%M %p")
        return {"success": True, "time": time_str}
    except Exception as e:
        return {"success": False, "message": f"Failed to get time: {e}"}


def get_current_date() -> dict:
    """Return the current local date in a human-readable format."""
    try:
        now = datetime.now()
        day = now.strftime("%d").lstrip("0") or "0"
        date_str = now.strftime(f"%A, %B {day}, %Y")
        return {"success": True, "date": date_str}
    except Exception as e:
        return {"success": False, "message": f"Failed to get date: {e}"}


MAX_RESULTS = 20


def _fuzzy_match_file(query: str, filename: str, fullpath: str = "") -> bool:
    """Smart filename matching that ignores spoken filler words."""
    q = query.lower()
    f = filename.lower()
    p = fullpath.lower() if fullpath else f
    
    if q in f:
        return True
        
    # Strip out spoken words that users add naturally
    stop_words = {"project", "file", "document", "video", "audio", "image", "the", "my", "a", "an", "folder", "in", "on", "at", "inside", "of", "from"}
    q_clean = re.sub(r'[^\w\s]', ' ', q)
    
    q_words = [w for w in q_clean.split() if w not in stop_words and len(w) > 1]
    
    if not q_words:
        # Fallback if query was literally just "project" or similar
        q_words = [w for w in q_clean.split() if len(w) > 1]
        
    if not q_words:
        return False
        
    # All keywords must be in the full path, and at least one must hit the actual filename
    return all(w in p for w in q_words) and any(w in f for w in q_words)


def search_files(query: str) -> dict:
    """Search for files on Desktop and in Documents matching the query."""
    try:
        search_dirs = [
            Path.home(),
            Path.home() / "Desktop",
            Path.home() / "Documents",
            Path.home() / "Downloads",
            Path.home() / "Music",
            Path.home() / "Videos",
            Path.home() / "Pictures",
        ]
        query_lower = query.strip().lower()
        found = []

        home = Path.home()
        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
            iterator = search_dir.glob("*") if search_dir == home else search_dir.rglob("*")
            for item in iterator:
                if _fuzzy_match_file(query_lower, item.name, str(item)):
                    found.append(str(item))
                    if len(found) >= MAX_RESULTS:
                        break
            if len(found) >= MAX_RESULTS:
                break

        if found:
            return {"success": True, "message": f"Found {len(found)} file(s).", "files": found[:MAX_RESULTS]}
        else:
            return {"success": False, "message": f"No files found matching '{query}'.", "files": []}
    except Exception as e:
        return {"success": False, "message": f"File search failed: {e}"}


def type_text(text: str) -> dict:
    """Type text into the focused window using a clipboard-paste approach."""
    try:
        try:
            old_clipboard = pyperclip.paste()
        except Exception:
            old_clipboard = ""

        pyperclip.copy(text)
        time.sleep(0.1)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.1)

        try:
            pyperclip.copy(old_clipboard)
        except Exception:
            pass

        return {"success": True, "message": f"Typed text successfully."}
    except Exception as e:
        return {"success": False, "message": f"Failed to type text: {e}"}


def copy_to_clipboard(text: str) -> dict:
    """Copy text to the system clipboard."""
    try:
        pyperclip.copy(text)
        preview = text[:60] + ("..." if len(text) > 60 else "")
        return {"success": True, "message": f"Copied to clipboard: '{preview}'"}
    except Exception as e:
        return {"success": False, "message": f"Failed to copy to clipboard: {e}"}


_CMD_BLOCKLIST = [
    "rm -rf", "rmdir /s", "format ", "shutdown", "del /f", "rd /s",
    ":(){:|:&};:", "mkfs", "dd if=", "wget http", "curl http",
    "reg delete", "bcdedit", "diskpart", "cipher /w",
]


def _is_safe_command(cmd: str) -> bool:
    cmd_lower = cmd.lower()
    return not any(blocked in cmd_lower for blocked in _CMD_BLOCKLIST)


def _generate_command_with_ai(task_description: str) -> str | None:
    """Ask Gemini to generate a safe Windows CMD command for the task."""
    import os
    from backend.gemini_client import call_task_model, extract_text, AllModelsExhaustedError

    api_key = os.getenv("GOOGLE_AI_STUDIO_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    prompt = f"""Generate a single safe Windows CMD command for this task: {task_description}

Rules:
- Output ONLY the command, nothing else.
- No destructive operations (delete, format, shutdown).
- Use built-in Windows commands or common tools.
- If the task cannot be done safely with a single command, output: UNSAFE"""

    try:
        contents = [{"parts": [{"text": prompt}]}]
        resp_json = call_task_model(contents, api_key=api_key, timeout=8)
        cmd = extract_text(resp_json).strip()
        if cmd and cmd != "UNSAFE" and _is_safe_command(cmd):
            return cmd
    except AllModelsExhaustedError:
        print("[pc_control] All task models exhausted for command generation.")
    except Exception as e:
        print(f"[pc_control] AI command generation failed: {e}")
    return None


def _try_direct_python(task_description: str) -> dict | None:
    """Handle common file/folder operations directly with Python.
    Returns a result dict on success, None if this task needs AI generation."""
    import re

    task_lower = task_description.lower()

    # CREATE FOLDER
    if "create" in task_lower and "folder" in task_lower:
        name_match = re.search(
            r"(?:called|named|folder)\s+['\"]?([a-zA-Z0-9 _\-\.]+?)['\"]?"
            r"(?:\s+on|\s+at|\s+in|\s*$)",
            task_lower
        )
        if not name_match:
            # Fallback: grab last quoted or word sequence after 'folder'
            name_match = re.search(r"folder\s+['\"]?([a-zA-Z0-9 _\-\.]+)['\"]?", task_lower)
        if name_match:
            folder_name = name_match.group(1).strip()
            # Determine location
            if "download" in task_lower:
                base = DOWNLOADS
            elif "document" in task_lower:
                base = DOCUMENTS
            else:
                base = DESKTOP
            folder_path = os.path.join(base, folder_name)
            os.makedirs(folder_path, exist_ok=True)
            if os.path.exists(folder_path):
                return {"success": True, "message": f"Created folder '{folder_name}' at {folder_path}"}

    # CREATE FILE
    if "create" in task_lower and any(
        ext in task_lower for ext in (".py", ".html", ".txt", ".js", ".css", ".json", ".md")
    ):
        file_match = re.search(
            r"(?:called|named|file)\s+['\"]?([a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+)['\"]?",
            task_lower
        )
        if file_match:
            filename = file_match.group(1).strip()
            if "download" in task_lower:
                base = DOWNLOADS
            elif "document" in task_lower:
                base = DOCUMENTS
            else:
                base = DESKTOP
            file_path = os.path.join(base, filename)
            if filename.endswith(".py"):
                content = 'print("hello world")\n'
            elif filename.endswith(".html"):
                content = "<!DOCTYPE html>\n<html>\n<body>\n<h1>Hello World</h1>\n</body>\n</html>\n"
            else:
                content = ""
            os.makedirs(os.path.dirname(file_path), exist_ok=True) if os.path.dirname(file_path) else None
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            if os.path.exists(file_path):
                return {"success": True, "message": f"Created file '{filename}' at {file_path}"}

    return None


def run_terminal_command(command: str = "", task_description: str = "") -> dict:
    """Run a Windows CMD command."""
    try:
        if not command.strip() and task_description.strip():
            # FIX 2: Try direct Python first for common operations — avoids AI call
            direct = _try_direct_python(task_description)
            if direct is not None:
                return direct
            generated = _generate_command_with_ai(task_description)
            if not generated:
                return {"success": False, "message": f"Could not generate a safe command for: {task_description}"}
            command = generated

        if not command.strip():
            return {"success": False, "message": "No command provided."}

        if not _is_safe_command(command):
            return {"success": False, "message": f"Command blocked for safety: '{command}'"}

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace",
        )
        output = (result.stdout or "").strip()
        error = (result.stderr or "").strip()

        if result.returncode == 0:
            return {
                "success": True,
                "command": command,
                "output": output[:2000] if output else "(no output)",
            }
        else:
            return {
                "success": False,
                "command": command,
                "message": error[:500] if error else f"Exit code {result.returncode}",
            }

    except subprocess.TimeoutExpired:
        return {"success": False, "message": "Command timed out after 30 seconds."}
    except Exception as e:
        return {"success": False, "message": f"Command execution failed: {e}"}


_TYPE_FOLDERS = {
    "Images":    {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico", ".tiff"},
    "Videos":    {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"},
    "Audio":     {".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a"},
    "Documents": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".odt", ".rtf"},
    "Archives":  {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"},
    "Code":      {".py", ".js", ".ts", ".html", ".css", ".json", ".xml", ".sh", ".bat", ".ps1", ".java", ".cpp", ".c", ".h"},
    "Other":     set(),
}


def organize_desktop(mode: str = "type") -> dict:
    """Organize desktop files into subfolders."""
    try:
        desktop = Path.home() / "Desktop"
        moved = 0
        errors = []

        for item in desktop.iterdir():
            if item.is_dir():
                continue

            if mode == "type":
                suffix = item.suffix.lower()
                target_folder = "Other"
                for folder_name, extensions in _TYPE_FOLDERS.items():
                    if suffix in extensions:
                        target_folder = folder_name
                        break
                dest_dir = desktop / target_folder

            elif mode == "date":
                mtime = datetime.fromtimestamp(item.stat().st_mtime)
                target_folder = mtime.strftime("%Y-%m")
                dest_dir = desktop / target_folder

            else:
                return {"success": False, "message": f"Unknown mode: {mode}. Use 'type' or 'date'."}

            try:
                dest_dir.mkdir(exist_ok=True)
                dest = dest_dir / item.name
                if dest.exists():
                    stem = item.stem
                    suffix = item.suffix
                    counter = 1
                    while dest.exists():
                        dest = dest_dir / f"{stem}_{counter}{suffix}"
                        counter += 1
                item.rename(dest)
                moved += 1
            except Exception as e:
                errors.append(f"{item.name}: {e}")

        msg = f"Organized {moved} file(s) by {mode}."
        if errors:
            msg += f" {len(errors)} error(s): {'; '.join(errors[:3])}"
        return {"success": True, "message": msg, "moved": moved}

    except Exception as e:
        return {"success": False, "message": f"Desktop organization failed: {e}"}


def clean_desktop() -> dict:
    """Move all desktop files into 'Desktop Archive YYYY-MM-DD' folder."""
    try:
        desktop = Path.home() / "Desktop"
        archive_name = f"Desktop Archive {datetime.now().strftime('%Y-%m-%d')}"
        archive_dir = desktop / archive_name
        archive_dir.mkdir(exist_ok=True)

        moved = 0
        for item in desktop.iterdir():
            if item.is_dir() and item.name == archive_name:
                continue
            if item.is_file():
                dest = archive_dir / item.name
                if dest.exists():
                    stem = item.stem
                    suf = item.suffix
                    counter = 1
                    while dest.exists():
                        dest = archive_dir / f"{stem}_{counter}{suf}"
                        counter += 1
                item.rename(dest)
                moved += 1

        return {"success": True, "message": f"Moved {moved} file(s) to '{archive_name}'."}
    except Exception as e:
        return {"success": False, "message": f"Desktop clean failed: {e}"}


def move_mouse(x: int, y: int) -> dict:
    pyautogui.moveTo(x, y, duration=0.3)
    return {"success": True, "message": f"Moved mouse to {x},{y}"}


def click_mouse(x: int = None, y: int = None, button: str = "left") -> dict:
    if x is not None and y is not None:
        pyautogui.click(x, y, button=button)
    else:
        pyautogui.click(button=button)
    return {"success": True, "message": "Clicked"}


def double_click(x: int = None, y: int = None) -> dict:
    if x is not None and y is not None:
        pyautogui.doubleClick(x, y)
    else:
        pyautogui.doubleClick()
    return {"success": True, "message": "Double clicked"}


def press_key(key: str) -> dict:
    pyautogui.press(key)
    return {"success": True, "message": f"Pressed {key}"}


def hotkey(*keys) -> dict:
    pyautogui.hotkey(*keys)
    return {"success": True, "message": f"Hotkey {keys}"}


def type_text_slow(text: str) -> dict:
    pyautogui.write(text, interval=0.05)
    return {"success": True, "message": "Typed"}


def take_screenshot_and_analyze() -> dict:
    """Take a screenshot and analyze it with Gemini Vision. Returns text description."""
    from backend.vision import analyze_screen
    return analyze_screen("Describe everything visible on screen in detail. List any buttons, text, dialogs, and UI elements.")


_STEAM_GAME_IDS = {
    # The Big Three / Essentials
    "pubg": "578080",
    "playerunknown": "578080",
    "cs2": "730",
    "counter strike": "730",
    "csgo": "730",
    "dota": "570",
    "dota 2": "570",

    # Massive Multiplayer & Shooters
    "apex": "1172470",
    "apex legends": "1172470",
    "destiny 2": "1085660",
    "warframe": "230410",
    "tf2": "440",
    "team fortress 2": "440",
    "rust": "252490",
    "rainbow six siege": "359550",
    "r6": "359550",
    "war thunder": "236390",
    "helldivers 2": "553850",
    "deadlock": "1422450",

    # Open World & RPGs
    "gta5": "271590",
    "gta v": "271590",
    "grand theft auto v": "271590",
    "rdr2": "1174180",
    "red dead redemption 2": "1174180",
    "cyberpunk": "1091500",
    "cyberpunk 2077": "1091500",
    "elden ring": "1245620",
    "baldurs gate 3": "1086940",
    "bg3": "1086940",
    "starfield": "1716740",
    "the witcher 3": "292030",
    "witcher 3": "292030",
    "skyrim": "489830",
    "monster hunter wilds": "2246340",

    # Survival & Simulation
    "palworld": "1623730",
    "stardew valley": "413150",
    "stardew": "413150",
    "terraria": "105600",
    "lethal company": "1966720",
    "ark survival ascended": "237850",
    "ark": "237850",
    "sons of the forest": "1326420",
    "valheim": "892970",
    "satisfactory": "526870",
    "euro truck simulator 2": "227300",
    "ets2": "227300",

    # Strategy & Indies
    "civ 6": "289070",
    "civilization vi": "289070",
    "balatro": "2379780",
    "hollow knight": "367520",
    "slay the spire": "588650",
    "slay the spire 2": "3062950",
    "manor lords": "1363080",
    "hearts of iron iv": "394360",
    "hoi4": "394360",

    # Valve Classics & Tools
    "garrys mod": "4000",
    "gmod": "4000",
    "left 4 dead 2": "550",
    "l4d2": "550",
    "portal 2": "620",
    "wallpaper engine": "431960",
}


def launch_steam_game(game_name: str) -> dict:
    """Launch a Steam game using the Steam URI protocol."""
    game_lower = game_name.lower()
    app_id = None
    for key, gid in _STEAM_GAME_IDS.items():
        if key in game_lower:
            app_id = gid
            break

    if app_id:
        subprocess.Popen(["cmd", "/c", "start", f"steam://rungameid/{app_id}"], shell=True)
        return {"success": True, "message": f"Launching {game_name}"}
    else:
        subprocess.Popen(["cmd", "/c", "start", f"steam://search/{game_name}"], shell=True)
        return {"success": True, "message": f"Opened Steam search for {game_name}"}


def _click_steam_install_button(game_name: str) -> None:
    """
    Wait for the Steam 'Installer' dialog window, then click the Install button.
    Uses the live window rect so it works on any screen size.

    Steam's window rect includes invisible DWM shadow padding, so the visible
    dialog content doesn't start at (left, top). The Install button reliably
    sits at 36% across and 90% down the raw window rect on all tested resolutions.
    """
    import win32gui

    DIALOG_TITLES = {"installer", "install", "installieren", "instalar",
                     "インストール", "установка"}
    game_lower = game_name.lower()

    # Wait up to 60 seconds for slow PCs where Steam takes longer to boot
    deadline = time.time() + 60
    while time.time() < deadline:
        time.sleep(1.0)
        try:
            hwnd = None

            def _cb(h, _):
                nonlocal hwnd
                if hwnd is not None:
                    return
                if not win32gui.IsWindowVisible(h):
                    return
                title = win32gui.GetWindowText(h).strip().lower()
                if title == "steam" or title.endswith(" - steam"):
                    return
                if any(dt in title for dt in DIALOG_TITLES) or game_lower in title:
                    hwnd = h

            win32gui.EnumWindows(_cb, None)

            if hwnd:
                left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                w = right - left
                h = bottom - top
                print(f"[Steam] Dialog rect: ({left},{top}) {w}×{h}")

                # Give slow PCs an extra 2 seconds to actually paint the window contents
                time.sleep(2.0)

                try:
                    win32gui.ShowWindow(hwnd, 9)  # SW_RESTORE
                    import pyautogui
                    pyautogui.press('alt') # Bypass Windows foreground lock
                    win32gui.SetForegroundWindow(hwnd)
                except Exception as e:
                    print(f"[Steam] Focus warning: {e}")
                time.sleep(0.4)

                # Install button: 36% from left, 90% from top of the raw window rect.
                # Verified against live rect (662,248,1259,778) → button at (877,724).
                btn_x = left + int(w * 0.36)
                btn_y = top  + int(h * 0.90)
                print(f"[Steam] Clicking at ({btn_x}, {btn_y})")
                pyautogui.moveTo(btn_x, btn_y, duration=0.2)
                time.sleep(0.1)
                pyautogui.click(btn_x, btn_y)
                
                # Fallback: if the pixel click missed because of resolution scaling,
                # pressing Enter natively triggers the focused default "Install" button.
                time.sleep(0.2)
                pyautogui.press('enter')
                return
        except Exception as e:
            print(f"[Steam] error: {e}")

    print("[Steam] Timed out — sending Enter as fallback")
    pyautogui.press('enter')


def download_steam_game(game_name: str) -> dict:
    """Open the Steam install dialog for a game and auto-confirm it."""
    game_lower = game_name.lower()
    app_id = None
    for key, gid in _STEAM_GAME_IDS.items():
        if key in game_lower:
            app_id = gid
            break

    if app_id:
        subprocess.Popen(["cmd", "/c", "start", f"steam://install/{app_id}"], shell=True)
        try:
            import threading
            threading.Thread(target=_click_steam_install_button, args=(game_name,), daemon=True).start()
        except Exception as e:
            print(f"[Steam] Background thread failed: {e}")
        return {"success": True, "message": f"Opening Steam install for {game_name} and confirming the download."}
    else:
        return {"success": False, "message": f"Game ID not found for {game_name}. Opening Steam so you can search manually."}


def set_reminder(message: str, minutes: int = None, time_str: str = None, date_str: str = None) -> dict:
    """Set a reminder using a background thread. Shows a Windows toast notification. No admin needed."""
    import threading
    from datetime import timedelta

    try:
        now = datetime.now()
        if minutes is not None:
            seconds = minutes * 60
            remind_time = now + timedelta(minutes=minutes)
        elif time_str and date_str:
            target = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            seconds = (target - now).total_seconds()
            remind_time = target
        elif time_str:
            today = now.strftime("%Y-%m-%d")
            target = datetime.strptime(f"{today} {time_str}", "%Y-%m-%d %H:%M")
            if target < now:
                target += timedelta(days=1)
            seconds = (target - now).total_seconds()
            remind_time = target
        else:
            return {"success": False, "message": "Need time or minutes"}

        if seconds <= 0:
            return {"success": False, "message": "That time is in the past"}

        def show_reminder():
            time.sleep(seconds)
            try:
                from win10toast import ToastNotifier
                ToastNotifier().show_toast("Ame Reminder", message, duration=15, threaded=True)
            except Exception:
                ps_cmd = f'''
                Add-Type -AssemblyName System.Windows.Forms
                $n = New-Object System.Windows.Forms.NotifyIcon
                $n.Icon = [System.Drawing.SystemIcons]::Information
                $n.Visible = $true
                $n.ShowBalloonTip(10000, "Ame Reminder", "{message}", [System.Windows.Forms.ToolTipIcon]::Info)
                Start-Sleep 10
                $n.Dispose()
                '''
                subprocess.Popen(["powershell", "-WindowStyle", "Hidden", "-Command", ps_cmd])

        threading.Thread(target=show_reminder, daemon=True).start()
        time_formatted = remind_time.strftime("%I:%M %p")
        return {"success": True, "message": f"Reminder set for {time_formatted}: {message}"}

    except Exception as e:
        return {"success": False, "message": f"Reminder failed: {e}"}


def list_desktop() -> dict:
    """List everything on the desktop with file sizes."""
    try:
        desktop = Path.home() / "Desktop"
        items = []
        for item in sorted(desktop.iterdir(), key=lambda x: x.name.lower()):
            try:
                if item.is_dir():
                    size_str = "folder"
                else:
                    size = item.stat().st_size
                    if size < 1024:
                        size_str = f"{size} B"
                    elif size < 1024 * 1024:
                        size_str = f"{size / 1024:.1f} KB"
                    else:
                        size_str = f"{size / (1024*1024):.1f} MB"
                items.append({"name": item.name, "size": size_str, "type": "folder" if item.is_dir() else "file"})
            except Exception:
                continue

        return {"success": True, "count": len(items), "items": items}
    except Exception as e:
        return {"success": False, "message": f"Could not list desktop: {e}"}
