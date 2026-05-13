"""
AME Code Watcher — scans the entire machine for code projects,
indexes them, and watches for file changes in real time.
Runs as a background thread from server startup.
"""

import sys, os
os.environ.setdefault('PYTHONUTF8', '1')
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'): sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import fnmatch
import queue as stdlib_queue
import threading
import time
from pathlib import Path

# ---------- Constants ----------

PROJECT_MARKERS = {
    # Code / Dev
    'package.json', 'requirements.txt', 'Pipfile', 'pyproject.toml',
    'Makefile', 'CMakeLists.txt', 'Cargo.toml', 'go.mod', 'pom.xml',
    'build.gradle', 'composer.json', '*.sln', '*.xcodeproj', '*.xcworkspace',
    'Gemfile', 'mix.exs', 'pubspec.yaml', 'setup.py', 'setup.cfg', '.git',

    # Adobe Creative Suite
    '*.aep',      # After Effects
    '*.prproj',   # Premiere Pro
    '*.psd',      # Photoshop
    '*.ai',       # Illustrator
    '*.indd',     # InDesign
    '*.xd',       # Adobe XD
    '*.aup3',     # Audition
    '*.sesx',     # Audition session

    # Video / Motion
    '*.drp',      # DaVinci Resolve project
    '*.fcpx',     # Final Cut Pro
    '*.veg',      # Vegas Pro
    '*.kdenlive', # Kdenlive

    # 3D / Engineering / Architecture
    '*.blend',    # Blender
    '*.c4d',      # Cinema 4D
    '*.max',      # 3ds Max
    '*.ma', '*.mb',  # Maya
    '*.fbx',      # FBX scene
    '*.skp',      # SketchUp
    '*.rvt',      # Revit
    '*.dwg',      # AutoCAD
    '*.f3d',      # Fusion 360
    '*.step', '*.stp',  # CAD files

    # TouchDesigner / Creative Coding
    '*.toe',      # TouchDesigner
    '*.pd',       # Pure Data
    '*.maxpat',   # Max/MSP patch

    # Music / Audio Production
    '*.als',      # Ableton Live
    '*.flp',      # FL Studio
    '*.ptx',      # Pro Tools
    '*.logic',    # Logic Pro
    '*.reason',   # Reason
    '*.band',     # GarageBand

    # Game Development
    'project.godot',   # Godot
    '*.uproject',      # Unreal Engine
    'Assets',          # Unity (folder marker — handled separately)

    # Design / UI
    '*.fig',      # Figma (local)
    '*.sketch',   # Sketch

    # Data / AI / Notebooks
    '*.ipynb',    # Jupyter notebook
}

# Glob-style markers (*.sln etc) — separated for matching
_GLOB_MARKERS = {m for m in PROJECT_MARKERS if '*' in m}
_EXACT_MARKERS = PROJECT_MARKERS - _GLOB_MARKERS

SKIP_DIRS = {
    # Dev / build noise
    'node_modules', '.git', '__pycache__', '.venv', 'venv', 'env',
    '.env', 'dist', 'build', 'target', '.cache', '.npm', '.yarn',
    'site-packages', 'lib', 'include', 'bin', 'obj',
    '.nuget', '.dotnet', 'anaconda3', 'miniconda3',
    # Linux user-cache / runtime
    '.local/share/trash', '.local/share/keyrings', '.local/share/flatpak',
    'snap', '.flatpak', '.steam', '.thunderbird', '.mozilla',
    '.config/google-chrome', '.config/chromium', '.config/microsoft',
    'cache', 'caches', 'crashpad', 'crashreports', 'logs',
    'extensions', 'databases', 'localstorage', 'sessionstorage',
    'gpucache', 'code cache', 'snapshots', 'blob_storage',
    'temp', 'tmp',
    # Browser / app internals
    'microsoft', 'nvidia', 'intel', 'amd', 'google', 'mozilla',
    'packages', 'history', 'cookies',
    # Downloaded toolchains that aren't user projects
    'ffmpeg', 'node', 'npm',
}

INDEXABLE_EXTENSIONS = {
    '.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.scss',
    '.json', '.yaml', '.yml', '.toml', '.md', '.txt', '.sh', '.bat',
    '.ps1', '.c', '.cpp', '.h', '.hpp', '.cs', '.java', '.go', '.rs',
    '.rb', '.php', '.swift', '.kt', '.vue', '.svelte', '.sql',
    # Creative project files
    '.prproj', '.prin',   # Premiere Pro
    '.aep', '.aet',       # After Effects
    '.psd', '.psb',       # Photoshop
    '.ai', '.eps',        # Illustrator
    '.indd', '.idml',     # InDesign
    '.xd',                # Adobe XD
    '.sesx', '.aup3',     # Audition
    '.drp',               # DaVinci Resolve
    '.blend', '.blend1',  # Blender
    '.c4d',               # Cinema 4D
    '.ma', '.mb',         # Maya
    '.max',               # 3ds Max
    '.fbx', '.obj', '.gltf', '.glb',  # 3D files
    '.skp',               # SketchUp
    '.toe',               # TouchDesigner
    '.als',               # Ableton Live
    '.flp',               # FL Studio
    '.logic', '.band',    # Logic/GarageBand
    '.ptx',               # Pro Tools
    '.godot',             # Godot
    '.uproject',          # Unreal Engine
    '.ipynb',             # Jupyter
    '.fig',               # Figma
    '.sketch',            # Sketch
    '.dwg', '.dxf',       # AutoCAD
    '.f3d', '.step', '.stp',  # Fusion/CAD
}

# Also index these exact filenames regardless of extension
_INDEXABLE_NAMES = {
    '.env.example', '.gitignore', 'dockerfile', 'Dockerfile',
}

MAX_FILE_SIZE = 500 * 1024   # 500KB
MAX_FILES_PER_PROJECT = 500

# ---------- Helpers ----------


def _should_skip_dir(name: str) -> bool:
    return name.lower() in SKIP_DIRS or name.startswith('.')


def _is_project_dir(path: Path) -> bool:
    """Check if a directory contains a project marker."""
    try:
        entries = {e.name for e in path.iterdir()}
    except (PermissionError, OSError):
        return False

    # Exact matches
    if entries & _EXACT_MARKERS:
        return True

    # Glob matches (*.sln etc)
    for entry_name in entries:
        for pattern in _GLOB_MARKERS:
            if fnmatch.fnmatch(entry_name, pattern):
                return True
    return False


def _detect_project_type(path: Path) -> str:
    """Detect the primary language/framework of a project."""
    try:
        names = {e.name for e in path.iterdir()}
    except (PermissionError, OSError):
        return "unknown"

    if 'package.json' in names:
        return 'node'
    if any(n in names for n in ('requirements.txt', 'pyproject.toml', 'setup.py', 'Pipfile')):
        return 'python'
    if 'Cargo.toml' in names:
        return 'rust'
    if 'go.mod' in names:
        return 'go'
    if any(fnmatch.fnmatch(n, '*.sln') or fnmatch.fnmatch(n, '*.csproj') for n in names):
        return 'dotnet'
    if any(n in names for n in ('pom.xml', 'build.gradle')):
        return 'java'
    return 'unknown'


def _is_indexable(path: Path) -> bool:
    """Check if a file should be indexed."""
    if path.name in _INDEXABLE_NAMES:
        return True
    return path.suffix.lower() in INDEXABLE_EXTENSIONS


# ---------- CodeWatcher ----------


class CodeWatcher:
    """Background thread that scans the machine for code projects and watches for changes."""

    def __init__(self):
        self._index: dict = {}  # project_name_lower -> ProjectEntry dict
        self._lock = threading.Lock()
        self._running = False
        self._scan_thread: threading.Thread = None
        self._observer = None  # watchdog observer
        self._first_run_delivered = False
        self._first_run_summary: str = None
        self._active = False  # True when user is actively talking
        self._pause_scan = False
        
        self._embed_queue = stdlib_queue.Queue()
        self._sast_queue = stdlib_queue.Queue()
        self._chroma_client = None
        self._code_collection = None

    def start(self) -> None:
        """Start background scan and file watcher. Non-blocking."""
        if self._running:
            return
        self._running = True
        self._scan_thread = threading.Thread(
            target=self._scan_worker,
            daemon=True,
            name="code-watcher-scan",
        )
        self._scan_thread.start()
        
        self._rag_thread = threading.Thread(
            target=self._rag_worker,
            daemon=True,
            name="code-rag-worker",
        )
        self._rag_thread.start()
        
        self._sast_thread = threading.Thread(
            target=self._sast_worker,
            daemon=True,
            name="code-sast-worker",
        )
        self._sast_thread.start()
        print("[CodeWatcher] Started background scan")

    def stop(self) -> None:
        """Stop all background threads cleanly."""
        self._running = False
        if self._observer:
            try:
                self._observer.stop()
                self._observer.join(timeout=3)
            except Exception:
                pass
            self._observer = None
        self._embed_queue.put(None) # Signal RAG thread to exit
        self._sast_queue.put(None)  # Signal SAST thread to exit
        print("[CodeWatcher] Stopped")

    def mark_activity(self) -> None:
        """Called when user is actively talking — pause heavy background scans."""
        self._pause_scan = True

    def get_project(self, name: str) -> dict | None:
        """Find a project by name. Fuzzy match."""
        if not name:
            return None
        name_lower = name.lower().strip()

        with self._lock:
            # Exact match
            if name_lower in self._index:
                return dict(self._index[name_lower])

            # Substring match
            for key, entry in self._index.items():
                if name_lower in key or key in name_lower:
                    return dict(entry)

            # Word match — "ame project" matches "ame"
            words = name_lower.split()
            for word in words:
                if word in self._index:
                    return dict(self._index[word])
                for key in self._index:
                    if word in key:
                        return dict(self._index[key])

        return None

    def get_all_projects(self) -> list[dict]:
        """Return all indexed projects sorted by last_modified descending."""
        with self._lock:
            projects = list(self._index.values())
        projects.sort(key=lambda p: p.get('last_modified', 0), reverse=True)
        return projects

    def find_file(self, filename: str) -> list[dict]:
        """Find a file by name across all projects. Fuzzy, case-insensitive, stem-aware."""
        filename_lower = filename.lower()
        query_stem = Path(filename).stem.lower()  # 'app' from 'app.py'
        results = []

        with self._lock:
            for entry in self._index.values():
                for fname, fpath in entry.get('files', {}).items():
                    fname_lower = fname.lower()
                    fname_stem = Path(fname).stem.lower()
                    # Match if: full name contains query, or stem contains query stem
                    if filename_lower in fname_lower or query_stem in fname_stem:
                        results.append({
                            'project': entry['name'],
                            'path': fpath,
                        })

        # Sort: exact name match > exact stem match > contains match > alphabetical
        def _sort_key(r):
            rname = Path(r['path']).name.lower()
            rstem = Path(r['path']).stem.lower()
            if rname == filename_lower:
                return (0, rname)
            if rstem == query_stem:
                return (1, rname)
            return (2, rname)

        results.sort(key=_sort_key)
        return results

    def semantic_search(self, query: str, n_results: int = 5) -> list[dict]:
        """Search across all indexed code projects by meaning using ChromaDB."""
        if not self._code_collection:
            return []
        try:
            res = self._code_collection.query(
                query_texts=[query],
                n_results=n_results
            )
            out = []
            if res and res["documents"] and res["documents"][0]:
                for fpath, doc, meta in zip(res["ids"][0], res["documents"][0], res["metadatas"][0]):
                    out.append({
                        "path": fpath,
                        "project": meta.get("project", "unknown"),
                        "content_preview": doc[:300] + "..." if len(doc) > 300 else doc
                    })
            return out
        except Exception as e:
            print(f"[CodeWatcher] Semantic search error: {e}")
            return []

    def get_file_content(self, file_path: str) -> str | None:
        """Read and return file content. Returns None if not found or too large."""
        try:
            p = Path(file_path)
            if not p.exists() or not p.is_file():
                return None
            if p.stat().st_size > MAX_FILE_SIZE:
                return None
            return p.read_text(encoding='utf-8', errors='replace')
        except (PermissionError, OSError, UnicodeDecodeError):
            return None

    def get_first_run_summary(self) -> str | None:
        """Returns a one-time summary string on first scan completion."""
        if self._first_run_delivered or self._first_run_summary is None:
            return None
        self._first_run_delivered = True
        return self._first_run_summary

    # ---------- Internal ----------

    def _rag_worker(self):
        """Background thread: consumes files and embeds them into ChromaDB safely."""
        try:
            import chromadb
            db_path = str(Path.home() / ".ame" / "memory" / "code_rag")
            self._chroma_client = chromadb.PersistentClient(path=db_path)
            self._code_collection = self._chroma_client.get_or_create_collection(name="code_index")
        except ImportError:
            print("[CodeWatcher] chromadb not installed — Semantic search disabled.")
            return
        except Exception as e:
            print(f"[CodeWatcher] Failed to init ChromaDB for RAG: {e}")
            return

        while self._running:
            try:
                task = self._embed_queue.get(timeout=1.0)
                if task is None: break
            except stdlib_queue.Empty:
                continue

            fpath = task["path"]
            project = task["project"]
            mtime = task["mtime"]

            try:
                # Check if file is already embedded and up to date
                existing = self._code_collection.get(ids=[fpath], include=["metadatas"])
                if existing and existing["metadatas"] and existing["metadatas"][0]:
                    if existing["metadatas"][0].get("mtime") == mtime:
                        continue  # Already up to date

                content = self.get_file_content(fpath)
                if content:
                    # Index just the first 3000 chars to save CPU/Memory but capture file intent
                    doc = content[:3000]
                    self._code_collection.upsert(ids=[fpath], documents=[doc], metadatas=[{"project": project, "mtime": mtime}])
            except Exception:
                pass
            
            # CRITICAL VOICE PROTECTION: Yield GIL/CPU heavily between embedding files
            time.sleep(0.1)
            
    def _sast_worker(self):
        """Background thread: scans newly saved files for critical security vulnerabilities."""
        import os
        from backend.gemini_client import call_task_model, extract_text
        from backend.server import live_session
        
        last_scanned = {}
        
        while self._running:
            try:
                task = self._sast_queue.get(timeout=1.0)
                if task is None: break
            except stdlib_queue.Empty:
                continue
                
            fpath = task["path"]
            project = task["project"]
            
            # Debounce rapid saves (only scan once every 10 seconds per file)
            now = time.time()
            if fpath in last_scanned and now - last_scanned[fpath] < 10:
                continue
            last_scanned[fpath] = now
            
            # Only scan files most likely to contain secrets or vulnerabilities
            ext = Path(fpath).suffix.lower()
            name = Path(fpath).name.lower()
            valid_exts = {".py", ".js", ".jsx", ".ts", ".tsx", ".php", ".java", ".cs", ".go", ".rs", ".json", ".yaml", ".yml"}
            if ext not in valid_exts and name not in {".env", "config.json", "credentials.json", "secrets.yml"}:
                continue
                
            content = self.get_file_content(fpath)
            if not content or len(content) > 50000:
                continue
                
            prompt = f"""You are a Real-Time SAST Security Scanner.
Review this code file that the user just saved.
File: {name}
Project: {project}

Look ONLY for critical, undeniable security vulnerabilities:
1. Hardcoded API keys, private tokens, or passwords.
2. Blatant SQL injection or command injection vulnerabilities.
3. Exposed secrets in config files.

Do NOT flag missing imports, bad practices, TODOs, or minor linting issues.
If the code is safe or just normal logic, output EXACTLY: SAFE

If there is a CRITICAL vulnerability, output EXACTLY:
VULNERABLE: [Write ONE natural, conversational sentence warning the user about what you found and asking if they want help fixing it.] ||| [Technical details of the exact line, the issue, and the solution to fix it]

Example output:
VULNERABLE: Hey, I noticed you just saved server.py with a hardcoded API key on line 42, want me to help move that to an env file? ||| Hardcoded API key 'sk-12345' found on line 42. Solution: use os.getenv('API_KEY') and add it to .env."""

            try:
                api_key = os.getenv("GOOGLE_AI_STUDIO_KEY") or os.getenv("GEMINI_API_KEY")
                if not api_key: continue
                
                contents = [{"parts": [{"text": prompt + f"\n\nCode:\n{content[:20000]}"}]}]
                resp = call_task_model(contents, api_key=api_key, timeout=10)
                res_text = extract_text(resp).strip()
                
                if res_text.startswith("VULNERABLE:"):
                    import re
                    res_text = res_text[11:].strip()
                    parts = re.split(r'\|\|\|', res_text)
                    spoken = parts[0].strip()
                    hidden = parts[1].strip() if len(parts) > 1 else "No extra details."
                    
                    if live_session and hasattr(live_session, "speak_proactive"):
                        context = f"You just performed a real-time SAST security scan on {name} and warned the user: {spoken}. Technical details: {hidden}"
                        live_session.speak_proactive(spoken, context)
                        print(f"[SAST] Vulnerability found in {name}: {hidden}")
            except Exception as e:
                print(f"[SAST] Scan error on {name}: {e}")
                
            time.sleep(0.5)

    def _scan_worker(self):
        """Background thread: scan drives for projects, then start file watcher."""
        try:
            self._full_scan()
        except Exception as e:
            print(f"[CodeWatcher] Scan error: {e}")

        # Start real-time watcher after initial scan
        self._start_file_watcher()

    def _full_scan(self):
        """Depth-first scan of all drives for project directories."""
        roots = self._get_scan_roots()
        import time as _time
        _scan_start = _time.time()
        _scan_timeout = 20  # seconds
        found_count = 0

        for root in roots:
            if not self._running:
                break
            if _time.time() - _scan_start > _scan_timeout:
                print(f"[CodeWatcher] Scan timeout reached — stopping with {len(self._index)} projects found")
                break
            try:
                self._scan_directory(Path(root), depth=0, max_depth=4)
            except Exception as e:
                print(f"[CodeWatcher] Error scanning {root}: {e}")

        with self._lock:
            found_count = len(self._index)

        print(f"[CodeWatcher] Found {found_count} projects")

        # Build first-run summary
        if found_count > 0:
            with self._lock:
                names = sorted(self._index.values(), key=lambda p: p.get('last_modified', 0), reverse=True)
                top_names = [p['name'] for p in names[:10]]
            names_str = ", ".join(top_names)
            if found_count > 10:
                names_str += f", and {found_count - 10} more"
            self._first_run_summary = f"I found {found_count} projects on your machine — {names_str}."
        else:
            self._first_run_summary = "I didn't find any code projects on your machine yet."

    def _get_scan_roots(self) -> list[str]:
        """Get root directories to scan."""
        roots = []
        home = str(Path.home())

        # Priority locations first
        priority_subdirs = [
            'Desktop', 'Documents', 'Projects', 'repos', 'code',
            'dev', 'workspace', 'src', 'GitHub', 'GitLab',
            'Music', 'Videos', 'Pictures', 'Creative', 'Design',
            'Art', 'Games', '3D', 'Audio', 'Video', 'Production',
        ]
        for subdir in priority_subdirs:
            candidate = os.path.join(home, subdir)
            if os.path.isdir(candidate):
                roots.append(candidate)

        # Home directory itself (low priority; subdirs above are scanned first)
        roots.append(home)

        # Removable + extra mount points on Linux.
        for mount_parent in ("/media", "/mnt", "/run/media"):
            if not os.path.isdir(mount_parent):
                continue
            try:
                for entry in os.listdir(mount_parent):
                    full = os.path.join(mount_parent, entry)
                    if os.path.isdir(full):
                        roots.append(full)
            except OSError:
                continue

        return roots

    def _scan_directory(self, path: Path, depth: int, max_depth: int):
        """Recursively scan a directory for projects."""
        if not self._running:
            return
        if depth > max_depth:
            return

        if _should_skip_dir(path.name) and depth > 0:
            return

        try:
            # Never index the user's home directory itself as a project
            if str(path).lower() == str(Path.home()).lower():
                pass  # scan inside it but don't index it
            elif _is_project_dir(path):
                self._index_project(path)
                # Don't recurse into project subdirectories — they're part of this project
                return
        except (PermissionError, OSError):
            return

        # Recurse into subdirectories
        try:
            subdirs = sorted(path.iterdir(), key=lambda p: p.name.lower())
        except (PermissionError, OSError):
            return

        for subdir in subdirs:
            if not self._running:
                break
            if subdir.is_dir() and not _should_skip_dir(subdir.name):
                try:
                    self._scan_directory(subdir, depth + 1, max_depth)
                except (PermissionError, OSError):
                    continue

    def _index_project(self, path: Path):
        """Index a single project directory."""
        try:
            project_name = path.name
            project_type = _detect_project_type(path)
            
            # Detect version folders (e.g. "25.0", "26.0", "2024", "1.0.0") inside app folders
            # and use the parent app name as the project name instead
            display_name = project_name
            actual_name = project_name
            parent = path.parent
            try:
                first_char = project_name[0] if project_name else ''
                is_version_folder = (
                    first_char.isdigit() and
                    (project_name.replace('.', '').isdigit() or
                     project_name.replace('.', '').replace('-', '').isdigit())
                )
                if is_version_folder:
                    app_name = parent.name  # e.g. "Premiere Pro", "After Effects"
                    actual_name = app_name
                    display_name = app_name
            except Exception:
                pass
                
            files = {}
            last_modified = 0.0

            # Walk the project directory and collect indexable files
            file_list = []
            for root, dirs, filenames in os.walk(str(path)):
                # Skip noise directories
                dirs[:] = [d for d in dirs if not _should_skip_dir(d)]

                for fname in filenames:
                    fpath = Path(root) / fname
                    if _is_indexable(fpath):
                        try:
                            stat = fpath.stat()
                            if stat.st_size <= MAX_FILE_SIZE:
                                file_list.append((str(fpath), fname, stat.st_mtime))
                                # Queue file for semantic embedding
                                self._embed_queue.put({"path": str(fpath), "project": actual_name, "mtime": stat.st_mtime})
                        except (PermissionError, OSError):
                            continue

            # Sort by modification time descending, take top MAX_FILES_PER_PROJECT
            file_list.sort(key=lambda x: x[2], reverse=True)
            file_list = file_list[:MAX_FILES_PER_PROJECT]

            for fpath, fname, mtime in file_list:
                files[fname] = fpath
                if mtime > last_modified:
                    last_modified = mtime

            # Minimum files threshold
            if len(files) < 1:
                return

            # Reject system/app/library paths — not user projects.
            path_str_lower = str(path).lower()
            _reject_path_fragments = [
                'node_modules', 'site-packages',
                '/.cache/', '/.local/share/flatpak/', '/.var/app/',
                '/snap/', '/usr/lib/', '/usr/share/',
                'python3.13', 'python3.12', 'python3.11', 'python3.10',
            ]
            if any(frag in path_str_lower for frag in _reject_path_fragments):
                return

            # Reject if the path IS the Documents or home root directly
            try:
                home = Path.home()
                docs = home / 'Documents'
                if path.resolve() == docs.resolve() or path.resolve() == home.resolve():
                    return
            except Exception:
                pass

            # Reject folders that look like downloaded archives/tools, not user projects
            # A user project has at least one file the user likely created
            # (not just auto-generated or library files)
            name_lower = path.name.lower()
            _tool_patterns = [
                'ffmpeg', 'three.js', 'bootstrap', 'jquery', 'lodash',
                'webpack', 'babel', 'eslint', 'prettier',
            ]
            if any(pat in name_lower for pat in _tool_patterns):
                # Only reject if it has no user-facing entry point
                has_entry = any(f in files for f in [
                    'package.json', 'README.md', 'readme.md',
                    'main.py', 'app.py', 'index.html', 'index.js',
                ])
                if not has_entry:
                    return

            entry = {
                'name': actual_name,
                'display_name': display_name,
                'path': str(path),
                'type': project_type,
                'files': files,
                'last_modified': last_modified,
                'size': len(files),
            }

            with self._lock:
                # If an entry with this app name already exists (e.g. Premiere Pro 25.0 already indexed),
                # merge the files — keep the one with more files
                existing = self._index.get(actual_name.lower())
                if existing:
                    existing_versions = existing.get('versions', [existing['path']])
                    new_path = str(path)
                    if new_path not in existing_versions:
                        existing_versions.append(new_path)
                    existing['versions'] = existing_versions
                    # Keep the entry with more files as the primary
                    if len(files) > existing.get('size', 0):
                        existing['files'] = files
                        existing['size'] = len(files)
                        existing['path'] = str(path)
                else:
                    entry['versions'] = [str(path)]
                    self._index[actual_name.lower()] = entry

        except (PermissionError, OSError) as e:
            pass  # Skip inaccessible directories silently

    def _start_file_watcher(self):
        """Start watchdog observer on all indexed project directories."""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            class _Handler(FileSystemEventHandler):
                def __init__(self, watcher):
                    self._watcher = watcher

                def on_modified(self, event):
                    if not event.is_directory:
                        self._watcher._on_file_changed(event.src_path)

                def on_created(self, event):
                    if not event.is_directory:
                        self._watcher._on_file_changed(event.src_path)

            self._observer = Observer()
            handler = _Handler(self)

            with self._lock:
                paths = [entry['path'] for entry in self._index.values()]

            watched = 0
            skipped = 0
            for project_path in paths:
                try:
                    if not os.path.isdir(project_path):
                        continue
                    # Test if we can actually watch this directory
                    # by checking read+execute permissions
                    if not os.access(project_path, os.R_OK | os.X_OK):
                        skipped += 1
                        continue
                    self._observer.schedule(handler, project_path, recursive=True)
                    watched += 1
                except Exception:
                    skipped += 1
                    continue

            if watched > 0:
                try:
                    self._observer.start()
                    print(f"[CodeWatcher] Watching {watched} projects for real-time changes")
                    if skipped:
                        print(f"[CodeWatcher] Skipped {skipped} protected directories")
                except Exception as e:
                    print(f"[CodeWatcher] File watcher could not start: {e}")
                    self._observer = None
            else:
                print("[CodeWatcher] No watchable project directories found")
                self._observer = None

        except ImportError:
            print("[CodeWatcher] watchdog not installed — real-time watching disabled")
        except Exception as e:
            print(f"[CodeWatcher] File watcher setup error: {e}")

    def _on_file_changed(self, file_path: str):
        """Called when a watched file changes. Update index entry."""
        try:
            p = Path(file_path)
            if not _is_indexable(p):
                return
            # Skip noise paths
            parts_lower = [part.lower() for part in p.parts]
            if any(skip in parts_lower for skip in SKIP_DIRS):
                return

            print(f"[CodeWatcher] File changed: {file_path}")

            # Find which project this file belongs to
            with self._lock:
                for key, entry in self._index.items():
                    if file_path.startswith(entry['path']):
                        entry['files'][p.name] = str(p)
                        entry['last_modified'] = time.time()
                        # Queue file for re-embedding on change
                        self._embed_queue.put({"path": file_path, "project": entry['name'], "mtime": time.time()})
                        # Queue file for real-time security scan
                        self._sast_queue.put({"path": file_path, "project": entry['name']})
                        break
        except Exception:
            pass
