"""
Token-efficient web search for Ame.
Uses DuckDuckGo instant answers (no API key needed).
Returns a compact summary under ~300 tokens — never raw HTML dumps.
"""

import re
import httpx
import urllib.parse


async def quick_search(query: str) -> str:
    """Search DuckDuckGo and return a compact summary string (≤300 tokens)."""
    result = await _ddg_instant(query)
    if result:
        return result

    result = await _ddg_html(query)
    if result:
        return result

    return f"No direct answer found for: {query}. The web agent can browse for more detail."


async def _ddg_instant(query: str) -> str | None:
    """DuckDuckGo instant answer API."""
    try:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(url, headers={"User-Agent": "Ame-Assistant/1.0"})
        if resp.status_code != 200:
            return None

        data = resp.json()
        parts = []

        abstract = (data.get("AbstractText") or "").strip()
        if abstract:
            parts.append(_first_sentences(abstract, 2))

        answer = (data.get("Answer") or "").strip()
        if answer and answer not in parts:
            parts.append(answer)

        topics = data.get("RelatedTopics", [])
        topic_lines = []
        for t in topics[:3]:
            if isinstance(t, dict):
                text = (t.get("Text") or t.get("Result") or "").strip()
                if text:
                    topic_lines.append(_first_sentences(text, 1))
        if topic_lines:
            parts.extend(topic_lines)

        if not parts:
            return None

        summary = "\n".join(parts)
        return _cap_tokens(summary, 280)

    except Exception:
        return None


async def _ddg_html(query: str) -> str | None:
    """Scrape DuckDuckGo HTML results page."""
    try:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            return None

        html = resp.text

        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
        if not snippets:
            snippets = re.findall(r'<a[^>]+class="[^"]*result[^"]*"[^>]*>(.*?)</a>', html, re.DOTALL)

        clean = []
        for s in snippets[:3]:
            text = re.sub(r"<[^>]+>", "", s).strip()
            text = re.sub(r"\s+", " ", text)
            if len(text) > 20:
                clean.append(_first_sentences(text, 2))

        if not clean:
            return None

        return _cap_tokens("\n".join(clean), 280)

    except Exception:
        return None


def _first_sentences(text: str, n: int) -> str:
    """Return the first n sentences from text."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(sentences[:n])


def _cap_tokens(text: str, max_tokens: int) -> str:
    """Rough token cap: 1 token ≈ 4 chars."""
    limit = max_tokens * 4
    if len(text) > limit:
        return text[:limit].rsplit(" ", 1)[0] + "..."
    return text
