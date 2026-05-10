# Source Generated with Decompyle++
# File: local_brain.pyc (Python 3.11)

'''
Local brain wrapper ΓÇö Ollama client for Gemma 3 (multimodal).

Purpose-built for Am├⌐\'s router (providers.route). Keeps the offline-fallback
chat path in providers.py untouched; this module is specifically for the
purpose-routed background calls (memory extraction, intent gate, vision
decide, news filter, etc.).

Model priority:
  1. User override via env `AME_LOCAL_MODEL`
  2. `gemma3:4b`    (primary ΓÇö 4B, multimodal, 128K ctx, ~3.3GB)
  3. `gemma3:12b`   (optional upgrade for high-end machines)
  4. `llama3.2:3b`  (text-only safety net)

If Ollama isn\'t running or no preferred model is pulled, `available()` stays
False and the router falls through to Gemini Flash Lite automatically.

Exposes:
  probe() -> bool         # async, discovers a usable model
  available() -> bool     # sync, cached result
  chosen_model() -> str   # the model string we\'ll send
  generate(prompt, image_bytes=None, timeout=...) -> str

This module never raises on transport errors ΓÇö callers treat a RuntimeError
as "local failed, fall through to cloud".
'''
from __future__ import annotations
import base64
import os
import httpx
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
_PREFERRED = [
    'gemma3:4b',
    'gemma3:12b',
    'llama3.2:3b']

class _LocalBrain:
    
    def __init__(self = None):
        self._available = False
        self._probed = False
        self._model = None
        self._local_models = []
        self._transport_dead_until = 0
        self._consecutive_timeouts = 0
        self._slow_until = 0
        self._SLOW_THRESHOLD = 3
        self._SLOW_COOLDOWN_S = 300

    
    async def probe(self = None):
        '''Check Ollama + pick a model. Safe to call repeatedly; caches result.'''
        pass
    # WARNING: Decompyle incomplete

    
    def available(self = None):
        return self._available

    
    def probed(self = None):
        return self._probed

    
    def chosen_model(self = None):
        return self._model

    
    def reset(self = None):
        '''Forget cached result ΓÇö next call to probe() will re-check.'''
        self._probed = False
        self._available = False
        self._model = None
        self._transport_dead_until = 0
        self._consecutive_timeouts = 0
        self._slow_until = 0

    
    def generate(self, prompt = None, image_bytes = None, system = None, timeout = (None, None, 30, 0.4), temperature = ('prompt', 'str', 'image_bytes', 'bytes | None', 'system', 'str | None', 'timeout', 'int', 'temperature', 'float', 'return', 'str')):
        '''Send a single-turn generation to Ollama. Returns plain text.

        Raises RuntimeError on any failure ΓÇö callers should fall through to cloud.
        Multimodal: if `image_bytes` is provided, sent as base64 in `images`.
        '''
        import time as _time
        if not self._available or self._model:
            raise RuntimeError('local_brain unavailable')
        if _time.time() < self._transport_dead_until:
            raise RuntimeError('local_brain transport dead ΓÇö recovering')
        if _time.time() < self._slow_until:
            raise RuntimeError('local_brain slow ΓÇö using cloud')
        payload = {
            'model': self._model,
            'prompt': prompt,
            'stream': False,
            'options': {
                'temperature': temperature } }
        if system:
            payload['system'] = system
        if image_bytes:
            payload['images'] = [
                base64.b64encode(image_bytes).decode('ascii')]
    # WARNING: Decompyle incomplete


local_brain = _LocalBrain()
