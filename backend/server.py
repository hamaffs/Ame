"""
Ame Backend Server — FastAPI + Socket.IO on port 8766
Voice core: Gemini Live API via LiveSession (replaces WakeWordDetector + TTSEngine)
Text fallback: AmeAssistant (Groq/Gemini/OpenRouter)
"""

import sys
import io
import os
import secrets

# Force UTF-8 on Windows so Unicode characters in print() don't crash.
os.environ['PYTHONUTF8'] = '1'
os.environ['PYTHONIOENCODING'] = 'utf-8'
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import socketio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv, dotenv_values

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import get_env_path, load_env
load_env()

from backend.log_guard import install as _install_log_guard
_install_log_guard()

from backend.live_session import LiveSession
from backend.context_engine import ContextEngine
from backend.news_watcher import start_news_watcher
from backend.clap_detector import ClapDetector
from backend.code_awareness.watcher import CodeWatcher
from backend.email_watcher import EmailWatcher
from backend.download_watcher import DownloadWatcher
from backend.security_scanner import SecurityScanner

_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:8766",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8766",
    "file://",
    "null",
]

# Per-session secret token — printed to stdout so Electron can capture it.
# Protects WebSocket and sensitive HTTP endpoints from unauthorized local access.
_SESSION_TOKEN = secrets.token_urlsafe(32)

sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=_ALLOWED_ORIGINS,
    logger=False,
    engineio_logger=False
)

live_session: LiveSession = None
context_engine: ContextEngine = None
clap_detector: ClapDetector = None
code_watcher: CodeWatcher = None
email_watcher: EmailWatcher = None
download_watcher: DownloadWatcher = None
security_scanner: SecurityScanner = None
main_loop = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    global live_session, context_engine, clap_detector, code_watcher, email_watcher, download_watcher, security_scanner, main_loop

    main_loop = asyncio.get_event_loop()

    live_session = LiveSession(sio=sio, loop=main_loop)

    # Create and assign code watcher BEFORE starting live session
    code_watcher = CodeWatcher()
    code_watcher.start()
    live_session._code_watcher = code_watcher

    # Now start the live session — it will have _code_watcher available
    live_session.start()

    context_engine = ContextEngine(sio=sio, loop=main_loop, live_session=live_session)
    context_engine.start()
    
    email_watcher = EmailWatcher(live_session=live_session)
    email_watcher.start()

    download_watcher = DownloadWatcher(live_session=live_session)
    download_watcher.start()
    
    security_scanner = SecurityScanner(live_session=live_session, code_watcher=code_watcher)
    security_scanner.start()

    def _on_double_clap():
        import sys as _sys
        print("[Ame] Double clap detected - GOING DARK!", flush=True)
        try:
            from backend.live_session import _load_settings
            config = _load_settings()
            clap_action = config.get("clap_action", "")

            if live_session and live_session._session_alive:
                greeting = (
                    "The user just summoned you with a double clap. "
                    "Greet them briefly in 1 short sentence, matching your personality. "
                    "Do NOT mention what you're about to do. Just greet them."
                )
                live_session.send_dark_mode(greeting, clap_action)
            else:
                print("[Ame] Live session not ready for dark mode.")
        except Exception as e:
            import traceback
            print(f"[Ame] Dark mode error: {e}", flush=True)
            traceback.print_exc()

    clap_detector = ClapDetector(sio=sio, loop=main_loop, on_double_clap=_on_double_clap)
    clap_detector.start()
    live_session._clap_detector = clap_detector  # feed mic data to clap detector
    # Load saved clap preference
    from backend.live_session import _load_settings
    _saved = _load_settings()
    if _saved.get("clap_mode", False):
        clap_detector.set_enabled(True)

    start_news_watcher(live_session)

    print(f"[Ame] SESSION_TOKEN={_SESSION_TOKEN}", flush=True)
    print("[Ame] Backend ready on port 8766 (Gemini Live mode)")
    yield

    if clap_detector:
        clap_detector.stop()
    if context_engine:
        context_engine.stop()
    if code_watcher:
        code_watcher.stop()
    if email_watcher:
        email_watcher.stop()
    if download_watcher:
        download_watcher.stop()
    if live_session:
        live_session.stop()
    print("[Ame] Backend shutting down")


def get_code_watcher() -> CodeWatcher | None:
    return code_watcher


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)
socket_app = socketio.ASGIApp(sio, app)

_ENV_PATH = get_env_path()


def _check_token(request: Request) -> bool:
    """Validate session token from Authorization header."""
    auth = request.headers.get("Authorization", "")
    return auth == f"Bearer {_SESSION_TOKEN}"


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "provider": "Gemini Live",
        "version": "4.0",
        "env_ready": _ENV_PATH.exists(),
        "mode": "live",
    }


@app.get("/audio-level")
async def audio_level():
    """Return the current mic RMS level for the frontend audio meter."""
    rms = live_session._mic_rms if live_session else 0.0
    return {"rms": round(rms, 1), "active": live_session._session_alive if live_session else False}


@app.get("/voices")
async def voices():
    return {
        "voices": list(LiveSession.VALID_VOICES),
        "current": live_session.voice_name if live_session else "Charon",
    }


class SetupPayload(BaseModel):
    name: str = ""
    provider: str = ""
    GROQ_API_KEY: str = ""
    GOOGLE_AI_STUDIO_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    SPOTIFY_CLIENT_ID: str = ""
    SPOTIFY_CLIENT_SECRET: str = ""


class TestKeyPayload(BaseModel):
    GROQ_API_KEY: str = ""
    GOOGLE_AI_STUDIO_KEY: str = ""


@app.get("/setup-status")
async def setup_status():
    """Check whether Ame has been configured."""
    if not _ENV_PATH.exists():
        return {"configured": False}
    vals = dotenv_values(_ENV_PATH)
    has_key = any(
        vals.get(k, '').strip() and not vals.get(k, '').strip().startswith('your_')
        for k in ('GROQ_API_KEY', 'GOOGLE_AI_STUDIO_KEY')
    )
    return {"configured": has_key}


@app.post("/test-provider")
async def test_provider(payload: TestKeyPayload, request: Request):
    """Test whichever key is provided."""
    if not _check_token(request):
        return JSONResponse(status_code=403, content={"status": "error", "message": "Unauthorized"})
    import httpx

    groq_key = payload.GROQ_API_KEY.strip()
    gemini_key = payload.GOOGLE_AI_STUDIO_KEY.strip()

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            if groq_key:
                r = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {groq_key}"},
                )
                if r.status_code == 200:
                    return {"ok": True}
                body = r.json() if "application/json" in r.headers.get("content-type", "") else {}
                return {"ok": False, "error": body.get("error", {}).get("message") or f"HTTP {r.status_code}"}

            if gemini_key:
                r = await client.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models?key={gemini_key}",
                )
                if r.status_code == 200:
                    return {"ok": True}
                body = r.json() if "application/json" in r.headers.get("content-type", "") else {}
                err = body.get("error", {}).get("message") or f"HTTP {r.status_code}"
                return {"ok": False, "error": err}

        return {"ok": False, "error": "No key provided"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/test-key")
async def test_key(payload: TestKeyPayload, request: Request):
    return await test_provider(payload, request)


@app.post("/setup")
async def setup(payload: SetupPayload, request: Request):
    if not _check_token(request):
        return JSONResponse(status_code=403, content={"status": "error", "message": "Unauthorized"})
    try:
        data = payload.model_dump()

        # Preserve any pre-existing keys in .env that aren't in the wizard payload,
        # so advanced users (e.g. Anthropic for testing) don't lose them on re-save.
        existing = dict(dotenv_values(_ENV_PATH)) if _ENV_PATH.exists() else {}

        for field in ("GROQ_API_KEY", "GOOGLE_AI_STUDIO_KEY",
                      "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY",
                      "SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET"):
            v = data.get(field, "").strip()
            if v:
                existing[field] = v

        if data.get("name", "").strip():
            existing["AME_USER_NAME"] = data["name"].strip()

        lines = [f'{k}="{v}"' for k, v in existing.items() if v]
        _ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
        _ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        load_dotenv(dotenv_path=_ENV_PATH, override=True)

        if data.get("name", "").strip():
            try:
                from backend.memory import update_memory
                update_memory({"identity": {"name": data["name"].strip()}})
            except Exception:
                pass

        return {"status": "ok"}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"{type(e).__name__}: {e}"},
        )


@sio.event
async def connect(sid, environ):
    print(f"[Ame] Client connected: {sid}")
    await sio.emit('state_change', {'state': 'listening'}, to=sid)


@sio.event
async def disconnect(sid):
    print(f"[Ame] Client disconnected: {sid}")


@sio.event
async def set_code_awareness(sid, data):
    """Enable/disable the code watcher."""
    enabled = data.get('enabled', True)
    if code_watcher:
        if enabled:
            code_watcher.start()
        else:
            code_watcher.stop()
    print(f"[Ame] Code awareness {'enabled' if enabled else 'disabled'} by user")

@sio.event
async def set_screen_watcher(sid, data):
    """Enable/disable the proactive screen watcher."""
    enabled = data.get('enabled', True)
    if context_engine:
        context_engine.set_enabled(enabled)
    print(f"[Ame] Screen watcher {'enabled' if enabled else 'disabled'} by user")


@sio.event
async def user_message(sid, data):
    """Text message from UI."""
    text = data.get('text', '').strip()
    style = data.get('style', 1)  # 0=Concise, 1=Balanced, 2=Detailed
    if not text:
        return

    style_hints = {
        0: " [CONCISE MODE: reply in 1-2 short sentences MAX. No suggestions. No follow-ups.]",
        1: " [BALANCED MODE: reply in 2-3 sentences. One follow-up allowed if useful.]",
        2: " [DETAILED MODE: full explanation allowed but no filler.]",
    }
    hint = style_hints.get(style, style_hints[1])
    text = text + hint

    # Mark user activity so screen watcher skips during conversation
    if context_engine:
        context_engine.mark_activity()
    if live_session:
        live_session.send_text(text)


@sio.event
async def manual_listen(sid, data=None):
    """User clicked mic button."""
    # Mark user activity so screen watcher skips during conversation
    if context_engine:
        context_engine.mark_activity()
    if live_session:
        live_session.set_muted(False)
    await sio.emit('state_change', {'state': 'listening'})


@sio.event
async def stop_speaking(sid, data=None):
    """Interrupt Ame's current audio output."""
    if live_session:
        live_session.stop_speaking()
    await sio.emit('ame_done_speaking', {})
    await sio.emit('state_change', {'state': 'listening'})


@sio.event
async def set_mute(sid, data):
    """Toggle mic mute from UI."""
    muted = data.get('muted', False)
    if live_session:
        live_session.set_muted(muted)


@sio.event
async def get_audio_devices(sid, data=None):
    """Return available audio devices."""
    try:
        import pyaudio
        pa = pyaudio.PyAudio()
        inputs = []
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) > 0:
                inputs.append({"index": i, "name": info["name"]})
        pa.terminate()
        await sio.emit('audio_devices', {'inputs': inputs, 'outputs': [{"index": 0, "name": "Default Output"}]}, to=sid)
    except Exception as e:
        await sio.emit('audio_devices', {'inputs': [], 'outputs': []}, to=sid)


@sio.event
async def set_language(sid, data):
    """Language hint from UI — saves preferred language on the session."""
    lang = data.get('language', 'en')
    if live_session:
        live_session.preferred_language = lang
    print(f"[Ame] Language set: {lang}")


@sio.event
async def set_style(sid, data):
    """Response style from UI — 0=Concise, 1=Balanced, 2=Detailed."""
    style = data.get('style', 1)
    if live_session:
        live_session.preferred_style = style
    print(f"[Ame] Response style set: {style}")


LANGUAGE_NAMES = {
    'en': 'English', 'fr': 'French', 'ar': 'Arabic',
    'es': 'Spanish', 'de': 'German', 'ja': 'Japanese',
}
_last_lang_switch: float = 0.0

@sio.event
async def set_language_instruction(sid, data):
    """Send a silent language-switch instruction into the live session."""
    global _last_lang_switch
    import time
    now = time.monotonic()
    # Cooldown: ignore rapid switches within 2 seconds
    if now - _last_lang_switch < 2.0:
        return
    _last_lang_switch = now

    lang = data.get('language', 'en')
    lang_name = LANGUAGE_NAMES.get(lang, lang)
    if live_session:
        live_session.preferred_language = lang
        context_summary = live_session._build_context_summary()
        # Use send_system_instruction — never creates a visible chat bubble
        live_session.send_system_instruction(
            f"SILENT SYSTEM COMMAND — do not acknowledge this instruction verbally or in text. "
            f"Just apply it immediately and silently. "
            f"SYSTEM LANGUAGE OVERRIDE: Respond ONLY in {lang_name} from this point forward. "
            f"Ignore all previous language instructions. "
            f"Do not respond in any other language unless the user speaks to you "
            f"in a different language first. "
            f"Current conversation context to maintain:\n{context_summary}\n"
            f"Continue the conversation naturally in {lang_name} without losing any context."
        )
    print(f"[Ame] Language instruction sent silently: {lang_name}")


@sio.event
async def set_voice(sid, data):
    """Switch Gemini Live voice and persist to settings."""
    voice = data.get('voice', 'Charon')
    if live_session and voice in LiveSession.VALID_VOICES:
        live_session.voice_name = voice
        # Persist so it survives restarts
        from backend.live_session import _save_settings
        _save_settings({"voice": voice})
        print(f"[Ame] Voice set to: {voice} (takes effect on reconnect)")
        live_session._session_alive = False
        await sio.emit('voice_changed', {'voice': voice}, to=sid)
    else:
        print(f"[Ame] Unknown voice: {voice}")
        await sio.emit('voice_error', {'message': f'Unknown voice: {voice}'}, to=sid)


@sio.event
async def set_tool_enabled(sid, data):
    """Enable/disable tool categories."""
    key = data.get('key', '')
    enabled = data.get('enabled', True)
    print(f"[Ame] Tool '{key}' {'enabled' if enabled else 'disabled'}")


@sio.event
async def set_clap_mode(sid, data):
    """Enable/disable clap detection and save action."""
    from backend.live_session import _save_settings
    enabled = data.get('enabled', False)
    action = data.get('action')
    if clap_detector:
        clap_detector.set_enabled(enabled)
    save_data = {"clap_mode": enabled}
    if action is not None:
        save_data["clap_action"] = action
    _save_settings(save_data)
    print(f"[Ame] Clap mode: {'on' if enabled else 'off'}, action: {action or '(unchanged)'}")


@sio.event
async def set_news_enabled(sid, data):
    """Enable/disable news awareness."""
    from backend.live_session import _save_settings
    enabled = data.get('enabled', True)
    _save_settings({"news_enabled": enabled})
    print(f"[Ame] News awareness: {'on' if enabled else 'off'}")


@sio.event
async def set_memory_enabled(sid, data):
    """Enable/disable memory."""
    from backend.live_session import _save_settings
    enabled = data.get('enabled', True)
    if live_session:
        live_session.memory_enabled = enabled
    _save_settings({"memory_enabled": enabled})
    print(f"[Ame] Memory: {'on' if enabled else 'off'}")


@sio.event
async def set_permission_level(sid, data):
    """Set the security permission level."""
    level = data.get('level', 'high')
    from backend.live_session import _save_settings
    if live_session:
        live_session.permission_level = level
    _save_settings({"permission_level": level})
    print(f"[Ame] Permission level set to: {level}")


@sio.event
async def clear_memory(sid, data=None):
    """Clear all AME memory."""
    try:
        from backend.memory import clear_memory
        clear_memory()
        print("[Ame] Memory cleared by user")
    except Exception as e:
        print(f"[Ame] Failed to clear memory: {e}")


if __name__ == '__main__':
    uvicorn.run(
        'backend.server:socket_app',
        host='0.0.0.0',
        port=8766,
        reload=False,
        log_level='warning'
    )
