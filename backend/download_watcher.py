"""
Amé Zero-Day Download Shield

Monitors the Downloads folder for dangerous executables. Optional VirusTotal
lookup when a key is configured. Without a VT key, falls back to a heuristic
warning that fires on the file extension alone.
"""

from __future__ import annotations
import hashlib
import json
import os
import threading
import time
from pathlib import Path
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen


_VT_ENDPOINT = "https://www.virustotal.com/api/v3/files/{sha256}"
_VT_TIMEOUT  = 8

# File extensions Amé treats as high-risk (warn on every drop, even without VT).
_HIGH_RISK_EXTS = {
    ".exe", ".msi", ".bat", ".cmd", ".ps1", ".scr", ".com",
    ".vbs", ".vbe", ".wsf", ".hta", ".cpl", ".lnk", ".reg",
    ".jar", ".dll", ".sys", ".pif",
    # Linux / cross
    ".sh", ".run", ".AppImage", ".deb", ".rpm",
}
_LOW_RISK_EXTS = {".js", ".py", ".rb", ".pl", ".php"}  # warn only when VT says so


class DownloadWatcher:
    def __init__(self, live_session):
        self.live_session = live_session
        self._running = False
        self._thread: threading.Thread | None = None
        self.downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        self._seen_files: set[str] = set()
        self._checked_hashes: set[str] = set()
        self._inspected_total = 0
        self._alerts_total = 0
        self._dismissals_total = 0

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="DownloadWatcher")
        self._thread.start()
        print("[DownloadWatcher] Shield Armed: Watching for dangerous payloads")

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def record_dismissal(self) -> None:
        self._dismissals_total += 1

    def get_telemetry(self) -> dict:
        return {
            "downloads_inspected_total": self._inspected_total,
            "download_alerts_total": self._alerts_total,
            "download_dismissals_total": self._dismissals_total,
            "vt_configured": bool(self._vt_api_key()),
        }

    # ── internal ──────────────────────────────────────────────────────────
    def _vt_api_key(self) -> str | None:
        from_env = os.getenv("VIRUSTOTAL_API_KEY")
        if from_env:
            return from_env
        try:
            from backend.live_session import _load_settings
            return _load_settings().get("virustotal_api_key") or None
        except Exception:
            return None

    def _run(self) -> None:
        if not os.path.isdir(self.downloads_dir):
            print(f"[DownloadWatcher] {self.downloads_dir} not present — watcher idle")
            return
        # Seed with whatever's already there so we don't alert on startup.
        try:
            self._seen_files = set(os.listdir(self.downloads_dir))
        except Exception:
            self._seen_files = set()
        while self._running:
            try:
                current = set(os.listdir(self.downloads_dir))
            except Exception:
                time.sleep(3)
                continue
            new = current - self._seen_files
            for fname in new:
                fpath = os.path.join(self.downloads_dir, fname)
                # Wait for the download to finish before fingerprinting.
                if not os.path.isfile(fpath):
                    continue
                size = os.path.getsize(fpath)
                time.sleep(0.5)
                try:
                    if os.path.getsize(fpath) != size:
                        # Still being written — re-check next loop.
                        continue
                except OSError:
                    continue
                ext = os.path.splitext(fname)[1].lower()
                if ext in _HIGH_RISK_EXTS:
                    self._inspected_total += 1
                    self._analyze_file(fpath, fname, is_high_risk=True)
                elif ext in _LOW_RISK_EXTS:
                    self._inspected_total += 1
                    self._analyze_file(fpath, fname, is_high_risk=False)
            self._seen_files = current
            time.sleep(3)

    def _sha256(self, filepath: str) -> str | None:
        try:
            h = hashlib.sha256()
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            return h.hexdigest()
        except Exception as e:
            print(f"[DownloadWatcher] sha256 failed for {filepath}: {e}")
            return None

    def _vt_lookup(self, sha256: str, api_key: str) -> dict | None:
        req = Request(_VT_ENDPOINT.format(sha256=sha256),
                      headers={"x-apikey": api_key, "Accept": "application/json"})
        try:
            with urlopen(req, timeout=_VT_TIMEOUT) as resp:
                if resp.status != 200:
                    return None
                data = json.loads(resp.read())
        except (URLError, HTTPError, TimeoutError, json.JSONDecodeError) as e:
            print(f"[DownloadWatcher] VT lookup failed: {e}")
            return None
        attrs = data.get("data", {}).get("attributes", {}) if isinstance(data, dict) else {}
        stats = attrs.get("last_analysis_stats") or {}
        return {
            "malicious":  int(stats.get("malicious", 0)),
            "suspicious": int(stats.get("suspicious", 0)),
            "harmless":   int(stats.get("harmless", 0)),
            "undetected": int(stats.get("undetected", 0)),
            "total":      sum(int(v or 0) for v in stats.values()),
        }

    def _analyze_file(self, filepath: str, filename: str, is_high_risk: bool = True) -> None:
        print(f"[DownloadWatcher] Detected {'executable' if is_high_risk else 'scripted file'}: {filename}")
        sha = self._sha256(filepath)
        if sha and sha in self._checked_hashes:
            return
        if sha:
            self._checked_hashes.add(sha)
        api_key = self._vt_api_key()
        if not api_key or not sha:
            if is_high_risk:
                self._speak_heuristic_warning(filename, sha or "")
            return
        report = self._vt_lookup(sha, api_key)
        if report and (report["malicious"] or report["suspicious"]):
            self._speak_vt_warning(filename, report["malicious"], report["suspicious"], report["total"], sha)
        elif is_high_risk:
            self._speak_heuristic_warning(filename, sha)

    def _speak_heuristic_warning(self, filename: str, sha: str = "", note: str = "") -> None:
        if self.live_session and hasattr(self.live_session, "speak_proactive"):
            extra = f" ({note})" if note else ""
            context = (f"A new executable file named '{filename}' just finished downloading"
                       f" to the user's PC{extra}. Executables can be dangerous. Warn them instantly.")
            try:
                self.live_session.speak_proactive(
                    f"Security Alert. An executable file named {filename} just dropped into "
                    "your downloads folder. Please verify it before opening.",
                    context,
                )
                self._alerts_total += 1
            except Exception as e:
                print(f"[DownloadWatcher] speak_proactive failed: {e}")

    def _speak_vt_warning(self, filename: str, malicious: int, suspicious: int, total: int, sha: str) -> None:
        flagged = malicious + suspicious
        pieces = []
        if malicious:  pieces.append(f"{malicious} flagged it as malicious")
        if suspicious: pieces.append(f"{suspicious} marked it suspicious")
        detail = " and ".join(pieces) or "some flagged it"
        spoken = (f"Heads up — {filename} just landed in Downloads, and VirusTotal says "
                  f"{flagged} out of {total} engines flagged it. {detail.capitalize()}. "
                  "Want me to quarantine it?")
        context = (f"VirusTotal report on '{filename}' (sha256 {sha[:12]}…): "
                   f"{malicious} malicious, {suspicious} suspicious out of {total} engines.")
        if self.live_session and hasattr(self.live_session, "speak_proactive"):
            try:
                self.live_session.speak_proactive(spoken, context)
                self._alerts_total += 1
            except Exception as e:
                print(f"[DownloadWatcher] speak_proactive failed: {e}")
