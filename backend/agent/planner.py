"""
Amé Agent Planner — breaks a natural language goal into up to 5 executable steps.
"""

from __future__ import annotations
import json
import os

from backend import load_env
from backend.gemini_client import call_task_model, extract_text, AllModelsExhaustedError

load_env()


AVAILABLE_TOOLS = [
    "web_search_ddg",
    "scrape_and_summarize",
    "open_url",
    "google_search",
    "run_web_task",
    "search_files",
    "type_text",
    "copy_to_clipboard",
    "take_screenshot",
    "run_terminal_command",
    "analyze_screen",
    "analyze_webcam",
    "play_song_on_spotify",
    "play_spotify_by_mood",
    "play_music_on_youtube",
    "open_application",
    "close_application",
    "set_volume",
    "get_current_time",
    "get_current_date",
    "organize_desktop",
    "clean_desktop",
    "list_desktop",
]

_PLAN_PROMPT = """You are a task planner for an AI assistant. Break the goal into at most 5 concrete steps.

Available tools: {tools}

Goal: {goal}

Return ONLY valid JSON:
{{
  "goal": "{goal}",
  "steps": [
    {{
      "step": 1,
      "tool": "tool_name",
      "description": "What this step does",
      "parameters": {{"param": "value"}},
      "critical": true
    }}
  ]
}}

Rules:
- Use the simplest sequence possible — fewer steps is better.
- "critical": true means failure of this step should abort or replan.
- parameters must match the tool's expected inputs.
- If the goal is simple enough for one tool, use one step.
JSON only:"""


def _route_agent(prompt: str) -> str:
    """Send a planner prompt and return raw model text."""
    api_key = os.getenv("GOOGLE_AI_STUDIO_KEY") or os.getenv("GEMINI_API_KEY")
    resp = call_task_model([{"parts": [{"text": prompt}]}], api_key=api_key, timeout=15)
    return extract_text(resp)


def _parse_json_response(raw: str) -> dict:
    """Strip markdown fences and parse JSON."""
    raw = (raw or "").strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def _fallback_plan(goal: str) -> dict:
    return {
        "goal": goal,
        "steps": [
            {
                "step": 1,
                "tool": "web_search_ddg",
                "description": f"Search for: {goal}",
                "parameters": {"query": goal},
                "critical": True,
            }
        ],
    }


def create_plan(goal: str) -> dict:
    """Break goal into up to 5 steps."""
    if not goal:
        return _fallback_plan("")

    api_key = os.getenv("GOOGLE_AI_STUDIO_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return _fallback_plan(goal)

    prompt = _PLAN_PROMPT.format(tools=", ".join(AVAILABLE_TOOLS), goal=goal)
    try:
        raw  = _route_agent(prompt)
        plan = _parse_json_response(raw)
    except (AllModelsExhaustedError, json.JSONDecodeError, Exception) as e:
        print(f"[agent:planner] create_plan failed, using fallback: {e}")
        return _fallback_plan(goal)

    plan.setdefault("goal", goal)
    plan["steps"] = (plan.get("steps") or [])[:5]
    return plan


def replan(goal: str, completed_steps: list, failed_step: dict, error: str) -> dict:
    """Create a revised plan that works around the failure."""
    api_key = os.getenv("GOOGLE_AI_STUDIO_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return _fallback_plan(goal)

    completed_desc = [s.get("description", "") if isinstance(s, dict) else str(s)
                      for s in (completed_steps or [])]
    failed_desc = (failed_step or {}).get("description", "")

    prompt = (
        "You are replanning a task after a step failed.\n\n"
        f"Goal: {goal}\n"
        f"Already completed: {json.dumps(completed_desc)}\n"
        f"Failed step: {failed_desc}\n"
        f"Error: {error}\n\n"
        "Create a new plan for ONLY the remaining work (skip completed steps).\n"
        f"Available tools: {', '.join(AVAILABLE_TOOLS)}\n\n"
        "Return ONLY valid JSON:\n"
        f'{{"goal": "{goal}", "steps": [{{"step": 1, "tool": "...", "description": "...", "parameters": {{}}, "critical": false}}]}}\n'
        "JSON only:"
    )
    try:
        raw  = _route_agent(prompt)
        plan = _parse_json_response(raw)
    except (AllModelsExhaustedError, json.JSONDecodeError, Exception) as e:
        print(f"[agent:planner] replan failed, using fallback: {e}")
        return _fallback_plan(goal)

    plan.setdefault("goal", goal)
    plan["steps"] = (plan.get("steps") or [])[:5]
    return plan
