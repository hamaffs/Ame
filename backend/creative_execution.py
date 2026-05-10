# Source Generated with Decompyle++
# File: creative_execution.pyc (Python 3.11)

'''Creative Execution ΓÇö Am├⌐ builds *with* you (Milestone 5).

`creative_soul.py` is the translator (free tier, unlimited). This module is
the executor ΓÇö she actually drives the user\'s tools to author the project.
Quota is enforced at the dispatcher (`creative_execute_plan` -> bucket
`creative_execution`). Voice "stop" halts within ~500ms. Every 3-5 actions
she pauses, describes the next batch, and waits for the user to confirm
through the existing `confirm_action` flow.

Two execution modes ship in M5:

- **text_target** (p5.js, shaders): she generates the code, writes it inside
  the project directory, and opens the target tool with it. One quota unit
  covers the whole authoring of one file.
- **gui_target** (Photoshop, TouchDesigner): a checkpointed loop ΓÇö she
  describes the next 3-5 hotkey/click steps, asks for confirmation, then
  runs them. After each batch she pauses again. She cannot run unsupervised
  for more than ~30s.

Safety rails (non-negotiable):
- File writes stay inside `session.project_dir`. Anything outside is refused
  + logged. No path traversal: the resolved absolute path must start with
  the resolved project directory.
- No installer launches, asset purchases, or system-setting changes.
- Hard-stop on the global "stop" voice command (live_session sets
  session.stopped, the loop polls every step).
- Destructive actions reuse the existing `confirm_action` flow inside
  live_session; the checkpoint pauses ride on top of that.
'''
from __future__ import annotations
import asyncio
import os
import time
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
CreativeSession = <NODE:12>()
_active: 'CreativeSession | None' = None
_lock = threading.RLock()

def _set_active(sess = None):
    pass
# WARNING: Decompyle incomplete


def get_active_session():
    """Public read-only accessor ΓÇö used by live_session to inject 'stop'."""
    pass
# WARNING: Decompyle incomplete


class SandboxViolation(Exception):
    '''Raised when an authoring step tries to escape the project directory.'''
    pass


def safe_join(project_dir = None, requested = None):
    """Resolve `requested` (relative or absolute) against `project_dir` and
    refuse anything that lands outside. Symlinks are followed during resolve
    so a symlink trick can't escape either.
    """
    pd = project_dir.resolve()
    candidate = pd / requested if not os.path.isabs(requested) else Path(requested)
    resolved = candidate.resolve()
    resolved.relative_to(pd)
# WARNING: Decompyle incomplete

_VALID_KINDS = {
    'wait',
    'hotkey',
    'describe',
    'open_file',
    'type_text',
    'write_file'}
_DESTRUCTIVE_KINDS = {
    'write_file'}

def normalize_plan(steps = None):
    '''Validate + normalize incoming plan. Raises ValueError on bad shapes.

    Each step is:
      {"kind": "write_file", "path": "sketch.js", "content": "..."}
      {"kind": "open_file",  "path": "sketch.js"}
      {"kind": "hotkey",     "keys": ["ctrl", "s"]}
      {"kind": "type_text",  "text": "..."}
      {"kind": "describe",   "text": "what she\'s about to do, spoken to user"}
      {"kind": "wait",       "seconds": 1.0}
    '''
    if not isinstance(steps, list) or steps:
        raise ValueError('plan must be a non-empty list')
    out = []
# WARNING: Decompyle incomplete


def _execute_step(sess = None, step = None):
    '''Run a single step. Pure-sync so the dispatcher can `to_thread` it.
    Returns a small dict for the spoken note / log.'''
    kind = step['kind']
    if kind == 'write_file':
        target = safe_join(sess.project_dir, step['path'])
        target.parent.mkdir(parents = True, exist_ok = True)
        target.write_text(step['content'], encoding = 'utf-8')
        return {
            'ok': True,
            'kind': kind,
            'path': str(target),
            'bytes': len(step['content']) }
    if None == 'open_file':
        target = safe_join(sess.project_dir, step['path'])
        if not target.exists():
            return {
                'ok': False,
                'kind': kind,
                'error': f'''file does not exist: {target}''' }
        os.startfile(str(target))
# WARNING: Decompyle incomplete

CHECKPOINT_EVERY = 4

def _next_batch(sess = None):
    '''Return the next CHECKPOINT_EVERY steps, or empty if plan exhausted.'''
    return sess.plan[sess.cursor:sess.cursor + CHECKPOINT_EVERY]


def _summarize_batch(batch = None):
    '''One-line human summary of a batch ΓÇö shown in the confirm dialog.'''
    lines = []
    for step in batch:
        k = step['kind']
        if k == 'write_file':
            lines.append(f'''write {step['path']} ({len(step['content'])} chars)''')
            continue
        if k == 'open_file':
            lines.append(f'''open {step['path']}''')
            continue
        if k == 'hotkey':
            lines.append(f'''press {'+'.join(step['keys'])}''')
            continue
        if k == 'type_text':
            preview = step['text'][:40].replace('\n', '\\n')
            lines.append(f'''type "{preview}"''')
            continue
        if k == 'describe':
            lines.append(f'''say: {step['text'][:60]}''')
            continue
        if k == 'wait':
            lines.append(f'''wait {step['seconds']}s''')
        return '\n'.join(lines)


async def run_session(sess = None):
    '''Drive the plan to completion, pausing at each checkpoint.

    Returns a dict shaped like:
      {"success": True, "completed": int, "total": int,
       "stopped": bool, "abandoned": bool, "log": [...]}
    '''
    pass
# WARNING: Decompyle incomplete


def creative_execute_plan(target = None, project_dir = None, plan = None, speak = (None, None), request_confirm = ('target', 'str', 'project_dir', 'str', 'plan', 'list[dict]', 'speak', 'Callable[[str], None] | None', 'request_confirm', "Callable[[str, str], 'asyncio.Future[bool]'] | None", 'return', 'CreativeSession')):
    '''Build the session and return it. The dispatcher is responsible for
    `await run_session(sess)` and emitting the eventual result back to the
    model. Quota consumption already happened at the dispatcher.
    '''
    if target not in frozenset({'p5js', 'shader', 'photoshop', 'touchdesigner'}):
        raise ValueError(f'''unknown target \'{target}\' (supported in M5: p5js, shader, photoshop, touchdesigner)''')
    pd = Path(project_dir).expanduser()
    pd.mkdir(parents = True, exist_ok = True)
    pd_resolved = pd.resolve()
    forbidden_roots = [
        Path(os.environ.get('WINDIR', 'C:/Windows')).resolve(),
        Path(os.environ.get('ProgramFiles', 'C:/Program Files')).resolve(),
        Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)')).resolve()]
# WARNING: Decompyle incomplete


def creative_pause():
    sess = get_active_session()
    if not sess:
        return {
            'success': False,
            'message': 'No active creative session.',
            'ame_should_say': "There's nothing running right now." }
    sess.paused = None
    return {
        'success': True,
        'paused_at': sess.cursor,
        'total': len(sess.plan),
        'ame_should_say': "Paused. Say resume when you're ready." }


def creative_resume():
    sess = get_active_session()
    if not sess:
        return {
            'success': False,
            'message': 'No active creative session.',
            'ame_should_say': "Nothing's paused ΓÇö we're clear." }
    if not None.paused:
        return {
            'success': True,
            'message': 'Already running.',
            'ame_should_say': 'Already going.' }
    sess.paused = None
    return {
        'success': True,
        'resumed_at': sess.cursor,
        'total': len(sess.plan),
        'ame_should_say': 'Back at it.' }


def creative_abandon():
    sess = get_active_session()
    if not sess:
        return {
            'success': False,
            'message': 'No active creative session.',
            'ame_should_say': "There's nothing to stop." }
    sess.stopped = None
    completed = sess.cursor
    total = len(sess.plan)
    _set_active(None)
    return {
        'success': True,
        'stopped_at': completed,
        'total': total,
        'ame_should_say': 'Done with it. We can pick a different angle whenever.' }

