"""
Multi-provider LLM manager for Amé.
Fallback chain: Gemini → Ollama (local, offline).
"""

import os
import time
import asyncio
import httpx
from backend import load_env

load_env()

# ── Cloud providers (tried in order) ────────────────────────────────────────

PROVIDERS = [
    {
        "name": "Gemini",
        "model": "gemini-2.5-flash",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "api_key_env": "GOOGLE_AI_STUDIO_KEY",
        "fallback_models": ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"],
        "supports_tools": True,
    },
]

# ── Ollama configuration (local, no API key needed) ─────────────────────────

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_API_URL = f"{OLLAMA_BASE_URL}/v1"

# Preferred Ollama models in priority order — the first one found locally wins.
# Users can override with OLLAMA_MODEL env var.
OLLAMA_PREFERRED_MODELS = [
    "llama3.1",
    "llama3",
    "mistral",
    "gemma2",
    "phi3",
    "qwen2",
    "deepseek-coder-v2",
    "codellama",
]

# Tools that require internet and should be disabled in offline mode
OFFLINE_DISABLED_TOOLS = {
    "web_search_ddg", "google_search", "scrape_and_summarize",
    "open_url", "open_youtube", "open_google_maps", "search_travel",
    "run_web_task", "browser_open", "browser_click", "browser_fill",
    "browser_scroll", "browser_press_key", "browser_get_text",
    "browser_close", "browser_screenshot_analyze", "go_back",
    "send_email", "read_recent_emails", "track_orders",
    "play_song_on_spotify", "play_music_on_spotify", "play_spotify_by_mood",
    "pause_spotify", "resume_spotify", "next_track", "previous_track",
}

OFFLINE_ANSWERS = {
    "time": lambda: f"It's {__import__('datetime').datetime.now().strftime('%I:%M %p')}.",
    "date": lambda: f"Today is {__import__('datetime').datetime.now().strftime('%A, %B %d, %Y')}.",
    "default": "I'm having trouble reaching my AI providers right now. Try again in a moment.",
}


class ProviderManager:
    """Manages LLM provider rotation with Ollama offline fallback. Thread-safe for async use."""

    def __init__(self):
        self._provider_idx = 0
        self._model_idx = 0
        self._cooldowns: dict[str, float] = {}
        self.active_provider_name = PROVIDERS[0]["name"]
        self.active_model = PROVIDERS[0]["model"]
        self.is_offline = False
        self._ollama_available = False
        self._ollama_model: str | None = None
        self._ollama_checked = False
        self._lock = asyncio.Lock()
        # Callback for notifying the frontend about provider changes
        self._on_provider_change = None

    def set_provider_change_callback(self, callback):
        """Register a callback(provider_name, is_offline) for UI updates."""
        self._on_provider_change = callback

    def _notify_provider_change(self):
        """Notify listeners about a provider or offline state change."""
        if self._on_provider_change:
            try:
                self._on_provider_change(self.active_provider_name, self.is_offline)
            except Exception as e:
                print(f"[Amé] Provider change callback error: {e}")

    def _get_api_key(self, provider: dict) -> str | None:
        return os.getenv(provider["api_key_env"])

    def _provider_available(self, provider: dict) -> bool:
        key = self._get_api_key(provider)
        if not key or key.startswith("your_"):
            return False
        cooldown = self._cooldowns.get(provider["name"], 0)
        return time.time() > cooldown

    def _set_cooldown(self, provider_name: str, seconds: int = 60):
        self._cooldowns[provider_name] = time.time() + seconds

    def get_status(self) -> str:
        """Short string shown in the UI status panel."""
        if self.is_offline:
            return f"Ollama/{self._ollama_model or '?'} (offline)"
        return f"{self.active_provider_name}/{self.active_model.split('/')[-1]}"

    async def check_ollama(self) -> bool:
        """Probe Ollama at startup. Discovers the best available model.
        Called once during backend init — non-blocking, failure is fine."""
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")

            if resp.status_code != 200:
                self._ollama_available = False
                self._ollama_checked = True
                return False

            data = resp.json()
            local_models = [m.get("name", "") for m in data.get("models", [])]

            if not local_models:
                print("[Amé] Ollama running but no models pulled. Run: ollama pull llama3.1")
                self._ollama_available = False
                self._ollama_checked = True
                return False

            # Strip :tag suffixes for matching (e.g. "llama3.1:latest" → "llama3.1")
            local_base = {m.split(":")[0]: m for m in local_models}

            # Check user override first
            user_model = os.getenv("OLLAMA_MODEL")
            if user_model and user_model in local_base:
                self._ollama_model = local_base[user_model]
            elif user_model and user_model in local_models:
                self._ollama_model = user_model
            else:
                # Pick the first preferred model that's available locally
                for preferred in OLLAMA_PREFERRED_MODELS:
                    if preferred in local_base:
                        self._ollama_model = local_base[preferred]
                        break

                # If none of our preferred models found, use whatever is first
                if not self._ollama_model:
                    self._ollama_model = local_models[0]

            self._ollama_available = True
            self._ollama_checked = True
            print(f"[Amé] Ollama available — model: {self._ollama_model} (from {len(local_models)} local models)")
            return True

        except Exception as e:
            print(f"[Amé] Ollama not available: {e}")
            self._ollama_available = False
            self._ollama_checked = True
            return False

    async def chat(
        self,
        messages: list,
        tools: list | None = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> dict:
        """Send a chat request. Falls back to Ollama if all cloud providers fail."""
        async with self._lock:
            return await self._chat_inner(messages, tools, max_tokens, temperature)

    async def _chat_inner(self, messages, tools, max_tokens, temperature) -> dict:
        # Build attempt list from cloud providers
        attempts = []
        for provider in PROVIDERS:
            for model in provider["fallback_models"]:
                attempts.append((provider, model))

        last_err = "All providers exhausted."
        was_offline = self.is_offline

        # Try cloud providers first
        for provider, model in attempts:
            if not self._provider_available(provider):
                continue

            api_key = self._get_api_key(provider)
            if not api_key:
                continue

            use_tools = tools if provider.get("supports_tools") else None

            try:
                response = await self._call_openai_compat(
                    base_url=provider["base_url"],
                    api_key=api_key,
                    model=model,
                    messages=messages,
                    tools=use_tools,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    provider_name=provider["name"],
                )
                self.active_provider_name = provider["name"]
                self.active_model = model
                # Came back online from offline
                if was_offline:
                    self.is_offline = False
                    print(f"[Amé] Back online — {provider['name']}/{model}")
                    self._notify_provider_change()
                return response

            except RateLimitError:
                print(f"[Amé] Rate limited on {provider['name']}/{model}")
                last_err = f"Rate limited: {provider['name']}"
                continue

            except ProviderError as e:
                print(f"[Amé] Provider error {provider['name']}/{model}: {e}")
                self._set_cooldown(provider["name"], seconds=120)
                last_err = str(e)
                break

            except Exception as e:
                print(f"[Amé] Unexpected error {provider['name']}/{model}: {e}")
                last_err = str(e)
                continue

        # ── All cloud providers failed — try Ollama ──────────────────────────
        if not self._ollama_checked:
            await self.check_ollama()

        if self._ollama_available and self._ollama_model:
            try:
                # Strip internet-dependent tools for offline mode
                offline_tools = None
                if tools:
                    offline_tools = [t for t in tools
                                     if t.get("function", {}).get("name") not in OFFLINE_DISABLED_TOOLS]
                    if not offline_tools:
                        offline_tools = None

                response = await self._call_openai_compat(
                    base_url=OLLAMA_API_URL,
                    api_key="ollama",  # Ollama doesn't need a real key
                    model=self._ollama_model,
                    messages=messages,
                    tools=offline_tools,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    provider_name="Ollama",
                    timeout=120,  # Local models can be slower
                )
                if not self.is_offline:
                    self.is_offline = True
                    self.active_provider_name = f"Ollama (offline)"
                    self.active_model = self._ollama_model
                    print(f"[Amé] OFFLINE MODE — using Ollama/{self._ollama_model}")
                    self._notify_provider_change()
                return response

            except Exception as e:
                print(f"[Amé] Ollama fallback also failed: {e}")
                last_err = f"All providers + Ollama failed: {e}"

        raise RuntimeError(last_err)

    async def _call_openai_compat(
        self,
        base_url: str,
        api_key: str,
        model: str,
        messages: list,
        tools: list | None,
        max_tokens: int,
        temperature: float,
        provider_name: str,
        timeout: int = 30,
    ) -> dict:
        """Make an OpenAI-compatible chat completions request via httpx."""
        url = f"{base_url.rstrip('/')}/chat/completions"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload: dict = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)

        if resp.status_code == 429:
            raise RateLimitError(f"429 from {provider_name}")

        if resp.status_code in (400, 422):
            body = resp.text
            if "decommission" in body.lower() or "deprecated" in body.lower():
                raise RateLimitError(f"Decommissioned model on {provider_name}")
            raise ProviderError(f"Bad request {provider_name}: {body[:200]}")

        if resp.status_code == 503:
            raise ProviderError(f"503 service unavailable: {provider_name}")

        if resp.status_code != 200:
            raise ProviderError(f"HTTP {resp.status_code} from {provider_name}: {resp.text[:200]}")

        return resp.json()


class RateLimitError(Exception):
    pass

class ProviderError(Exception):
    pass


provider_manager = ProviderManager()
