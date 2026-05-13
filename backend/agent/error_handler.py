"""
Amé Agent Error Handler — analyzes step failures and decides how to proceed.
"""

from __future__ import annotations
import json
import os

from backend import load_env
from backend.gemini_client import call_task_model, extract_text, AllModelsExhaustedError

load_env()


DECISIONS = ["retry", "skip", "replan", "abort"]

_ERROR_PROMPT = """An AI assistant step failed. Decide how to proceed.

Step: {step_description}
Tool: {tool}
Error: {error}
Attempt number: {attempt}

Decide: retry / skip / replan / abort

Rules:
- retry: transient error (network timeout, rate limit). Max 2 retries.
- skip: step is non-critical and can be omitted safely.
- replan: critical step failed but the goal is still achievable differently.
- abort: goal is impossible or the error is fatal.

Return ONLY valid JSON:
{{
  "decision": "retry|skip|replan|abort",
  "reason": "one sentence why",
  "fix_suggestion": "what to try differently (optional)",
  "user_message": "brief message to tell the user"
}}
JSON only:"""


def _heuristic_decision(step: dict, error: str, attempt: int) -> dict:
    is_critical = bool(step.get("critical", False))
    err_low = (error or "").lower()
    if attempt >= 2:
        decision = "replan" if is_critical else "skip"
    elif "timeout" in err_low or "rate" in err_low or "connection" in err_low:
        decision = "retry"
    elif is_critical:
        decision = "replan"
    else:
        decision = "skip"
    return {
        "decision": decision,
        "reason": f"Step failed after {attempt} attempt(s): {(error or '')[:100]}",
        "fix_suggestion": "",
        "user_message": f"Hit a snag on '{step.get('description', 'step')}', trying to work around it.",
    }


def _strip_fence(raw: str) -> str:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


def analyze_error(step: dict, error: str, attempt: int) -> dict:
    """Analyze a step failure and return a decision dict."""
    step = step or {}
    fallback = _heuristic_decision(step, error or "", attempt or 0)

    api_key = os.getenv("GOOGLE_AI_STUDIO_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return fallback

    prompt = _ERROR_PROMPT.format(
        step_description=step.get("description", ""),
        tool=step.get("tool", ""),
        error=error or "",
        attempt=attempt,
    )
    try:
        resp = call_task_model(
            [{"parts": [{"text": prompt}]}],
            api_key=api_key, timeout=15,
        )
        raw = extract_text(resp)
        data = json.loads(_strip_fence(raw))
        if data.get("decision") in DECISIONS:
            # Keep the heuristic's user_message if the model didn't give one.
            data.setdefault("user_message", fallback["user_message"])
            return data
    except (AllModelsExhaustedError, json.JSONDecodeError, Exception) as e:
        print(f"[agent:error_handler] LLM call failed, using heuristic: {e}")
    return fallback
