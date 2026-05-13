"""
Simple synchronous web tools for Amé AI assistant.
Handles opening URLs, searching the web, and scraping page content.
"""

from __future__ import annotations
import urllib.parse as _urllib
import webbrowser

from backend import net_guard


def _url_to_friendly(url: str, query: str | None = None) -> str:
    """Convert a URL to a human-readable name without exposing the raw URL."""
    try:
        host = _urllib.urlparse(url).hostname or ""
        host = host.replace("www.", "")
        if query:
            return f"{host} (search: {query})"
        return host or url
    except Exception:
        return url


def open_url(url: str) -> dict:
    """Open a URL in the default system browser. Only http/https schemes are permitted."""
    if not url:
        return {"success": False, "message": "Empty URL"}
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = _urllib.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return {
            "success": False,
            "message": f"Blocked: URL scheme '{parsed.scheme}' is not allowed.",
        }
    print(f"[open_url] Opening: {url}")
    try:
        webbrowser.open(url)
    except Exception as e:
        return {"success": False, "message": f"Failed to open URL: {e}"}
    friendly = _url_to_friendly(url)
    return {
        "success": True,
        "message": f"Opened {friendly}.",
        "context": f"Browser is now showing {friendly}.",
    }


def google_search(query: str) -> dict:
    """Open Google in the default browser with a search query."""
    if not query:
        return {"success": False, "message": "Empty query"}
    encoded = _urllib.quote_plus(query)
    url = f"https://www.google.com/search?q={encoded}"
    webbrowser.open(url)
    return {
        "success": True,
        "message": f"Opened Google search for '{query}'.",
        "context": f"Browser is now showing Google search results for: {query}.",
    }


def open_google_maps(location: str) -> dict:
    if not location:
        return {"success": False, "message": "Empty location"}
    encoded = _urllib.quote_plus(location)
    url = f"https://www.google.com/maps/search/{encoded}"
    webbrowser.open(url)
    return {"success": True, "message": f"Opened Google Maps for '{location}'."}


def open_youtube(query: str) -> dict:
    if not query:
        return {"success": False, "message": "Empty query"}
    encoded = _urllib.quote_plus(query)
    url = f"https://www.youtube.com/results?search_query={encoded}"
    webbrowser.open(url)
    return {"success": True, "message": f"Opened YouTube search for '{query}'."}


def search_travel(origin: str = "", destination: str = "", date: str = "",
                  time: str = "", mode: str = "") -> dict:
    """Open Google Travel pre-filled with travel details."""
    mode_lower = (mode or "").lower()
    parts: list[str] = []
    if mode_lower in ("flight", "flights", ""):
        parts.append(f"flights from {origin}" if origin else "flights")
    else:
        parts.append(f"{mode_lower} from {origin}" if origin else mode_lower)
    if destination: parts.append(f"to {destination}")
    if date:        parts.append(date)
    if time:        parts.append(f"at {time}")
    query = " ".join(parts)
    encoded = _urllib.quote_plus(query)
    if mode_lower in ("flight", "flights", ""):
        url = f"https://www.google.com/travel/flights?q={encoded}"
    else:
        url = f"https://www.google.com/travel?q={encoded}"
    webbrowser.open(url)
    return {"success": True, "message": f"Opened travel search: {query}"}


def scrape_and_summarize(url: str) -> dict:
    """Fetch the readable text content of a web page using Playwright."""
    if not url:
        return {"success": False, "message": "Empty URL"}
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    ok, info = net_guard.resolve_and_check(url)
    if not ok:
        return {
            "success": False,
            "message": f"Blocked: {info.get('reason', 'URL guard refused')}",
            "blocked": True,
        }
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception as e:
        return {"success": False, "message": f"Playwright not installed: {e}"}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=15000, wait_until="domcontentloaded")
            title = page.title()
            text = page.evaluate("() => document.body && document.body.innerText || ''")
            browser.close()
    except Exception as e:
        return {"success": False, "message": f"Scrape failed: {e}"}

    if not text:
        return {"success": False, "message": "No readable text found"}
    return {
        "success": True,
        "title": title,
        "text": text[:8000],
        "url": url,
    }
