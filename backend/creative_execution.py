"""Creative Execution — Amé builds *with* you.

`creative_soul.py` is the translator. This module is the executor — she
actually drives the user's tools to author the project. Voice "stop" halts
within ~500ms. Every 3-5 actions she pauses, describes the next batch, and
waits for the user to confirm.

Safety rails (non-negotiable):
- File writes stay inside `session.project_dir`. Anything outside is refused.
- No installer launches, asset purchases, or system-setting changes.
- Hard-stop on the global "stop" voice command.
"""

from __future__ import annotations
import asyncio
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class CreativeSession:
    target: str
    project_dir: Path
    plan: list[dict]
    cursor: int = 0
    paused: bool = False
    stopped: bool = False
    speak: Callable[[str], None] | None = None
    request_confirm: Callable[[str, str], "asyncio.Future[bool]"] | None = None
    log: list[dict] = field(default_factory=list)


_active: CreativeSession | None = None
_lock = threading.RLock()


def _set_active(sess: CreativeSession | None) -> None:
    global _active
    with _lock:
        _active = sess


def get_active_session() -> CreativeSession | None:
    """Public read-only accessor — used by live_session to inject 'stop'."""
    with _lock:
        return _active


class SandboxViolation(Exception):
    """Raised when an authoring step tries to escape the project directory."""


def safe_join(project_dir: Path, requested: str) -> Path:
    """Resolve `requested` against `project_dir` and refuse anything outside."""
    pd = project_dir.resolve()
    candidate = pd / requested if not os.path.isabs(requested) else Path(requested)
    resolved = candidate.resolve()
    try:
        resolved.relative_to(pd)
    except ValueError:
        raise SandboxViolation(f"Path escapes project dir: {requested}")
    return resolved


_VALID_KINDS = {"wait", "hotkey", "describe", "open_file", "type_text", "write_file"}
_DESTRUCTIVE_KINDS = {"write_file"}


def normalize_plan(steps: list[dict]) -> list[dict]:
    """Validate + normalize incoming plan. Raises ValueError on bad shapes."""
    if not isinstance(steps, list) or not steps:
        raise ValueError("plan must be a non-empty list")
    out: list[dict] = []
    for i, raw in enumerate(steps):
        if not isinstance(raw, dict) or "kind" not in raw:
            raise ValueError(f"step {i}: not a dict / missing 'kind'")
        kind = raw["kind"]
        if kind not in _VALID_KINDS:
            raise ValueError(f"step {i}: unknown kind '{kind}'")
        step = {"kind": kind}
        if kind == "write_file":
            step["path"]    = str(raw["path"])
            step["content"] = str(raw.get("content", ""))
        elif kind == "open_file":
            step["path"] = str(raw["path"])
        elif kind == "hotkey":
            step["keys"] = list(raw.get("keys") or [])
        elif kind == "type_text":
            step["text"] = str(raw.get("text", ""))
        elif kind == "describe":
            step["text"] = str(raw.get("text", ""))
        elif kind == "wait":
            step["seconds"] = float(raw.get("seconds", 1.0))
        out.append(step)
    return out


def _open_file_native(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def _execute_step(sess: CreativeSession, step: dict) -> dict:
    """Run a single step. Pure-sync so the dispatcher can `to_thread` it."""
    kind = step["kind"]
    if kind == "write_file":
        target = safe_join(sess.project_dir, step["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(step["content"], encoding="utf-8")
        return {"ok": True, "kind": kind, "path": str(target), "bytes": len(step["content"])}
    if kind == "open_file":
        target = safe_join(sess.project_dir, step["path"])
        if not target.exists():
            return {"ok": False, "kind": kind, "error": f"file does not exist: {target}"}
        _open_file_native(target)
        return {"ok": True, "kind": kind, "path": str(target)}
    if kind == "hotkey":
        try:
            import pyautogui  # type: ignore
            pyautogui.hotkey(*step["keys"])
            return {"ok": True, "kind": kind, "keys": step["keys"]}
        except Exception as e:
            return {"ok": False, "kind": kind, "error": str(e)}
    if kind == "type_text":
        try:
            import pyautogui  # type: ignore
            pyautogui.typewrite(step["text"], interval=0.02)
            return {"ok": True, "kind": kind, "chars": len(step["text"])}
        except Exception as e:
            return {"ok": False, "kind": kind, "error": str(e)}
    if kind == "describe":
        if sess.speak:
            try: sess.speak(step["text"])
            except Exception: pass
        return {"ok": True, "kind": kind, "spoken": step["text"]}
    if kind == "wait":
        time.sleep(min(10.0, max(0.0, step["seconds"])))
        return {"ok": True, "kind": kind, "seconds": step["seconds"]}
    return {"ok": False, "kind": kind, "error": "unhandled kind"}


CHECKPOINT_EVERY = 4


def _next_batch(sess: CreativeSession) -> list[dict]:
    return sess.plan[sess.cursor:sess.cursor + CHECKPOINT_EVERY]


def _summarize_batch(batch: list[dict]) -> str:
    """One-line human summary of a batch — shown in the confirm dialog."""
    lines: list[str] = []
    for step in batch:
        k = step["kind"]
        if   k == "write_file": lines.append(f"write {step['path']} ({len(step['content'])} chars)")
        elif k == "open_file":  lines.append(f"open {step['path']}")
        elif k == "hotkey":     lines.append(f"press {'+'.join(step['keys'])}")
        elif k == "type_text":  lines.append(f'type "{step["text"][:40].replace(chr(10), chr(92)+"n")}"')
        elif k == "describe":   lines.append(f"say: {step['text'][:60]}")
        elif k == "wait":       lines.append(f"wait {step['seconds']}s")
    return "\n".join(lines)


async def run_session(sess: CreativeSession) -> dict:
    """Drive the plan to completion, pausing at each checkpoint."""
    log: list[dict] = sess.log
    total = len(sess.plan)
    while sess.cursor < total:
        if sess.stopped:
            return {"success": True, "completed": sess.cursor, "total": total,
                    "stopped": True, "abandoned": False, "log": log}
        while sess.paused and not sess.stopped:
            await asyncio.sleep(0.2)

        batch = _next_batch(sess)
        if not batch:
            break
        if sess.request_confirm:
            try:
                summary = _summarize_batch(batch)
                ok = await sess.request_confirm("Continue?", summary)
                if not ok:
                    return {"success": True, "completed": sess.cursor, "total": total,
                            "stopped": False, "abandoned": True, "log": log}
            except Exception:
                # Confirm flow broke — abandon to be safe.
                return {"success": False, "completed": sess.cursor, "total": total,
                        "stopped": False, "abandoned": True, "log": log,
                        "error": "confirm channel failed"}

        for step in batch:
            if sess.stopped:
                break
            result = await asyncio.to_thread(_execute_step, sess, step)
            log.append(result)
            sess.cursor += 1
            await asyncio.sleep(0.05)

    return {"success": True, "completed": sess.cursor, "total": total,
            "stopped": sess.stopped, "abandoned": False, "log": log}


def creative_execute_plan(target: str,
                          project_dir: str,
                          plan: list[dict],
                          speak: Callable[[str], None] | None = None,
                          request_confirm: Callable[[str, str], "asyncio.Future[bool]"] | None = None) -> CreativeSession:
    """Build the session and return it."""
    if target not in frozenset({"p5js", "shader", "photoshop", "touchdesigner"}):
        raise ValueError(f"unknown target '{target}'")
    pd = Path(project_dir).expanduser()
    pd.mkdir(parents=True, exist_ok=True)
    pd_resolved = pd.resolve()
    # Refuse if the project dir lands inside any forbidden root.
    forbidden_roots: list[Path] = []
    if sys.platform == "win32":
        for env in ("WINDIR", "ProgramFiles", "ProgramFiles(x86)"):
            v = os.environ.get(env)
            if v:
                try: forbidden_roots.append(Path(v).resolve())
                except Exception: pass
    else:
        forbidden_roots += [Path("/etc"), Path("/usr"), Path("/var"), Path("/root")]
    for forbidden in forbidden_roots:
        try:
            pd_resolved.relative_to(forbidden)
            raise SandboxViolation(f"Project dir is inside protected path: {forbidden}")
        except ValueError:
            continue

    normalized = normalize_plan(plan)
    sess = CreativeSession(target=target, project_dir=pd_resolved, plan=normalized,
                           speak=speak, request_confirm=request_confirm)
    _set_active(sess)
    return sess


def creative_pause() -> dict:
    sess = get_active_session()
    if not sess:
        return {"success": False, "message": "No active creative session.",
                "ame_should_say": "There's nothing running right now."}
    sess.paused = True
    return {"success": True, "paused_at": sess.cursor, "total": len(sess.plan),
            "ame_should_say": "Paused. Say resume when you're ready."}


def creative_resume() -> dict:
    sess = get_active_session()
    if not sess:
        return {"success": False, "message": "No active creative session.",
                "ame_should_say": "Nothing's paused — we're clear."}
    if not sess.paused:
        return {"success": True, "message": "Already running.", "ame_should_say": "Already going."}
    sess.paused = False
    return {"success": True, "resumed_at": sess.cursor, "total": len(sess.plan),
            "ame_should_say": "Back at it."}


def creative_abandon() -> dict:
    sess = get_active_session()
    if not sess:
        return {"success": False, "message": "No active creative session.",
                "ame_should_say": "There's nothing to stop."}
    sess.stopped = True
    completed = sess.cursor
    total = len(sess.plan)
    _set_active(None)
    return {"success": True, "stopped_at": completed, "total": total,
            "ame_should_say": "Done with it. We can pick a different angle whenever."}
