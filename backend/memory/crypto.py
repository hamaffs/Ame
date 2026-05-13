"""At-rest encryption for Amé memory files.

Primary on Windows: DPAPI (per-user, no passphrase needed).
Primary on Linux/macOS: user-supplied passphrase via PBKDF2-HMAC-SHA256 + Fernet.
Fallback everywhere: explicit plaintext when `_allow_plaintext` is set.

Callers pass no secrets — `encrypt_json` / `decrypt_json` pick the best
available scheme. The choice is stamped into the on-disk envelope so reads
work across mode changes.

On-disk format (JSON, one envelope per file):
    {
      "scheme": "dpapi" | "fernet" | "plaintext",
      "v": 1,
      "salt": <base64, only for fernet>,
      "payload": <base64 ciphertext, or plaintext JSON string>
    }
"""

from __future__ import annotations
import base64
import hashlib
import json
import os
import sys
import threading


_dpapi_available = False
_win32crypt = None
if sys.platform == "win32":
    try:
        import win32crypt as _win32crypt  # type: ignore
        _dpapi_available = True
    except Exception:
        _dpapi_available = False


_lock = threading.Lock()
_passphrase: str | None = None
_allow_plaintext = False


def set_passphrase(pp: str | None) -> None:
    """Caller (settings layer) supplies a user passphrase. None disables Fernet."""
    global _passphrase
    with _lock:
        _passphrase = pp


def set_allow_plaintext(allow: bool) -> None:
    """Opt-in escape hatch — only use in dev / unit tests."""
    global _allow_plaintext
    _allow_plaintext = bool(allow)


def is_available() -> dict:
    """What does the current process have to work with?"""
    return {
        "dpapi": _dpapi_available,
        "fernet": _passphrase is not None,
        "plaintext_allowed": _allow_plaintext,
    }


# ── Fernet derivation ──────────────────────────────────────────────────────

def _derive_fernet_key(passphrase: str, salt: bytes) -> bytes:
    """PBKDF2-HMAC-SHA256, 200k iterations → 32 bytes → urlsafe-b64 (Fernet shape)."""
    dk = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, 200_000, dklen=32)
    return base64.urlsafe_b64encode(dk)


def _fernet():
    """Lazy import — Fernet only needed when we're actually encrypting."""
    from cryptography.fernet import Fernet  # type: ignore
    return Fernet


# ── Public API ─────────────────────────────────────────────────────────────

def encrypt_json(obj) -> str:
    """Return a JSON-encoded envelope string."""
    raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")

    if _dpapi_available and _win32crypt is not None:
        try:
            blob = _win32crypt.CryptProtectData(raw, "ame", None, None, None, 0)
            return json.dumps({
                "scheme":  "dpapi",
                "v":       1,
                "payload": base64.b64encode(blob).decode("ascii"),
            })
        except Exception:
            pass  # fall through to next scheme

    if _passphrase:
        salt = os.urandom(16)
        key = _derive_fernet_key(_passphrase, salt)
        token = _fernet()(key).encrypt(raw)
        return json.dumps({
            "scheme":  "fernet",
            "v":       1,
            "salt":    base64.b64encode(salt).decode("ascii"),
            "payload": token.decode("ascii"),
        })

    if _allow_plaintext:
        return json.dumps({
            "scheme":  "plaintext",
            "v":       1,
            "payload": raw.decode("utf-8"),
        })

    raise RuntimeError(
        "No encryption available. Set a passphrase via set_passphrase(...) "
        "or call set_allow_plaintext(True) in dev."
    )


def decrypt_json(envelope: str):
    """Reverse of encrypt_json. Accepts any scheme this build supports."""
    if not envelope:
        return None
    try:
        env = json.loads(envelope)
    except Exception as e:
        raise ValueError(f"Not a valid envelope: {e}")

    scheme = env.get("scheme")

    if scheme == "dpapi":
        if not (_dpapi_available and _win32crypt):
            raise RuntimeError("Envelope was DPAPI-encrypted but DPAPI is not available here")
        blob = base64.b64decode(env["payload"])
        _, raw = _win32crypt.CryptUnprotectData(blob, None, None, None, 0)
        return json.loads(raw.decode("utf-8"))

    if scheme == "fernet":
        if not _passphrase:
            raise RuntimeError("Envelope was Fernet-encrypted but no passphrase is set")
        salt = base64.b64decode(env["salt"])
        key  = _derive_fernet_key(_passphrase, salt)
        raw  = _fernet()(key).decrypt(env["payload"].encode("ascii"))
        return json.loads(raw.decode("utf-8"))

    if scheme == "plaintext":
        return json.loads(env["payload"])

    raise ValueError(f"Unknown envelope scheme: {scheme!r}")
