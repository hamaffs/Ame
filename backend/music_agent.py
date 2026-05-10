"""
Music control for Amé AI assistant.
Handles Spotify (via spotipy) and YouTube (via system browser) playback.
"""

import sys, os
os.environ.setdefault('PYTHONUTF8', '1')
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'): sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import ctypes
import time
import urllib.parse
from typing import Optional

from backend import load_env, get_cache_dir

load_env()

_sp = None


def _get_spotify():
    """Lazily initialise and return the spotipy client."""
    global _sp
    if _sp is not None:
        return _sp

    import spotipy
    from spotipy.oauth2 import SpotifyPKCE
    from spotipy.cache_handler import CacheFileHandler

    # Hardcode YOUR public Spotify Developer Client ID here.
    # Because we are using PKCE, it is 100% safe to expose this Client ID to the public.
    client_id = "1d6a71e15763488a9a61a16ebe37f128"
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")

    if not client_id:
        raise RuntimeError("SPOTIFY_CLIENT_ID must be set in your .env file.")

    scope = (
        "user-read-playback-state "
        "user-modify-playback-state "
        "user-read-currently-playing"
    )

    cache_dir = get_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / ".cache-spotify"

    _sp = spotipy.Spotify(
        auth_manager=SpotifyPKCE(
            client_id=client_id,
            redirect_uri=redirect_uri,
            scope=scope,
            open_browser=True,
            cache_handler=CacheFileHandler(cache_path=str(cache_path)),
        )
    )
    return _sp


def _get_active_device_id(sp) -> Optional[str]:
    """Return the first active Spotify device ID, or None."""
    try:
        devices = sp.devices()
        device_list = devices.get("devices", [])
        for d in device_list:
            if d.get("is_active"):
                return d["id"]
        if device_list:
            return device_list[0]["id"]
    except Exception:
        pass
    return None


def _ensure_spotify_open_and_get_device(sp) -> Optional[str]:
    """Get an active Spotify device ID, opening Spotify if needed."""
    from backend.pc_control import open_application
    open_application("spotify")

    # Retry up to 4 times — Spotify on Windows can take 8-15s to register
    # as a Connect device via the API after launch
    for wait in (3, 3, 4, 5):
        time.sleep(wait)
        try:
            devices = sp.devices().get("devices", [])
            if devices:
                # Prefer computer/PC, fallback to first available
                for d in devices:
                    if d.get("type", "").lower() in ("computer", "pc"):
                        return d["id"]
                return devices[0]["id"]
        except Exception as e:
            print(f"[Music] Device poll error (will retry): {e}")

    print("[Music] Could not find any Spotify device after launch")
    return None


def get_available_devices() -> list[dict]:
    """Return all available Spotify Connect devices."""
    sp = _get_spotify()
    devices = sp.devices()
    return devices.get('devices', [])


def select_device(user_request: str = None) -> Optional[str]:
    """Pick the best Spotify device based on user request or sensible defaults."""
    devices = get_available_devices()
    if not devices:
        return None

    if user_request:
        user_request_lower = user_request.lower()
        for device in devices:
            name = device.get('name', '').lower()
            type_ = device.get('type', '').lower()
            if 'phone' in user_request_lower and type_ == 'smartphone':
                return device['id']
            if 'tv' in user_request_lower and type_ == 'tv':
                return device['id']
            if name and name in user_request_lower:
                return device['id']
            if type_ and type_ in user_request_lower:
                return device['id']

    # Default: prefer computer/PC device
    for device in devices:
        type_ = device.get('type', '').lower()
        if type_ in ('computer', 'pc'):
            return device['id']

    # Fallback: first available device
    return devices[0]['id'] if devices else None


def _press_media_key(vk_code: int) -> None:
    """Send a Windows media key press/release event."""
    KEYEVENTF_KEYUP = 0x0002
    ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)


def _parse_song_artist(query: str):
    """Try to split 'song by artist' into (song, artist)."""
    import re
    m = re.match(r'^(.+?)\s+by\s+(.+)$', query, re.IGNORECASE)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return query.strip(), None


def play_song_on_spotify(query: str, device_hint: str = None) -> dict:
    """Search Spotify for a track and start playback on the active device."""
    try:
        sp = _get_spotify()

        song_part, artist_part = _parse_song_artist(query)

        # Search with the exact query first — don't modify or simplify it
        results = sp.search(q=query, type="track", limit=5)
        tracks = results.get("tracks", {}).get("items", [])

        # Fallback: try structured search if exact query found nothing
        if not tracks and artist_part:
            search_q = f"track:{song_part} artist:{artist_part}"
            results = sp.search(q=search_q, type="track", limit=5)
            tracks = results.get("tracks", {}).get("items", [])

        if not tracks:
            return {"success": False, "message": f"No track found on Spotify for '{query}'."}

        best = tracks[0]
        if artist_part:
            artist_lower = artist_part.lower()
            for t in tracks:
                t_artists = [a["name"].lower() for a in t.get("artists", [])]
                if any(artist_lower in a or a in artist_lower for a in t_artists):
                    best = t
                    break
        else:
            best = max(tracks, key=lambda t: t.get("popularity", 0))

        track = best
        track_uri = track["uri"]
        track_name = track["name"]
        artist_name = track["artists"][0]["name"] if track["artists"] else "Unknown Artist"

        # Smart device selection: user hint > PC default > open Spotify fallback
        device_id = select_device(device_hint) if device_hint else select_device()
        if not device_id:
            device_id = _ensure_spotify_open_and_get_device(sp)
        if not device_id:
            return {
                "success": False,
                "message": (
                    "No active Spotify device found. Please open Spotify and start playing something first."
                ),
            }

        sp.start_playback(device_id=device_id, uris=[track_uri])
        return {
            "success": True,
            "track": track_name,
            "artist": artist_name,
        }

    except RuntimeError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        return {"success": False, "message": f"Spotify playback error: {e}"}


def play_spotify_by_mood(mood_or_genre: str, device_hint: str = None) -> dict:
    """Search Spotify for a playlist matching the mood/genre and start playback."""
    print(f"[Music] play_spotify_by_mood: '{mood_or_genre}'")

    try:
        # Check if we have a valid Spotify token
        token = _get_spotify().auth_manager.get_cached_token()
        print(f"[Music] Token status: {'valid' if token else 'NONE/EXPIRED'}")
    except Exception as e:
        print(f"[Music] Token error: {e}")
        return {"success": False, "message": "Spotify not connected"}

    try:
        sp = _get_spotify()
        print(f"[Music] Got spotify client: {sp is not None}")

        queries_to_try = [
            mood_or_genre,
            f"{mood_or_genre} music",
            f"{mood_or_genre} playlist",
            f"best {mood_or_genre}",
        ]

        playlist = None
        for query in queries_to_try:
            print(f"[Music] Trying search: '{query}'")
            results = sp.search(q=query, type="playlist", limit=5)
            items = results.get("playlists", {}).get("items", [])
            items = [i for i in items if i is not None]
            if items:
                playlist = items[0]
                print(f"[Music] Found with query '{query}': {playlist.get('name')}")
                break
            print(f"[Music] No results for '{query}'")

        if playlist is None:
            print("[Music] No playlist found for mood: " + mood_or_genre)
            return {"success": False, "message": "Couldn't find a playlist for that mood. Try something like 'hip hop', 'jazz', or 'pop'?"}

        print(f"[Music] Selected: {playlist.get('name')}, {playlist.get('uri')}")

        playlist_uri = playlist["uri"]
        playlist_name = playlist["name"]

        # Smart device selection: user hint > PC default > open Spotify fallback
        device_id = select_device(device_hint) if device_hint else select_device()
        if not device_id:
            device_id = _ensure_spotify_open_and_get_device(sp)
        if not device_id:
            return {
                "success": False,
                "message": "No active Spotify device found. Please open Spotify first.",
            }

        sp.start_playback(device_id=device_id, context_uri=playlist_uri)
        return {
            "success": True,
            "playlist": playlist_name,
        }

    except Exception as e:
        import traceback
        print(f"[Music] CRASH: {e}")
        traceback.print_exc()
        # Log the Spotify API response if available
        resp_body = getattr(e, 'response', None)
        if resp_body is not None:
            try:
                print(f"[MusicAgent] Spotify API response status: {resp_body.status_code}")
                print(f"[MusicAgent] Spotify API response body: {resp_body.text}")
            except Exception:
                print(f"[MusicAgent] Spotify API raw response: {resp_body}")
        return {"success": False, "message": f"Music error: {e}"}


def play_music_on_youtube(query: str) -> dict:
    """Search YouTube for a song and open the first result in the browser."""
    import webbrowser
    import re
    import requests

    search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(search_url, headers=headers, timeout=10)
        video_ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', resp.text)
        if video_ids:
            video_url = f"https://www.youtube.com/watch?v={video_ids[0]}"
            webbrowser.open(video_url)
            return {"success": True}
    except Exception:
        pass

    webbrowser.open(search_url)
    return {"success": True}


def play_music_on_spotify() -> dict:
    """Open the Spotify desktop application."""
    from backend.pc_control import open_application
    return open_application("spotify")


def pause_music() -> dict:
    """Send the system media play/pause key to pause or resume playback."""
    try:
        VK_MEDIA_PLAY_PAUSE = 0xB3
        _press_media_key(VK_MEDIA_PLAY_PAUSE)
        return {"success": True, "action": "toggled"}
    except Exception as e:
        return {"success": False, "message": f"Failed to toggle play/pause: {e}"}


def pause_spotify() -> dict:
    """Pause the currently playing Spotify track."""
    try:
        sp = _get_spotify()
        sp.pause_playback()
        return {"success": True, "action": "paused"}
    except Exception as e:
        # Fallback: use media key (works with any player, no OAuth needed)
        try:
            VK_MEDIA_PLAY_PAUSE = 0xB3
            _press_media_key(VK_MEDIA_PLAY_PAUSE)
            return {"success": True, "action": "paused (media key)"}
        except Exception:
            pass
        print(f"[Music] pause_spotify error: {e}")
        return {"success": False, "message": f"Failed to pause: {e}"}


def resume_spotify() -> dict:
    """Resume the paused Spotify track."""
    try:
        sp = _get_spotify()
        sp.start_playback()
        return {"success": True, "action": "resumed"}
    except Exception as e:
        # Fallback: use media key (works with any player, no OAuth needed)
        try:
            VK_MEDIA_PLAY_PAUSE = 0xB3
            _press_media_key(VK_MEDIA_PLAY_PAUSE)
            return {"success": True, "action": "resumed (media key)"}
        except Exception:
            pass
        print(f"[Music] resume_spotify error: {e}")
        return {"success": False, "message": f"Failed to resume: {e}"}


def next_track() -> dict:
    """Send the system media next-track key."""
    try:
        VK_MEDIA_NEXT_TRACK = 0xB0
        _press_media_key(VK_MEDIA_NEXT_TRACK)
        return {"success": True, "action": "skipped"}
    except Exception as e:
        return {"success": False, "message": f"Failed to skip track: {e}"}


def previous_track() -> dict:
    """Send the system media previous-track key."""
    try:
        VK_MEDIA_PREV_TRACK = 0xB1
        _press_media_key(VK_MEDIA_PREV_TRACK)
        return {"success": True, "action": "previous"}
    except Exception as e:
        return {"success": False, "message": f"Failed to go to previous track: {e}"}
