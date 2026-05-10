# Source Generated with Decompyle++
# File: news_watcher.pyc (Python 3.11)

'''
Am├⌐ News Watcher ΓÇö startup awareness system.

Runs ONCE per session, 30s after startup:
1. Reads user memory for known interests
2. Searches for recent news on those topics
3. Uses Claude to evaluate if anything is worth mentioning
4. Injects a natural mention via send_system_instruction
'''
import os
import threading
import time
_has_run = False

def start_news_watcher(live_session):
    '''Launch the news watcher in a background thread. Call once at startup.'''
    global _has_run
    if _has_run:
        return None
    _has_run = None
    t = threading.Thread(target = _run, args = (live_session,), daemon = True, name = 'NewsWatcher')
    t.start()
    print('[NewsWatcher] Scheduled (30s delay)')


def _run(live_session):
    '''Main worker ΓÇö runs once after a 30s delay.'''
    time.sleep(30)
    _load_settings = _load_settings
    import backend.live_session
    if not _load_settings().get('news_enabled', True):
        print('[NewsWatcher] Disabled by user ΓÇö skipping')
        return None
# WARNING: Decompyle incomplete


def _get_user_topics():
    '''Extract up to 3 topics from user memory.'''
    pass
# WARNING: Decompyle incomplete


def _search_topic(topic = None):
    '''Search DuckDuckGo for recent news on a topic. Returns list of result strings.'''
    import httpx
    import urllib.parse as urllib
    query = f'''{topic} news'''
    encoded = urllib.parse.quote_plus(query)
    results = []
    url = f'''https://html.duckduckgo.com/html/?q={encoded}&df=d'''
    resp = httpx.get(url, headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' }, timeout = 8, follow_redirects = True)
# WARNING: Decompyle incomplete


def _evaluate_news(all_results = None):
    """Decide if any result is worth mentioning. Returns a sentence or None.

    Routes via Purpose.NEWS_FILTER ΓÇö local Gemma 4 first, then Gemini Flash
    Lite. Claude is never used here (stays out of the router path for
    free-tier users and isn't needed for a tiny filter classification).
    """
    route = route
    Purpose = Purpose
    import backend.providers
    lines = []
# WARNING: Decompyle incomplete

