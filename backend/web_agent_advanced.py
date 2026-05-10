"""
Autonomous browser agent for Ame AI assistant.
Uses multi-provider LLM rotation + Playwright to complete multi-step web tasks.
"""

import asyncio
import json
import os
import re

from backend import load_env
from playwright.async_api import async_playwright

load_env()

MAX_STEPS = 7

async def _agent_chat(messages: list, max_tokens: int = 512) -> str:
    """Send a chat request through the provider manager."""
    from backend.providers import provider_manager
    resp = await provider_manager.chat(
        messages=messages,
        tools=None,
        max_tokens=max_tokens,
        temperature=0.1,
    )
    return resp["choices"][0]["message"].get("content", "").strip()


async def _extract_page_info(page) -> dict:
    """Extract structured information from the current page state."""
    try:
        url = page.url
        title = await page.title()

        content = await page.evaluate("""() => {
            const noisy = ['script', 'style', 'nav', 'footer', 'noscript', 'iframe', 'svg'];
            noisy.forEach(sel => {
                document.querySelectorAll(sel).forEach(el => el.remove());
            });
            return document.body ? document.body.innerText : '';
        }""")

        content = re.sub(r"\n{3,}", "\n\n", content or "")
        content = re.sub(r"[ \t]{2,}", " ", content)
        content = content.strip()[:6000]

        buttons = await page.evaluate("""() => {
            const btns = [];
            document.querySelectorAll('button, input[type="button"], input[type="submit"], [role="button"]').forEach(el => {
                const text = (el.innerText || el.getAttribute('value') || el.getAttribute('aria-label') || '').trim();
                if (text && text.length < 100) btns.push(text);
            });
            return btns.slice(0, 20);
        }""")

        links = await page.evaluate("""() => {
            const result = [];
            document.querySelectorAll('a[href]').forEach(el => {
                const text = (el.innerText || el.getAttribute('aria-label') || '').trim();
                const href = el.getAttribute('href');
                if (text && href && text.length < 120) {
                    result.push({ text: text, href: href });
                }
            });
            return result.slice(0, 25);
        }""")

        inputs = await page.evaluate("""() => {
            const result = [];
            document.querySelectorAll('input:not([type="hidden"]), textarea').forEach(el => {
                result.push({
                    placeholder: el.getAttribute('placeholder') || '',
                    name: el.getAttribute('name') || '',
                    type: el.getAttribute('type') || 'text',
                    id: el.getAttribute('id') || ''
                });
            });
            return result.slice(0, 10);
        }""")

        return {
            "url": url,
            "title": title,
            "content": content,
            "buttons": buttons or [],
            "links": links or [],
            "inputs": inputs or [],
        }

    except Exception as e:
        return {
            "url": page.url,
            "title": "Error extracting page info",
            "content": f"Error: {e}",
            "buttons": [],
            "links": [],
            "inputs": [],
        }


SYSTEM_PROMPT = """You are an autonomous web browsing agent. Given a task and the current page state, decide the SINGLE next browser action to take.

Available actions (respond with ONLY valid JSON — no markdown fences, no explanation):

1. Navigate to a URL:
   {"action": "navigate", "url": "https://..."}

2. Click an element by visible text:
   {"action": "click", "selector_type": "text", "value": "the button text"}

3. Click the Nth link (0-indexed):
   {"action": "click", "selector_type": "index", "value": 0}

4. Type into an input field:
   {"action": "type", "selector": "input[name='q']", "text": "search term", "submit": true}

5. Scroll down the page:
   {"action": "scroll", "direction": "down", "amount": 500}

6. Press a keyboard key:
   {"action": "press", "key": "Enter"}

7. Task completed — return result:
   {"action": "done", "result": "The answer or summary of what was accomplished."}

8. Task cannot be completed:
   {"action": "failed", "reason": "Explain why it cannot be done."}

Rules:
- Always output ONLY the JSON object, nothing else.
- Prefer clicking links/buttons by their visible text when possible.
- If the page content already contains the answer to the task, IMMEDIATELY use "done" — do NOT search again.
- On Google/Bing/DuckDuckGo search results pages: read the content first. If it contains the answer, call "done" with the answer extracted from the content. Only click a link if the answer is NOT visible in the content.
- After filling a form, submit it. Never re-type or re-submit the same query twice.
- If you have gathered enough information to answer the task, use "done".
- If you already performed a search and see results, do NOT search again — extract the answer or click a result.
"""


async def _decide_next_action(task: str, page_info: dict, history: list) -> dict:
    """Ask the LLM what the next browser action should be."""

    history_text = ""
    if history:
        recent = history[-6:]
        history_text = "\n".join(
            f"Step {i+1}: {json.dumps(h)}" for i, h in enumerate(recent)
        )

    user_message = f"""TASK: {task}

CURRENT PAGE:
URL: {page_info['url']}
Title: {page_info['title']}

PAGE CONTENT (first 3000 chars):
{page_info['content'][:3000]}

BUTTONS: {json.dumps(page_info['buttons'][:10])}
LINKS (first 15): {json.dumps(page_info['links'][:15])}
INPUTS: {json.dumps(page_info['inputs'])}

HISTORY OF STEPS TAKEN:
{history_text if history_text else '(none yet)'}

IMPORTANT: If the PAGE CONTENT above already contains the answer to the task, call "done" immediately with the answer. Do NOT search again if you already searched.

What is your NEXT action? Output ONLY a JSON object."""

    raw = await _agent_chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        max_tokens=512,
    )

    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()

    try:
        action = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            action = json.loads(match.group())
        else:
            action = {"action": "failed", "reason": f"LLM returned unparseable response: {raw}"}

    return action


async def _execute_action(page, action: dict) -> str:
    """Execute a single browser action. Returns a status string."""
    act = action.get("action", "")

    try:
        if act == "navigate":
            url = action["url"]
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(2000)
            return f"Navigated to {url}"

        elif act == "click":
            selector_type = action.get("selector_type", "text")
            value = action.get("value")

            if selector_type == "text":
                try:
                    await page.get_by_text(str(value), exact=True).first.click(timeout=5000)
                except Exception:
                    await page.get_by_text(str(value)).first.click(timeout=5000)
                await page.wait_for_timeout(1500)
                return f"Clicked element with text '{value}'"

            elif selector_type == "index":
                idx = int(value)
                links = await page.query_selector_all("a[href]")
                if idx < len(links):
                    await links[idx].click()
                    await page.wait_for_timeout(1500)
                    return f"Clicked link at index {idx}"
                else:
                    return f"Link index {idx} out of range (only {len(links)} links)"

        elif act == "type":
            selector = action.get("selector", "")
            text = action.get("text", "")
            submit = action.get("submit", False)

            try:
                element = page.locator(selector).first
                await element.click(timeout=5000)
                await element.fill(text)
            except Exception:
                for fallback_selector in ['input[type="search"]', 'input[type="text"]', "textarea"]:
                    try:
                        el = page.locator(fallback_selector).first
                        await el.click(timeout=3000)
                        await el.fill(text)
                        break
                    except Exception:
                        continue

            if submit:
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(2000)

            return f"Typed '{text}' into '{selector}'"

        elif act == "scroll":
            direction = action.get("direction", "down")
            amount = int(action.get("amount", 500))
            delta = amount if direction == "down" else -amount
            await page.mouse.wheel(0, delta)
            await page.wait_for_timeout(500)
            return f"Scrolled {direction} by {amount}px"

        elif act == "press":
            key = action.get("key", "Enter")
            await page.keyboard.press(key)
            await page.wait_for_timeout(1000)
            return f"Pressed key '{key}'"

        elif act in ("done", "failed"):
            return f"Task ended: {act}"

        else:
            return f"Unknown action: {act}"

    except Exception as e:
        return f"Action '{act}' failed: {e}"


def _action_summary(action: dict) -> str:
    act = action.get("action", "")
    if act == "navigate":
        return f"Going to {action.get('url', '')}"
    elif act == "click":
        return f'Clicking "{action.get("value", "")}"'
    elif act == "type":
        return f'Typing "{action.get("text", "")[:40]}"'
    elif act == "scroll":
        return f"Scrolling {action.get('direction', 'down')}"
    elif act == "press":
        return f"Pressing {action.get('key', '')}"
    elif act == "done":
        return "Done"
    elif act == "failed":
        return f"Failed: {action.get('reason', '')}"
    return act


async def run_web_task(task: str, starting_url: str = None, on_step=None) -> str:
    """Run an autonomous multi-step web task."""
    if not starting_url:
        raw_url = await _agent_chat(
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"For this web task: '{task}'\n"
                        "What is the best starting URL? "
                        "If this is a general web search/lookup, reply with a Google search URL in the format: https://www.google.com/search?q=search+terms&hl=en\n"
                        "Otherwise reply with ONLY the full URL, nothing else."
                    ),
                }
            ],
            max_tokens=150,
        )
        starting_url = re.sub(r"[`'\"]", "", raw_url).strip()
        if not starting_url.startswith(("http://", "https://")):
            starting_url = "https://" + starting_url

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        page = await context.new_page()

        try:
            await page.goto(starting_url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(2000)
            if on_step:
                on_step({"type": "navigate", "url": starting_url, "step": 0})
        except Exception as e:
            await browser.close()
            return f"Could not load page: {e}"

        history = []
        final_result = f"Task '{task}' completed but no explicit result was returned."

        for step in range(MAX_STEPS):
            page_info = await _extract_page_info(page)
            action = await _decide_next_action(task, page_info, history)

            action_type = action.get("action", "")

            if on_step:
                on_step({"type": "step", "step": step + 1, "action": action_type,
                         "detail": _action_summary(action),
                         "url": page_info.get("url", ""), "title": page_info.get("title", "")})

            if action_type == "done":
                final_result = action.get("result", "Task completed.")
                history.append({"step": step + 1, "action": action, "status": "done"})
                break

            if action_type == "failed":
                final_result = f"Task failed: {action.get('reason', 'Unknown reason')}"
                history.append({"step": step + 1, "action": action, "status": "failed"})
                break

            status = await _execute_action(page, action)
            history.append({"step": step + 1, "action": action, "status": status})

        else:
            page_info = await _extract_page_info(page)
            final_result = (
                f"Reached maximum steps ({MAX_STEPS}). "
                f"Last page: {page_info['title']} ({page_info['url']}). "
                f"Content preview: {page_info['content'][:500]}"
            )

        await browser.close()
        return final_result


def web_task_sync(task: str, starting_url: str = None, on_step=None) -> dict:
    """Synchronous wrapper around run_web_task."""
    try:
        result = asyncio.run(run_web_task(task, starting_url, on_step=on_step))
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "result": str(e)}
