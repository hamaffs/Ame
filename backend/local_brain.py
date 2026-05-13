"""
Local brain wrapper — Ollama client for Gemma 3 (multimodal).

Purpose-built for Amé's router (providers.route). Keeps the offline-fallback
chat path in providers.py untouched; this module is specifically for the
purpose-routed background calls (memory extraction, intent gate, vision
decide, news filter, etc.).

Model priority:
  1. User override via env `AME_LOCAL_MODEL` (or OLLAMA_MODEL)
  2. `gemma3:4b`    (primary — 4B, multimodal)
  3. `gemma3:12b`   (optional upgrade for high-end machines)
  4. `llama3.2:3b`  (text-only safety net)

If Ollama isn't running or no preferred model is pulled, `available()` stays
False and the router falls through to Gemini Flash Lite automatically.

This module never raises on transport errors — callers treat a RuntimeError
as "local failed, fall through to cloud".
"""

from __future__ import annotations
import base64
import os
import time
import httpx


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_PREFERRED = ["gemma3:4b", "gemma3:12b", "llama3.2:3b"]


class _LocalBrain:
    def __init__(self):
        self._available = False
        self._probed = False
        self._model: str | None = None
        self._local_models: list[str] = []
        self._transport_dead_until = 0.0
        self._consecutive_timeouts = 0
        self._slow_until = 0.0
        self._SLOW_THRESHOLD = 3
        self._SLOW_COOLDOWN_S = 300

    async def probe(self) -> bool:
        """Check Ollama + pick a model. Safe to call repeatedly; caches result."""
        if self._probed:
            return self._available
        self._probed = True

        override = os.getenv("AME_LOCAL_MODEL") or os.getenv("OLLAMA_MODEL")
        candidates = ([override] if override else []) + _PREFERRED

        try:
            async with httpx.AsyncClient(base_url=OLLAMA_BASE_URL, timeout=4.0) as cx:
                r = await cx.get("/api/tags")
                if r.status_code != 200:
                    return False
                data = r.json()
                self._local_models = [m.get("name", "") for m in data.get("models", [])]
        except Exception as e:
            print(f"[local_brain] probe failed: {e}")
            return False

        for c in candidates:
            if c and c in self._local_models:
                self._model = c
                self._available = True
                print(f"[local_brain] online — using model {c}")
                return True

        print(f"[local_brain] no preferred model pulled (have: {self._local_models})")
        return False

    def available(self) -> bool:
        return self._available

    def probed(self) -> bool:
        return self._probed

    def chosen_model(self) -> str | None:
        return self._model

    def reset(self) -> None:
        """Forget cached result — next call to probe() will re-check."""
        self._probed = False
        self._available = False
        self._model = None
        self._transport_dead_until = 0.0
        self._consecutive_timeouts = 0
        self._slow_until = 0.0

    def generate(self,
                 prompt: str,
                 image_bytes: bytes | None = None,
                 system: str | None = None,
                 timeout: int = 30,
                 temperature: float = 0.4) -> str:
        """Send a single-turn generation to Ollama. Returns plain text.

        Raises RuntimeError on any failure — callers should fall through to cloud.
        """
        if not self._available or not self._model:
            raise RuntimeError("local_brain unavailable")
        if time.time() < self._transport_dead_until:
            raise RuntimeError("local_brain transport dead — recovering")
        if time.time() < self._slow_until:
            raise RuntimeError("local_brain slow — using cloud")

        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system
        if image_bytes:
            payload["images"] = [base64.b64encode(image_bytes).decode("ascii")]

        t0 = time.time()
        try:
            with httpx.Client(base_url=OLLAMA_BASE_URL, timeout=timeout) as cx:
                r = cx.post("/api/generate", json=payload)
            r.raise_for_status()
        except httpx.TimeoutException:
            self._consecutive_timeouts += 1
            if self._consecutive_timeouts >= self._SLOW_THRESHOLD:
                self._slow_until = time.time() + self._SLOW_COOLDOWN_S
            raise RuntimeError("local_brain timeout")
        except (httpx.TransportError, httpx.HTTPStatusError) as e:
            self._transport_dead_until = time.time() + 30
            raise RuntimeError(f"local_brain transport: {e}")

        self._consecutive_timeouts = 0
        elapsed = time.time() - t0
        if elapsed > 15:
            self._slow_until = time.time() + 120
        try:
            return (r.json().get("response") or "").strip()
        except Exception as e:
            raise RuntimeError(f"local_brain bad JSON: {e}")


local_brain = _LocalBrain()
