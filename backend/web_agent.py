# Source Generated with Decompyle++
# File: web_agent.pyc (Python 3.11)

'''
Simple synchronous web tools for Am├⌐ AI assistant.
Handles opening URLs, searching the web, and scraping page content.
'''
import urllib.parse as urllib
import webbrowser

def _url_to_friendly(url = None, query = None):
    '''Convert a URL to a human-readable name without exposing the raw URL.'''
    pass
# WARNING: Decompyle incomplete


def open_url(url = None):
    '''Open a URL in the default system browser. Only http/https schemes are permitted.'''
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return {
            'success': False,
            'message': f'''Blocked: URL scheme \'{parsed.scheme}\' is not allowed. Only http/https URLs are supported.''' }
    None(f'''[open_url] Opening: {url}''')
    webbrowser.open(url)
    friendly = _url_to_friendly(url)
    return {
        'success': True,
        'message': f'''Opened {friendly}.''',
        'context': f'''Browser is now showing {friendly}. The user can see this page.''' }
# WARNING: Decompyle incomplete


def google_search(query = None):
    '''Open Google in the default browser with a search query.'''
    encoded = urllib.parse.quote_plus(query)
    url = f'''https://www.google.com/search?q={encoded}'''
    webbrowser.open(url)
    return {
        'success': True,
        'message': f'''Opened Google search for \'{query}\'.''',
        'context': f'''Browser is now showing Google search results for: {query}. The user can see the results.''' }
# WARNING: Decompyle incomplete


def open_google_maps(location = None):
    '''Open Google Maps in the default browser for a given location.'''
    encoded = urllib.parse.quote_plus(location)
    url = f'''https://www.google.com/maps/search/{encoded}'''
    webbrowser.open(url)
    return {
        'success': True,
        'message': f'''Opened Google Maps for \'{location}\'.''' }
# WARNING: Decompyle incomplete


def open_youtube(query = None):
    '''Open YouTube in the default browser with a search query.'''
    encoded = urllib.parse.quote_plus(query)
    url = f'''https://www.youtube.com/results?search_query={encoded}'''
    webbrowser.open(url)
    return {
        'success': True,
        'message': f'''Opened YouTube search for \'{query}\'.''' }
# WARNING: Decompyle incomplete


def play_latest_from_youtuber(channel_name = None):
    """Open the newest video from a specific YouTuber's channel.

    Resolves the channel (not a random search result), then opens
    /@handle/videos and plays the first videoId on that page.
    """
    import httpx
    import re as _re
# WARNING: Decompyle incomplete


def search_travel(origin = None, destination = None, date = None, time = ('', '', '', '', ''), mode = ('origin', str, 'destination', str, 'date', str, 'time', str, 'mode', str, 'return', dict)):
    '''Open Google Travel pre-filled with travel details. Works for any country, any route.'''
    if not mode:
        mode_lower = ''.lower()
        parts = []
        if not mode_lower == 'flight' or mode_lower:
            if origin:
                parts.append(f'''flights from {origin}''')
            else:
                parts.append('flights')
        elif origin:
            parts.append(f'''{mode_lower} from {origin}''')
        else:
            parts.append(mode_lower)
    if destination:
        parts.append(f'''to {destination}''')
    if date:
        parts.append(date)
    if time:
        parts.append(f'''at {time}''')
    query = ' '.join(parts)
    encoded = urllib.parse.quote_plus(query)
    if not mode_lower in ('flight', 'flights', '') or mode_lower:
        url = f'''https://www.google.com/travel/flights?q={encoded}'''
    else:
        url = f'''https://www.google.com/travel?q={encoded}'''
    webbrowser.open(url)
    desc_parts = []
    if origin:
        desc_parts.append(f'''from {origin}''')
    if destination:
        desc_parts.append(f'''to {destination}''')
    if date:
        desc_parts.append(f'''on {date}''')
    if time:
        desc_parts.append(f'''at {time}''')
# WARNING: Decompyle incomplete


def scrape_and_summarize(url = None):
    '''Fetch the readable text content of a web page using Playwright.'''
    sync_playwright = sync_playwright
    import playwright.sync_api
    net_guard = net_guard
    import backend
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    (ok, info) = net_guard.resolve_and_check(url)
    if not ok:
        return {
            'success': False,
            'message': f'''Blocked: {info.get('reason', 'URL guard refused')}''',
            'blocked': True }
    url = None['url']
# WARNING: Decompyle incomplete

