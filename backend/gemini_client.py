"""
Shared Gemini task model client with automatic multi-model fallback.

ONLY for task/agent calls (planner, error_handler, memory, vision).
The voice model in live_session.py is completely separate and untouched.

Fallback chain: gemini-2.5-flash → gemini-2.0-flash → gemini-2.0-flash-lite
Uses GOOGLE_AI_STUDIO_KEY for all calls.
"""

import sys, os
os.environ.setdefault('PYTHONUTF8', '1')
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'): sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import httpx

TASK_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]

_RATE_LIMIT_SIGNALS = [
    "429",
    "quota",
    "rate limit",
    "resource exhausted",
    "too many requests",
]


class AllModelsExhaustedError(Exception):
    pass


def _is_rate_limit(status_code: int, body: str) -> bool:
    if status_code == 429:
        return True
    body_lower = body.lower()
    return any(sig in body_lower for sig in _RATE_LIMIT_SIGNALS)


def call_task_model(
    contents: list,
    api_key: str | None = None,
    timeout: int = 15,
) -> dict:
    """
    Send a generateContent request to the Gemini REST API.

    Falls back through TASK_MODELS on rate-limit or 404 errors.
    Uses GOOGLE_AI_STUDIO_KEY unless api_key is explicitly provided.

    Raises:
        AllModelsExhaustedError: if every model is rate-limited.
        Exception:               on any non-rate-limit error.
    """
    key = api_key or os.getenv("GOOGLE_AI_STUDIO_KEY")
    if not key:
        raise RuntimeError("No Gemini API key configured (GOOGLE_AI_STUDIO_KEY).")

    payload = {"contents": contents}

    for model in TASK_MODELS:
        url = (
            f"https://generativelanguage.googleapis.com"
            f"/v1beta/models/{model}:generateContent?key={key}"
        )
        try:
            resp = httpx.post(url, json=payload, timeout=timeout)

            if _is_rate_limit(resp.status_code, resp.text):
                print(f"[FALLBACK] {model} rate limited → trying next model")
                continue

            if resp.status_code == 404:
                print(f"[FALLBACK] {model} not found (404) → trying next model")
                continue

            if resp.status_code != 200:
                resp.raise_for_status()

            return resp.json()

        except AllModelsExhaustedError:
            raise
        except httpx.TimeoutException:
            print(f"[FALLBACK] {model} timed out → trying next model")
            continue
        except Exception as e:
            error_str = str(e).lower()
            if any(sig in error_str for sig in _RATE_LIMIT_SIGNALS):
                print(f"[FALLBACK] {model} rate limited → trying next model")
                continue
            raise

    raise AllModelsExhaustedError(
        "[FALLBACK] All models exhausted. Try again later."
    )


def extract_text(response_json: dict) -> str:
    """
    Safely extract plain text from a Gemini generateContent response,
    skipping thought parts (used in thinking models).
    """
    try:
        parts = response_json.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        text_parts = [
            p["text"] for p in parts
            if "text" in p and not p.get("thought", False)
        ]
        return " ".join(text_parts).strip()
    except Exception:
        return ""
