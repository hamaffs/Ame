# Source Generated with Decompyle++
# File: analyzer.pyc (Python 3.11)

__doc__ = "\nAM├ë Code Analyzer ΓÇö reads project files and builds context for Gemini.\nCalled by AM├ë's tool handler when the user asks about code.\n"
import sys
import os
os.environ.setdefault('PYTHONUTF8', '1')
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding = 'utf-8', errors = 'replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding = 'utf-8', errors = 'replace')
import shutil
from pathlib import Path
from backend import path_guard as _path_guard
# WARNING: Decompyle incomplete
