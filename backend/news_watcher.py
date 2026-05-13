"""
Amé News Watcher — startup awareness system.

Runs ONCE per session, 30s after startup:
1. Reads user memory for known interests
2. Searches for recent news on those topics
3. Uses an LLM to evaluate if anything is worth mentioning
4. Injects a natural mention via send_system_instruction
"""

from __future__ import annotations
import os
import threading
import time
import urllib.parse as _urllib


_has_run = False


def start_news_watcher(live_session) -> None:
    """Launch the news watcher in a background thread. Call once at startup."""
    global _has_run
    if _has_run:
        return
    _has_run = True
    t = threading.Thread(target=_run, args=(live_session,), daemon=True, name="NewsWatcher")
    t.start()
    print("[NewsWatcher] Scheduled (30s delay)")


def _run(live_session) -> None:
    """Main worker — runs once after a 30s delay."""
    time.sleep(30)
    try:
        from backend.live_session import _load_settings
        if not _load_settings().get("news_enabled", True):
            print("[NewsWatcher] Disabled by user — skipping")
            return
    except Exception:
        # If we can't read settings, default to "enabled but quietly try once".
        pass

    topics = _get_user_topics()
    if not topics:
        print("[NewsWatcher] No user topics known — skipping")
        return

    all_results = []
    for topic in topics[:3]:
        results = _search_topic(topic)
        if results:
            all_results.append({"topic": topic, "results": results[:3]})

    if not all_results:
        return

    summary = _evaluate_news(all_results)
    if summary and live_session and hasattr(live_session, "speak_proactive"):
        try:
            ctx = f"News watcher found recent items related to user interests: {topics[:3]}"
            live_session.speak_proactive(summary, ctx)
        except Exception as e:
            print(f"[NewsWatcher] speak_proactive failed: {e}")


def _get_user_topics() -> list[str]:
    """Extract up to 3 topics from user memory."""
    try:
        from backend.memory import load_memory
        mem = load_memory()
        data = getattr(mem, "_identity_data", {}) or {}
    except Exception:
        return []
    topics: list[str] = []
    for cat in ("preferences", "projects", "wishes"):
        for k, v in (data.get(cat) or {}).items():
            val = v.get("value") if isinstance(v, dict) else v
            if val and isinstance(val, str) and len(val) > 2:
                topics.append(val)
    return list(dict.fromkeys(topics))[:3]  # de-dupe, cap at 3


def _search_topic(topic: str) -> list[str]:
    """Search DuckDuckGo HTML for recent news on a topic."""
    try:
        import httpx
    except Exception:
        return []
    try:
        query = f"{topic} news"
        encoded = _urllib.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}&df=d"
        resp = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8, follow_redirects=True)
        if resp.status_code != 200:
            return []
        # Cheap title extraction — we don't need precision for filtering.
        import re
        matches = re.findall(r'class="result__a"[^>]*>([^<]+)<', resp.text)
        return [m.strip() for m in matches[:5]]
    except Exception as e:
        print(f"[NewsWatcher] search '{topic}' failed: {e}")
        return []


def _evaluate_news(all_results: list[dict]) -> str | None:
    """Decide if any result is worth mentioning. Returns a sentence or None."""
    try:
        from backend.providers import route, Purpose
    except Exception:
        return None
    lines: list[str] = []
    for bucket in all_results:
        lines.append(f"Topic: {bucket['topic']}")
        for r in bucket["results"]:
            lines.append(f"  - {r}")
    prompt = (
        "You are filtering news for an AI assistant. Decide whether ANY of the "
        "items below is genuinely worth interrupting the user about. If yes, "
        "reply with ONE friendly sentence (no greeting). If no, reply with the "
        "single word NONE.\n\n" + "\n".join(lines)
    )
    try:
        raw = route(Purpose.NEWS_FILTER, prompt, timeout=10)
    except Exception:
        return None
    if not raw or raw.strip().upper() == "NONE":
        return None
    return raw.strip()
