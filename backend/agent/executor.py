"""
Ame Agent Executor — runs a multi-step plan, handles errors, speaks progress.
"""

import sys, os
os.environ.setdefault('PYTHONUTF8', '1')
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'): sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import asyncio
from typing import Callable

from backend.agent.planner import create_plan, replan
from backend.agent.error_handler import analyze_error


async def _run_tool(name: str, params: dict) -> dict:
    """Execute a single tool by name."""
    try:
        if name == "web_search_ddg":
            from backend.search import quick_search
            result = await quick_search(params.get("query", ""))
            return {"success": True, "results": result}

        elif name == "scrape_and_summarize":
            from backend.web_agent import scrape_and_summarize
            return await asyncio.to_thread(scrape_and_summarize, params.get("url", ""))

        elif name == "open_url":
            from backend.web_agent import open_url
            return await asyncio.to_thread(open_url, params.get("url", ""))

        elif name == "google_search":
            from backend.web_agent import google_search
            return await asyncio.to_thread(google_search, params.get("query", ""))

        elif name == "run_web_task":
            from backend.web_agent_advanced import run_web_task
            result = await run_web_task(params.get("task", ""), params.get("starting_url"))
            return {"success": True, "result": result}

        elif name == "search_files":
            from backend.pc_control import search_files
            return await asyncio.to_thread(search_files, params.get("query", ""))

        elif name == "type_text":
            from backend.pc_control import type_text
            return await asyncio.to_thread(type_text, params.get("text", ""))

        elif name == "copy_to_clipboard":
            from backend.pc_control import copy_to_clipboard
            return await asyncio.to_thread(copy_to_clipboard, params.get("text", ""))

        elif name == "take_screenshot":
            from backend.pc_control import take_screenshot
            return await asyncio.to_thread(take_screenshot)

        elif name == "run_terminal_command":
            from backend.pc_control import run_terminal_command
            return await asyncio.to_thread(
                run_terminal_command,
                params.get("command", ""),
                params.get("task_description", ""),
            )

        elif name == "analyze_screen":
            from backend.vision import analyze_screen
            return await asyncio.to_thread(analyze_screen, params.get("prompt", "Describe the screen."))

        elif name == "analyze_webcam":
            from backend.vision import analyze_webcam
            return await asyncio.to_thread(analyze_webcam, params.get("prompt", "Describe what you see."))

        elif name == "organize_desktop":
            from backend.pc_control import organize_desktop
            return await asyncio.to_thread(organize_desktop, params.get("mode", "type"))

        elif name == "clean_desktop":
            from backend.pc_control import clean_desktop
            return await asyncio.to_thread(clean_desktop)

        elif name == "list_desktop":
            from backend.pc_control import list_desktop
            return await asyncio.to_thread(list_desktop)

        elif name == "open_application":
            from backend.pc_control import open_application
            return await asyncio.to_thread(open_application, params.get("app_name", ""))

        elif name == "set_volume":
            from backend.pc_control import set_volume
            return await asyncio.to_thread(set_volume, params.get("level", 50))

        elif name == "get_current_time":
            from backend.pc_control import get_current_time
            return await asyncio.to_thread(get_current_time)

        elif name == "get_current_date":
            from backend.pc_control import get_current_date
            return await asyncio.to_thread(get_current_date)

        elif name in ("play_song_on_spotify", "play_spotify_by_mood", "play_music_on_youtube"):
            from backend.music_agent import play_song_on_spotify, play_spotify_by_mood, play_music_on_youtube
            fn_map = {
                "play_song_on_spotify": (play_song_on_spotify, params.get("query", "")),
                "play_spotify_by_mood": (play_spotify_by_mood, params.get("mood_or_genre", "")),
                "play_music_on_youtube": (play_music_on_youtube, params.get("query", "")),
            }
            fn, arg = fn_map[name]
            return await asyncio.to_thread(fn, arg)

        else:
            return {"success": False, "error": f"Unknown tool in executor: {name}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


async def execute(goal: str, speak_fn: Callable, cancel_flag: dict) -> str:
    """Execute a goal by planning steps and running them sequentially."""
    plan = create_plan(goal)
    steps = plan.get("steps", [])

    if not steps:
        return "I couldn't figure out how to approach that task."

    completed = []
    results_summary = []
    current_steps = list(steps)
    step_idx = 0

    while step_idx < len(current_steps):
        if cancel_flag.get("cancelled"):
            return "Task cancelled."

        step = current_steps[step_idx]
        tool = step.get("tool", "")
        params = step.get("parameters", {})
        desc = step.get("description", tool)

        speak_fn(f"Working on it: {desc}")

        attempt = 0
        success = False
        last_error = ""

        while attempt < 3:
            if cancel_flag.get("cancelled"):
                return "Task cancelled."

            result = await _run_tool(tool, params)

            if result.get("success"):
                success = True
                for key in ("results", "result", "description", "message", "files"):
                    val = result.get(key)
                    if val:
                        results_summary.append(f"[{desc}]: {str(val)[:300]}")
                        break
                completed.append(step)
                break
            else:
                last_error = result.get("error") or result.get("message") or "Unknown error"
                attempt += 1

                error_decision = analyze_error(step, last_error, attempt)
                decision = error_decision.get("decision", "skip")

                if decision == "retry" and attempt < 3:
                    speak_fn(f"Retrying {desc}...")
                    await asyncio.sleep(1)
                    continue

                elif decision == "skip":
                    speak_fn(f"Skipped step: {desc}")
                    break

                elif decision == "replan":
                    speak_fn("Adjusting my approach...")
                    new_plan = replan(goal, completed, step, last_error)
                    new_steps = new_plan.get("steps", [])
                    if new_steps:
                        current_steps = new_steps
                        step_idx = -1
                        break
                    else:
                        speak_fn("Couldn't find an alternative approach.")
                        break

                elif decision == "abort":
                    msg = error_decision.get("user_message", f"Task aborted: {last_error}")
                    speak_fn(msg)
                    return msg

                break

        step_idx += 1

    if results_summary:
        summary = f"Done. Here's what I found:\n" + "\n".join(results_summary[:3])
    elif completed:
        summary = f"Completed {len(completed)} step(s) for: {goal}"
    else:
        summary = f"I wasn't able to complete the task: {goal}"

    return summary
