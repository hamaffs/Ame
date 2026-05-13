"""At-rest encryption for Amé memory files — Linux edition.

Primary: user-supplied passphrase → PBKDF2-HMAC-SHA256 → Fernet (urlsafe AES-128).
Fallback: explicit plaintext when `set_allow_plaintext(True)` is called.

(The old Windows DPAPI branch is gone — Linux uses a passphrase, optionally
sourced from the secret service / gnome-keyring via the caller; this module
doesn't try to talk to the keyring itself, it just accepts the passphrase.)

On-disk format (JSON envelope, one per file):
    {
      "scheme":  "fernet" | "plaintext",
      "v":       1,
      "salt":    <base64, only for fernet>,
      "payload": <base64 ciphertext, or plaintext JSON string>
    }
"""

from __future__ import annotations
import base64
import hashlib
import json
import os
import threading


_lock = threading.Lock()
_passphrase: str | None = None
_allow_plaintext = False


def set_passphrase(pp: str | None) -> None:
    """Caller (settings layer / keyring bridge) supplies a user passphrase.
    None disables Fernet."""
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
        "dpapi": False,                     # always False on Linux — kept for API compat
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
        # Legacy envelope written by the old Windows build. We can't decrypt
        # these on Linux — surface a clear error so the caller can wipe and
        # re-seed memory rather than silently treating the file as empty.
        raise RuntimeError(
            "Encountered a Windows DPAPI envelope on Linux. "
            "Clear ~/.ame/memory/ to start fresh."
        )

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
