"""
Screen control module for Ame — vision-based dynamic clicking.
Uses Gemini Vision to find elements by description and click them
using percentage-based coordinates (resolution-independent).
Phase 2 adds: screen context memory, index-based clicking,
smart scroll, multi-step execution, and popup watching.
"""

import asyncio
import pyautogui
import PIL.ImageGrab
import base64
import io
import json
import os
import time
import threading

from google import genai
from google.genai import types

# Screen context memory — what AME last saw
_screen_context = {
    "last_screenshot": None,
    "last_elements": [],
    "last_action": None,
    "last_scroll_position": 0,
    "page_description": ""
}

_screen_context_lock = threading.Lock()

# Cache for analyze_screen_context — avoids redundant vision calls within 3 seconds
_analysis_cache = {
    "result": None,
    "timestamp": 0,
}

# Safety — prevent pyautogui from locking up
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.3


_VISION_MODEL = "gemini-2.0-flash"


def _get_genai_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_AI_STUDIO_KEY")
    return genai.Client(api_key=api_key)


def _screenshot_part(screenshot_b64: str) -> types.Part:
    """Convert a base64 PNG screenshot to a google.genai Part."""
    return types.Part.from_bytes(
        data=base64.b64decode(screenshot_b64),
        mime_type="image/png",
    )


def take_screenshot_base64() -> str:
    """Take screenshot and return as base64 string."""
    screenshot = PIL.ImageGrab.grab()
    buffer = io.BytesIO()
    screenshot.save(buffer, format='PNG')
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode('utf-8')


def get_screen_size():
    return pyautogui.size()


async def find_element_on_screen(description: str) -> dict:
    """
    Use Gemini Vision to find an element on screen.
    Returns position as percentage of screen dimensions.
    """
    try:
        screenshot_b64 = take_screenshot_base64()
        client = _get_genai_client()

        prompt = f"""Look at this screenshot carefully.
Find this element: "{description}"

Return ONLY a JSON object with this exact format:
{{
    "found": true,
    "x_percent": 45.2,
    "y_percent": 67.8,
    "confidence": "high",
    "description": "brief description of what you found"
}}

x_percent is the horizontal position as a percentage of total screen width (0 = left edge, 100 = right edge).
y_percent is the vertical position as a percentage of total screen height (0 = top, 100 = bottom).

If element not found:
{{
    "found": false,
    "confidence": "none",
    "description": "what you see instead"
}}

Return ONLY the JSON. No other text."""

        response = client.models.generate_content(
            model=_VISION_MODEL,
            contents=[prompt, _screenshot_part(screenshot_b64)],
        )

        text = response.text.strip()
        text = text.replace('```json', '').replace('```', '').strip()
        result = json.loads(text)
        return result

    except Exception as e:
        return {
            "found": False,
            "confidence": "none",
            "description": f"Error: {str(e)}"
        }


async def click_element(description: str, retries: int = 3) -> dict:
    """Find and click an element described in natural language, with retries."""
    client = _get_genai_client()

    for attempt in range(retries):
        try:
            screenshot_b64 = take_screenshot_base64()

            prompt = f'''Find "{description}" in this screenshot.
Return ONLY JSON:
{{
    "found": true,
    "x_percent": 45.2,
    "y_percent": 30.1,
    "description": "what you found"
}}
x_percent = horizontal position as % of screen width
y_percent = vertical position as % of screen height
If not found: {{"found": false, "description": "what you see"}}
ONLY JSON. No other text.'''

            response = client.models.generate_content(
                model=_VISION_MODEL,
                contents=[prompt, _screenshot_part(screenshot_b64)],
            )

            text = response.text.strip()
            text = text.replace('```json', '').replace('```', '').strip()
            result = json.loads(text)

            if result.get('found'):
                screen_w, screen_h = pyautogui.size()
                x = int((result['x_percent'] / 100) * screen_w)
                y = int((result['y_percent'] / 100) * screen_h)
                pyautogui.moveTo(x, y, duration=0.4)
                await asyncio.sleep(0.1)
                pyautogui.click()
                return {
                    "success": True,
                    "message": f"Clicked: {result.get('description', description)}"
                }
            else:
                if attempt < retries - 1:
                    await asyncio.sleep(0.5)
                    continue
                return {
                    "success": False,
                    "message": f"Could not find '{description}' on screen. Saw: {result.get('description', 'unknown')}"
                }

        except json.JSONDecodeError:
            if attempt < retries - 1:
                await asyncio.sleep(0.5)
                continue
            return {"success": False, "message": "Screen analysis returned invalid response"}
        except Exception as e:
            if attempt < retries - 1:
                await asyncio.sleep(0.5)
                continue
            return {"success": False, "message": f"Screen analysis error: {str(e)}"}

    return {"success": False, "message": "All retry attempts failed"}


async def scroll_screen(direction: str, amount: int = 10) -> dict:
    """Scroll up or down."""
    try:
        # Click center of screen first to ensure focus
        screen_w, screen_h = pyautogui.size()
        pyautogui.click(screen_w // 2, screen_h // 2)
        await asyncio.sleep(0.2)

        if direction.lower() in ['down', 'bas', 'abajo', 'unten']:
            pyautogui.scroll(-amount)
        else:
            pyautogui.scroll(amount)
        return {"success": True, "message": f"Scrolled {direction}"}
    except Exception as e:
        return {"success": False, "message": str(e)}


async def go_back() -> dict:
    """Press browser/system back."""
    try:
        pyautogui.hotkey('alt', 'left')
        return {"success": True, "message": "Went back"}
    except Exception as e:
        return {"success": False, "message": str(e)}


async def handle_popup() -> dict:
    """
    Detect and click the confirm button on any visible popup, dialog, or UAC prompt.
    """
    try:
        # Small delay to let popup fully render
        await asyncio.sleep(0.5)

        screenshot_b64 = take_screenshot_base64()
        client = _get_genai_client()

        prompt = '''Look at this screenshot.
Is there a popup, dialog, confirmation window, UAC prompt, or any modal overlay visible?

If YES, find the confirm/accept button (OK, Yes, Allow, Install, Accept, Continue, Next).
Return ONLY JSON:
{
    "popup_found": true,
    "popup_type": "UAC/install/confirmation/etc",
    "button_text": "OK",
    "x_percent": 50.0,
    "y_percent": 75.0
}

If NO popup visible:
{
    "popup_found": false,
    "screen_description": "brief description of what IS visible"
}

ONLY JSON. No other text.'''

        response = client.models.generate_content(
            model=_VISION_MODEL,
            contents=[prompt, _screenshot_part(screenshot_b64)],
        )

        text = response.text.strip()
        text = text.replace('```json', '').replace('```', '').strip()
        result = json.loads(text)

        if result.get('popup_found'):
            screen_w, screen_h = pyautogui.size()
            x = int((result['x_percent'] / 100) * screen_w)
            y = int((result['y_percent'] / 100) * screen_h)
            pyautogui.moveTo(x, y, duration=0.3)
            pyautogui.click()
            return {
                "success": True,
                "message": f"Clicked '{result.get('button_text', 'confirm')}' on {result.get('popup_type', 'dialog')}"
            }
        else:
            return {
                "success": False,
                "message": f"No popup found. Screen shows: {result.get('screen_description', 'unknown')}"
            }

    except Exception as e:
        return {"success": False, "message": f"Popup detection failed: {str(e)}"}


# ── Phase 2 ───────────────────────────────────────────────────────────────────

async def analyze_screen_context(retries: int = 3) -> dict:
    """
    Take screenshot and build a full understanding of what's on screen.
    Stores element list and page description in context memory.
    Returns cached result if called within 3 seconds of the last scan.
    """
    now = time.time()
    if _analysis_cache["result"] and now - _analysis_cache["timestamp"] < 3:
        return _analysis_cache["result"]

    client = _get_genai_client()

    prompt = """Analyze this screenshot completely. Return ONLY JSON:
{
    "page_type": "browser/desktop/app/dialog",
    "main_content": "brief description of main content",
    "clickable_elements": [
        {
            "index": 1,
            "type": "button/link/item/image",
            "label": "text or description",
            "x_percent": 45.2,
            "y_percent": 30.1,
            "color": "optional color description"
        }
    ],
    "has_popup": false,
    "popup_description": "",
    "scroll_possible": true,
    "page_description": "full description of what's visible"
}

List ALL clickable/interactive elements you can see.
Number them starting from 1, top to bottom, left to right.
Return ONLY the JSON. No other text."""

    for attempt in range(retries):
        try:
            screenshot_b64 = take_screenshot_base64()
            with _screen_context_lock:
                _screen_context["last_screenshot"] = screenshot_b64

            response = client.models.generate_content(
                model=_VISION_MODEL,
                contents=[prompt, _screenshot_part(screenshot_b64)],
            )

            text = response.text.strip()
            text = text.replace('```json', '').replace('```', '').strip()
            context = json.loads(text)

            with _screen_context_lock:
                _screen_context["last_elements"] = context.get("clickable_elements", [])
                _screen_context["page_description"] = context.get("page_description", "")

                _analysis_cache["result"] = context
                _analysis_cache["timestamp"] = time.time()

            return context

        except json.JSONDecodeError:
            if attempt < retries - 1:
                await asyncio.sleep(0.5)
                continue
            return {"error": "Screen analysis returned invalid response", "success": False}
        except Exception as e:
            if attempt < retries - 1:
                await asyncio.sleep(0.5)
                continue
            return {"error": str(e), "success": False}

    return {"error": "All retry attempts failed", "success": False}


async def click_by_index(index: int) -> dict:
    """Click element by its numbered position on screen."""
    with _screen_context_lock:
        elements = _screen_context.get("last_elements", [])

    if not elements:
        await analyze_screen_context()
        with _screen_context_lock:
            elements = _screen_context.get("last_elements", [])

    target = next((el for el in elements if el.get("index") == index), None)

    if not target:
        return {
            "success": False,
            "message": f"Could not find element number {index}. Found {len(elements)} elements total."
        }

    screen_w, screen_h = get_screen_size()
    x = int((target["x_percent"] / 100) * screen_w)
    y = int((target["y_percent"] / 100) * screen_h)

    pyautogui.moveTo(x, y, duration=0.4)
    pyautogui.click()

    with _screen_context_lock:
        _screen_context["last_action"] = f"clicked element {index}: {target.get('label', '')}"

    return {
        "success": True,
        "message": f"Clicked '{target.get('label', 'element')}' (item {index})",
        "element": target
    }


async def click_by_description_contextual(description: str) -> dict:
    """
    Click element using context from last screen scan.
    Understands 'that one', 'the other one', 'the red button', etc.
    Falls back to Phase 1 direct vision search if needed.
    """
    with _screen_context_lock:
        elements = _screen_context.get("last_elements", [])
        page_desc = _screen_context.get("page_description", "")
        last_action = _screen_context.get("last_action", "none")

    if not elements:
        await analyze_screen_context()
        with _screen_context_lock:
            elements = _screen_context.get("last_elements", [])

    if not elements:
        return await click_element(description)

    client = _get_genai_client()

    prompt = f"""The user wants to click: "{description}"

Current screen context: {page_desc}
Last action taken: {last_action}

Available elements on screen:
{json.dumps(elements, indent=2)}

Which element index should be clicked?
Return ONLY JSON:
{{
    "index": 2,
    "reasoning": "why this element matches",
    "confidence": "high/medium/low"
}}

If nothing matches, return:
{{
    "index": null,
    "reasoning": "why nothing matches",
    "confidence": "none"
}}

Return ONLY the JSON. No other text."""

    try:
        response = client.models.generate_content(
            model=_VISION_MODEL,
            contents=[prompt],
        )
        text = response.text.strip()
        text = text.replace('```json', '').replace('```', '').strip()
        result = json.loads(text)

        if result.get("index") and result.get("confidence") != "low":
            return await click_by_index(result["index"])
        else:
            return await click_element(description)

    except Exception:
        return await click_element(description)


async def smart_scroll(direction: str, amount: str = "normal") -> dict:
    """Scroll with natural language amount control."""
    scroll_amounts = {
        "bit": 5,
        "little": 5,
        "small": 5,
        "normal": 10,
        "more": 15,
        "lot": 25,
        "alot": 25,
        "much": 25,
        "top": 100,
        "bottom": 100,
    }

    clicks = scroll_amounts.get(amount.lower(), 4)

    # Click center of screen first to ensure scroll focus
    screen_w, screen_h = pyautogui.size()
    pyautogui.click(screen_w // 2, screen_h // 2)
    await asyncio.sleep(0.2)

    if direction.lower() in ['down', 'bas', 'abajo', 'unten']:
        pyautogui.scroll(-clicks)
        with _screen_context_lock:
            _screen_context["last_scroll_position"] += clicks
    else:
        pyautogui.scroll(clicks)
        with _screen_context_lock:
            _screen_context["last_scroll_position"] -= clicks

    return {
        "success": True,
        "message": f"Scrolled {direction} {amount}"
    }


async def execute_multi_step(steps: list) -> dict:
    """Execute multiple screen actions in sequence."""
    results = []

    for i, step in enumerate(steps):
        action = step.get("action")
        params = step.get("params", {})

        try:
            if action == "click":
                result = await click_element(params.get("description", ""))
            elif action == "click_index":
                result = await click_by_index(params.get("index", 1))
            elif action == "click_contextual":
                result = await click_by_description_contextual(params.get("description", ""))
            elif action == "scroll":
                result = await smart_scroll(
                    params.get("direction", "down"),
                    params.get("amount", "normal")
                )
            elif action == "go_back":
                result = await go_back()
            elif action == "press_key":
                result = await press_key_sc(params.get("key", ""))
            elif action == "handle_popup":
                result = await handle_popup()
            elif action == "wait":
                await asyncio.sleep(params.get("seconds", 1))
                result = {"success": True, "message": "Waited"}
            elif action == "analyze":
                result = await analyze_screen_context()
            else:
                result = {"success": False, "message": f"Unknown action: {action}"}

            results.append({"step": i + 1, "action": action, "result": result})

            await asyncio.sleep(0.5)

            if not result.get("success") and step.get("required", False):
                break

        except Exception as e:
            results.append({
                "step": i + 1,
                "action": action,
                "result": {"success": False, "message": str(e)}
            })

    success_count = sum(1 for r in results if r["result"].get("success"))

    return {
        "success": success_count > 0,
        "steps_completed": success_count,
        "total_steps": len(steps),
        "results": results
    }


async def watch_and_handle_popups(duration: int = 5) -> dict:
    """Watch screen for popups and handle them automatically as they appear."""
    start = time.time()
    handled = []

    while time.time() - start < duration:
        result = await handle_popup()
        if result.get("success"):
            handled.append(result["message"])
            await asyncio.sleep(1)
        else:
            await asyncio.sleep(0.5)

    return {
        "success": len(handled) > 0,
        "handled_count": len(handled),
        "actions": handled
    }


async def press_key_sc(key: str) -> dict:
    """Press a specific key or key combination (screen_control internal use)."""
    try:
        keys = key.lower().split('+')
        if len(keys) > 1:
            pyautogui.hotkey(*keys)
        else:
            pyautogui.press(keys[0])
        return {"success": True, "message": f"Pressed {key}"}
    except Exception as e:
        return {"success": False, "message": str(e)}
