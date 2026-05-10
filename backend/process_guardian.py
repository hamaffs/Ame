# Source Generated with Decompyle++
# File: process_guardian.pyc (Python 3.11)

__doc__ = '\nAm├⌐ Process Guardian.\n\nLive background watcher for new processes and outbound TCP connections.\nPermission-aware:\n  - low  ΓåÆ not started at all.\n  - mid  ΓåÆ passive logging only (writes to ~/.ame/security/guardian.log), no voice.\n  - high ΓåÆ active alerts via live_session.speak_proactive when something looks off.\n\nThis is a soft heuristic layer, not an IDS. The goal is for Am├⌐ to feel like a\nguardian who notices things ΓÇö not to replace real security tooling.\n'
import os
import json
import time
import threading
from datetime import datetime
from pathlib import Path
import psutil
# WARNING: Decompyle incomplete
