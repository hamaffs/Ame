"""
LiveWebAgent — visible browser agent that navigates websites,
fills forms, clicks elements, and converses with the user mid-task.

Uses Playwright with a VISIBLE (headless=False) Chromium window so the
user can watch every action in real time.
"""
import sys, os
os.environ.setdefault('PYTHONUTF8', '1')
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'): sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import asyncio
import base64
import io
import re
import urllib.parse
import threading

from playwright.async_api import async_playwright
from PIL import Image


class WebInterceptor:
    """Background security shield that blocks known malicious domains."""
    def __init__(self):
        # Hardcoded domains for immediate testing
        self.malicious_domains = {
            "testsafebrowsing.appspot.com",
            "ianfette.org",
            "smartscreenTest.com",
            "malware.testing.machine"
        }
        # Fetch community malware list in the background
        threading.Thread(target=self._fetch_list, daemon=True, name="WebInterceptor").start()

    def _fetch_list(self):
        try:
            import httpx
            url = "https://raw.githubusercontent.com/StevenBlack/hosts/master/alternates/malware-only/hosts"
            resp = httpx.get(url, timeout=20)
            if resp.status_code == 200:
                count = 0
                for line in resp.text.splitlines():
                    if line.startswith("0.0.0.0 "):
                        domain = line.split(" ")[1].strip().lower()
                        self.malicious_domains.add(domain)
                        count += 1
                print(f"[WebInterceptor] Shield Armed: Loaded {count} malicious domains.")
        except Exception as e:
            print(f"[WebInterceptor] Failed to fetch live blocklist: {e}")

    def is_blocked(self, url: str) -> bool:
        try:
            domain = urllib.parse.urlparse(url).netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            return domain in self.malicious_domains
        except:
            return False

_interceptor = WebInterceptor()


class LiveWebAgent:
    """
    A visible browser agent that navigates websites,
    fills forms, and converses with the user mid-task.
    """

    def __init__(self):
        self._browser = None
        self._page = None
        self._playwright = None
        self._running = False

    async def start(self):
        """Launch visible browser window."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=False,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await self._browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        self._page = await context.new_page()
        
        # --- CYBERSECURITY: WEB INTERCEPTOR ---
        async def _route_intercept(route):
            req = route.request
            if req.resource_type in ("document", "iframe"):
                url = req.url
                if _interceptor.is_blocked(url):
                    print(f"[WebInterceptor] BLOCKED access to {url}")
                    await route.abort("blockedbyclient")
                    from backend.server import live_session
                    if live_session:
                        domain = urllib.parse.urlparse(url).netloc
                        live_session.speak_proactive(
                            f"Security Alert. I just blocked a connection to {domain}. This website is flagged as a malicious threat.",
                            f"You successfully protected the user's PC by blocking navigation to the malware site: {url}"
                        )
                    return
            await route.continue_()

        await self._page.route("**/*", _route_intercept)
        self._running = True

    async def stop(self):
        """Close browser."""
        try:
            if self._browser:
                await self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass
        self._running = False
        self._page = None
        self._browser = None
        self._playwright = None

    async def navigate(self, url: str):
        """Go to a URL."""
        if not url.startswith("http"):
            url = "https://" + url
        try:
            await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            if "ERR_BLOCKED_BY_CLIENT" in str(e):
                print(f"[LiveWebAgent] Navigation intercepted and blocked: {url}")
            else:
                print(f"[LiveWebAgent] Navigation error: {e}")
        await asyncio.sleep(2)

    async def screenshot_base64(self) -> str:
        """Take screenshot and return as base64 JPEG."""
        screenshot = await self._page.screenshot()
        img = Image.open(io.BytesIO(screenshot))
        img.thumbnail([1280, 720], Image.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=60)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    async def analyze_screen(self, question: str) -> str:
        """
        Take a screenshot and ask Gemini Vision what's on screen.
        Returns the model's text answer.
        """
        from backend.gemini_client import call_task_model, extract_text

        api_key = os.getenv("GOOGLE_AI_STUDIO_KEY") or os.getenv("GEMINI_API_KEY")
        b64 = await self.screenshot_base64()

        contents = [
            {
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": b64,
                        }
                    },
                    {"text": question},
                ]
            }
        ]
        resp_json = call_task_model(contents, api_key=api_key, timeout=20)
        return extract_text(resp_json)

    async def find_and_click(self, description: str) -> bool:
        """
        Find an element by description and click it.
        First tries Playwright text/role selectors, then falls back to
        vision-based coordinate clicking.
        """
        selectors_to_try = [
            f'text="{description}"',
            f'button:has-text("{description}")',
            f'[placeholder*="{description}" i]',
            f'label:has-text("{description}")',
            f'a:has-text("{description}")',
            f'[aria-label*="{description}" i]',
            f'[title*="{description}" i]',
        ]

        for selector in selectors_to_try:
            try:
                element = self._page.locator(selector).first
                if await element.count() > 0:
                    await element.click(timeout=3000)
                    await asyncio.sleep(0.5)
                    return True
            except Exception:
                continue

        result = await self.analyze_screen(
            f'Find the "{description}" button, link, or element on the page. '
            f"Return ONLY the x,y pixel coordinates as: x=NNN y=NNN"
        )

        try:
            match_x = re.search(r"x=(\d+)", result)
            match_y = re.search(r"y=(\d+)", result)
            if not match_x or not match_y:
                return False
            x = int(match_x.group(1))
            y = int(match_y.group(1))
            await self._page.mouse.click(x, y)
            await asyncio.sleep(0.5)
            return True
        except Exception:
            return False

    async def fill_field(self, field_description: str, value: str) -> bool:
        """
        Find a form field by description/label and fill it with value.
        """
        selectors = [
            f'input[placeholder*="{field_description}" i]',
            f'input[name*="{field_description}" i]',
            f'input[id*="{field_description}" i]',
            f'input[aria-label*="{field_description}" i]',
            f'textarea[placeholder*="{field_description}" i]',
            f'textarea[name*="{field_description}" i]',
        ]

        for selector in selectors:
            try:
                element = self._page.locator(selector).first
                if await element.count() > 0:
                    await element.click()
                    await element.fill(value)
                    await asyncio.sleep(0.3)
                    return True
            except Exception:
                continue

        result = await self.analyze_screen(
            f'Find the input field for "{field_description}". '
            f"Return ONLY x,y as: x=NNN y=NNN"
        )

        try:
            match_x = re.search(r"x=(\d+)", result)
            match_y = re.search(r"y=(\d+)", result)
            if not match_x or not match_y:
                return False
            x = int(match_x.group(1))
            y = int(match_y.group(1))
            await self._page.mouse.click(x, y)
            await asyncio.sleep(0.3)
            await self._page.keyboard.type(value, delay=50)
            return True
        except Exception:
            return False

    async def press_key(self, key: str):
        """Press a keyboard key."""
        await self._page.keyboard.press(key)

    async def scroll(self, direction: str = "down", amount: int = 3):
        """Scroll the page."""
        delta = 300 * amount
        if direction == "up":
            delta = -delta
        await self._page.mouse.wheel(0, delta)
        await asyncio.sleep(0.5)

    async def get_page_text(self) -> str:
        """Get readable text from current page (strips nav/footer/scripts, capped at 5000 chars)."""
        content = await self._page.evaluate(
            """() => {
                ['script','style','nav','footer','header'].forEach(tag => {
                    document.querySelectorAll(tag).forEach(el => el.remove());
                });
                return document.body ? document.body.innerText : '';
            }"""
        )
        return content[:5000] if content else ""

    def is_running(self) -> bool:
        return self._running and self._page is not None

_agent = LiveWebAgent()


async def get_agent() -> LiveWebAgent:
    """Return the running agent, starting it first if needed."""
    if not _agent.is_running():
        await _agent.start()
    return _agent
