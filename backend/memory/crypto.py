# Source Generated with Decompyle++
# File: crypto.pyc (Python 3.11)

__doc__ = '\nAt-rest encryption for Am├⌐ memory files.\n\nPrimary: Windows DPAPI (per-user, no passphrase needed).\nFallback: user-supplied passphrase via PBKDF2-HMAC-SHA256 + Fernet.\n\nPrecedence:\n1. DPAPI if available (Windows + pywin32) ΓÇö zero friction.\n2. Passphrase set via `set_passphrase(pp)` ΓÇö for non-Windows or when DPAPI missing.\n3. Plaintext ONLY if `_allow_plaintext` explicitly set True; otherwise raise loudly.\n\nCallers pass no secrets ΓÇö `encrypt_json` / `decrypt_json` pick the best\navailable scheme. The choice is stamped into the on-disk envelope so reads\nwork across mode changes.\n'
import sys
import os
import json
import base64
import hashlib
import threading
os.environ.setdefault('PYTHONUTF8', '1')
_dpapi_available = False
_dpapi_warning_emitted = False
if sys.platform == 'win32':
    import win32crypt
    _dpapi_available = True
# WARNING: Decompyle incomplete
