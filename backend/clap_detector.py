"""
Clap Detector — listens for double-clap patterns.
Fed audio from the live session's mic callback (no separate mic stream).
"""

import struct
import time
import math


class ClapDetector:
    "Monitors mic input for double-clap patterns while ignoring speech."

    # --- ADJUST THESE IF NEEDED ---
    CLAP_ABSOLUTE_MIN = 800     # Massively lowered to catch distant claps on cheap mics
    CLAP_MIN_SPIKE = 300        # Must jump just slightly above background baseline
    CLAP_MAX_DURATION = 0.4     # Increased to handle echoes from across the room
    DOUBLE_CLAP_WINDOW = 1.4    # Generous window for the second clap
    COOLDOWN = 2.0

    # --- SMART FILTERS (Reject breathing, music, and speech) ---
    MIN_CREST_FACTOR = 1.5      # Lowered significantly. Loud fan noise raises RMS, lowering the crest factor of claps.
    MIN_ZCR = 0.05              # Lowered slightly to tolerate fan noise mixing with the clap frequencies.

    def __init__(self, sio, loop, on_double_clap=None):
        self.sio = sio
        self._loop = loop
        self._on_double_clap = on_double_clap
        self._enabled = False
        self._baseline = 0
        self._last_clap_time = 0
        self._last_detection_time = 0
        self._in_spike = False
        self._spike_start = 0
        self._last_debug = 0

    def start(self):
        print("[ClapDetector] Started (fed from live session mic)")

    def stop(self):
        print("[ClapDetector] Stopped")

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
        print(f"[ClapDetector] {'Enabled' if enabled else 'Disabled'}")

    def _emit(self, event, data):
        import asyncio
        if self.sio and self._loop:
            try:
                asyncio.run_coroutine_threadsafe(self.sio.emit(event, data), self._loop)
            except Exception:
                pass

    def feed_audio(self, raw_bytes: bytes):
        """Called from the live session's mic callback with raw int16 PCM data."""
        if not self._enabled:
            return

        n_samples = len(raw_bytes) // 2
        if n_samples == 0:
            return

        samples = struct.unpack(f"<{n_samples}h", raw_bytes)
        peak = max(abs(s) for s in samples)
        now = time.monotonic()

        # Acoustic signature analysis
        sum_sq = sum(float(s) * s for s in samples)
        rms = math.sqrt(sum_sq / n_samples)
        crest_factor = peak / (rms + 1)
        crossings = sum(1 for i in range(1, n_samples) if (samples[i-1] * samples[i]) < 0)
        zcr = crossings / n_samples

        # Smart dynamic baseline to ignore background fans/hum
        # Only update if we aren't actively in a loud spike
        if not self._in_spike and peak < (self._baseline + self.CLAP_MIN_SPIKE):
            self._baseline = (self._baseline * 0.8) + (peak * 0.2)

        # Debug: log loud sounds
        if peak > self.CLAP_ABSOLUTE_MIN and (now - self._last_debug) > 0.5:
            import logging
            logging.debug(f"[ClapDetector] peak={peak} crest={crest_factor:.1f} zcr={zcr:.2f} base={int(self._baseline)}")
            self._last_debug = now

        # Cooldown after a successful double-clap
        if now - self._last_detection_time < self.COOLDOWN:
            return

        is_loud_enough = peak > self.CLAP_ABSOLUTE_MIN
        is_sharp_spike = peak > (self._baseline + self.CLAP_MIN_SPIKE)
        is_transient = crest_factor > self.MIN_CREST_FACTOR
        is_high_freq = zcr > self.MIN_ZCR

        if not self._in_spike:
            # Start spike ONLY if it sounds exactly like a clap (loud, sharp, transient, high freq)
            if is_loud_enough and is_sharp_spike and is_transient and is_high_freq:
                self._in_spike = True
                self._spike_start = now
        else:
            # We are currently in a spike. Wait for the volume to drop to end it.
            if not is_sharp_spike:
                spike_duration = now - self._spike_start
                self._in_spike = False

                if spike_duration < self.CLAP_MAX_DURATION:
                    if self._last_clap_time > 0 and (now - self._last_clap_time) < self.DOUBLE_CLAP_WINDOW:
                        print("[ClapDetector] Double clap detected!")
                        self._emit('dark_mode_triggered', {})
                        if self._on_double_clap:
                            self._on_double_clap()
                        self._last_detection_time = now
                        self._last_clap_time = 0
                    else:
                        print(f"[ClapDetector] First clap (peak={peak}, dur={spike_duration:.3f}s)")
                        self._last_clap_time = now
                else:
                    print(f"[ClapDetector] Spike too long ({spike_duration:.3f}s) — not a clap")
            else:
                # Volume is still high. Reject early if it goes on too long (music/talking).
                spike_duration = now - self._spike_start
                if spike_duration > self.CLAP_MAX_DURATION:
                    self._in_spike = False

        if self._last_clap_time > 0 and (now - self._last_clap_time) > self.DOUBLE_CLAP_WINDOW:
            self._last_clap_time = 0
