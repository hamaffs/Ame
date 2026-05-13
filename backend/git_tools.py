"""
Amé Git Tools — strictly read-only git operations.

No commits, no pushes, no destructive operations.
Only status, log, diff, and branch listing.
"""

from __future__ import annotations
import os
import subprocess

_ALLOWED_COMMANDS = {
    "git_status":   ["git", "status", "--porcelain", "-b"],
    "git_log":      ["git", "log", "--oneline", "--no-color", "-n", "20"],
    "git_diff":     ["git", "diff", "--stat", "--no-color"],
    "git_branches": ["git", "branch", "-a", "--no-color"],
}


def run_git_tool(tool_name: str, params: dict | None = None) -> dict:
    """Execute a read-only git command. Returns structured result."""
    params = params or {}
    if tool_name not in _ALLOWED_COMMANDS:
        return {"success": False, "error": f"Unknown git tool: {tool_name}"}

    path = params.get("path", "")
    if not path or not os.path.isdir(path):
        return {"success": False, "error": f"Invalid directory: {path}"}

    # Verify it's actually a git repo before invoking the real command.
    check = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        cwd=path, capture_output=True, text=True, timeout=5,
    )
    if check.returncode != 0:
        return {"success": False, "error": f"Not a git repository: {path}"}

    try:
        result = subprocess.run(
            _ALLOWED_COMMANDS[tool_name],
            cwd=path, capture_output=True, text=True, timeout=10,
        )
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "git command timed out"}
    except Exception as e:
        return {"success": False, "error": f"git failed: {e}"}

    return {
        "success": result.returncode == 0,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "code": result.returncode,
    }
