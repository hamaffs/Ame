"""
AMÉ Code Analyzer — reads project files and builds context for Gemini.
Called by AMÉ's tool handler when the user asks about code.
"""

from __future__ import annotations
import os
from pathlib import Path

from backend import path_guard as _path_guard


_MAX_FILE_CHARS = 6000      # ~1500 tokens per file
_MAX_PROJECT_CHARS = 18000  # ~4500 tokens total for the project view


class CodeAnalyzer:
    def __init__(self, watcher):
        self.watcher = watcher

    def analyze(self, project_name: str | None = None) -> dict:
        """Return a structured digest of the project's interesting files."""
        try:
            projects = self.watcher.get_all_projects() if self.watcher else []
        except Exception as e:
            return {"success": False, "error": f"watcher unavailable: {e}"}

        if not projects:
            return {"success": False, "error": "no projects indexed yet"}

        if project_name:
            project = next((p for p in projects if p.get("name", "").lower() == project_name.lower()), None)
            if not project:
                return {"success": False, "error": f"project '{project_name}' not found"}
        else:
            # Most recently active project
            project = max(projects, key=lambda p: p.get("last_seen", 0))

        files = project.get("files", {})
        digest: list[str] = [f"# Project: {project.get('name', 'unknown')}",
                             f"# Root: {project.get('root', '?')}",
                             f"# Files indexed: {len(files)}", ""]
        used = 0
        for fname, fpath in files.items():
            ok, _ = _path_guard.is_allowed(fpath, mode="read")
            if not ok:
                continue
            content = self.read_file(fpath, _silent=True)
            if not content or not isinstance(content, str):
                continue
            section = f"\n--- {fname} ---\n{content[:_MAX_FILE_CHARS]}\n"
            if used + len(section) > _MAX_PROJECT_CHARS:
                digest.append("\n[…truncated to stay within context budget]")
                break
            digest.append(section)
            used += len(section)
        return {
            "success": True,
            "project": project.get("name"),
            "root": project.get("root"),
            "context": "\n".join(digest),
            "files_used": len([d for d in digest if d.startswith("\n--- ")]),
        }

    def read_file(self, filepath: str, _silent: bool = False) -> str:
        """Read a single file with path-guard checks. Returns "" on refusal/error."""
        guard = _path_guard.guard_or_error(filepath, mode="read")
        if guard is not None:
            return "" if _silent else f"[Refused: {guard.get('reason', 'guarded')}]"
        try:
            p = Path(filepath).expanduser()
            if not p.exists() or not p.is_file():
                return "" if _silent else f"[Not a file: {filepath}]"
            with p.open("r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception as e:
            return "" if _silent else f"[Read failed: {e}]"
