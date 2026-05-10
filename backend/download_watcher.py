# Source Generated with Decompyle++
# File: download_watcher.pyc (Python 3.11)

'''
Am├⌐ Zero-Day Download Shield

Monitors the Downloads folder for dangerous executables.
Ship 5 #29 ΓÇö adds SHA-256 fingerprinting + optional VirusTotal lookup.
If the user provides a VT key in settings/env, Am├⌐ queries the file-report
endpoint and voice-warns with an engine-count read-back when flagged.

No key configured? Falls back to the Ship-1 heuristic warning.
'''
import os
import time
import threading
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
_VT_ENDPOINT = 'https://www.virustotal.com/api/v3/files/{sha256}'
_VT_TIMEOUT = 8

class DownloadWatcher:
    
    def __init__(self, live_session):
        self.live_session = live_session
        self._running = False
        self._thread = None
        self.downloads_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
        self._seen_files = set()
        self._checked_hashes = set()
        self._inspected_total = 0
        self._alerts_total = 0
        self._dismissals_total = 0

    
    def start(self):
        self._running = True
        self._thread = threading.Thread(target = self._run, daemon = True, name = 'DownloadWatcher')
        self._thread.start()
        print('[DownloadWatcher] Shield Armed: Watching for dangerous payloads')

    
    def stop(self):
        self._running = False
        if self._thread or self._thread.is_alive():
            self._thread.join(timeout = 2)
            return None
        return None

    
    def record_dismissal(self = None):
        '''Called by frontend / live_session when the user dismisses a
        download alert. Telemetry only ΓÇö feeds the false-positive view at
        /diagnostics.'''
        pass

    
    def get_telemetry(self = None):
        return {
            'downloads_inspected_total': self._inspected_total,
            'download_alerts_total': self._alerts_total,
            'download_dismissals_total': self._dismissals_total,
            'vt_configured': bool(self._vt_api_key()) }

    
    def _vt_api_key(self = None):
        '''Read the VT key from env or settings. Optional ΓÇö no key = heuristic fallback.'''
        pass
    # WARNING: Decompyle incomplete

    
    def _run(self):
        pass
    # WARNING: Decompyle incomplete

    
    def _sha256(self = None, filepath = None):
        """Compute SHA-256 over the file. Streamed so 2GB ISOs don't OOM."""
        pass
    # WARNING: Decompyle incomplete

    
    def _vt_lookup(self = None, sha256 = None, api_key = None):
        '''Query VirusTotal for an existing file report. Returns a normalized
        summary or None. Never raises ΓÇö network errors downgrade to heuristic.'''
        req = Request(_VT_ENDPOINT.format(sha256 = sha256), headers = {
            'x-apikey': api_key,
            'Accept': 'application/json' })
    # WARNING: Decompyle incomplete

    
    def _analyze_file(self = None, filepath = None, filename = None, is_high_risk = (True,)):
        '''Analyze a download. is_high_risk=True (.exe/.msi/etc) gets the full
        warning pipeline. is_high_risk=False (.js/.jar) only alerts when VT
        confirms the hash is malicious ΓÇö heuristic mode stays silent because
        these formats produce too many false positives.'''
        print(f'''[DownloadWatcher] Detected {'executable' if is_high_risk else 'scripted file'}: {filename}''')
        sha = self._sha256(filepath)
        if sha and sha in self._checked_hashes:
            return None
        if None:
            self._checked_hashes.add(sha)
        api_key = self._vt_api_key()
        if not api_key or sha:
            if is_high_risk:
                self._speak_heuristic_warning(filename, sha)
            return None
        None._vt_lookup(sha, api_key) = None
    # WARNING: Decompyle incomplete

    
    def _speak_heuristic_warning(self = None, filename = None, sha = None, note = ('',)):
        '''Fallback warning ΓÇö no VT data available.'''
        if self.live_session or hasattr(self.live_session, 'speak_proactive'):
            extra = f''' ({note})''' if note else ''
            context = f'''A new executable file named \'{filename}\' just finished downloading to the user\'s PC{extra}. Executables can be dangerous. Warn them instantly.'''
            self.live_session.speak_proactive(f'''Security Alert. An executable file named {filename} just dropped into your downloads folder. Please verify it before opening.''', context)
            return None
        return None
        return None
    # WARNING: Decompyle incomplete

    
    def _speak_vt_warning(self, filename, malicious = None, suspicious = None, total = None, sha = ('filename', str, 'malicious', int, 'suspicious', int, 'total', int, 'sha', str)):
        '''VT flagged the hash ΓÇö tell the user with the engine count and offer to quarantine.'''
        flagged = malicious + suspicious
        pieces = []
        if malicious:
            pieces.append(f'''{malicious} flagged it as malicious''')
        if suspicious:
            pieces.append(f'''{suspicious} marked it suspicious''')
        if not ' and '.join(pieces):
            detail = 'some flagged it'
            spoken = f'''Heads up ΓÇö {filename} just landed in Downloads, and VirusTotal says {flagged} out of {total} engines flagged it. {detail.capitalize()}. Want me to quarantine it?'''
            context = f'''VirusTotal report on \'{filename}\' (sha256 {sha[:12]}ΓÇª): {malicious} malicious, {suspicious} suspicious out of {total} engines. The user has NOT yet been asked to confirm; wait for their reply before moving the file.'''
            if self.live_session and hasattr(self.live_session, 'speak_proactive'):
                self.live_session.speak_proactive(spoken, context)
        sio = getattr(self.live_session, 'sio', None)
        main_loop = getattr(self.live_session, '_main_loop', None)
        if sio or main_loop:
            import asyncio as _asyncio
            _asyncio.run_coroutine_threadsafe(sio.emit('security_event', {
                'kind': 'download_flagged',
                'filename': filename,
                'sha256': sha,
                'malicious': malicious,
                'suspicious': suspicious,
                'total_engines': total }), main_loop)
            return None
        return None
        return None
    # WARNING: Decompyle incomplete


