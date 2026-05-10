"""Redact secrets from anything written to stdout/stderr and the stdlib logger.

The rest of the codebase prints liberally. If an API key, bearer token, or
other secret sneaks into a print string, this module catches it before the
bytes leave the process — without touching the caller.
"""

import re
import sys
import logging

_KEY_PATTERNS = [
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"), "[REDACTED_ANTHROPIC_KEY]"),
    # S-12: tightened Google API key pattern to exactly 35 chars after AIza
    # (matches real Google API key format and avoids false positives).
    (re.compile(r"AIza[A-Za-z0-9_\-]{35}"), "[REDACTED_GOOGLE_KEY]"),
    (re.compile(r"ghp_[A-Za-z0-9]{36}"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"gho_[A-Za-z0-9]{36}"), "[REDACTED_GITHUB_TOKEN]"),
    # S-12: fine-grained PATs
    (re.compile(r"github_pat_[A-Za-z0-9_]{80,}"), "[REDACTED_GITHUB_PAT]"),
    (re.compile(r"Bearer\s+[A-Za-z0-9_\-\.=]{20,}", re.IGNORECASE), "Bearer [REDACTED]"),
    (re.compile(r"xoxb-[A-Za-z0-9\-]{20,}"), "[REDACTED_SLACK_TOKEN]"),
    (re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"), "[REDACTED_JWT]"),
    # S-12: Google OAuth client secrets, access tokens, refresh tokens
    (re.compile(r"GOCSPX-[A-Za-z0-9_\-]{20,}"), "[REDACTED_GOOGLE_OAUTH_SECRET]"),
    (re.compile(r"ya29\.[A-Za-z0-9_\-]{20,}"), "[REDACTED_GOOGLE_OAUTH_ACCESS]"),
    (re.compile(r"1//[A-Za-z0-9_\-]{40,}"), "[REDACTED_GOOGLE_OAUTH_REFRESH]"),
    # S-12: Spotify bearer-ish
    (re.compile(r"BQ[A-Za-z0-9_\-]{50,}"), "[REDACTED_SPOTIFY_TOKEN]"),
]


def redact(s: str) -> str:
    if not s:
        return s
    for pat, repl in _KEY_PATTERNS:
        s = pat.sub(repl, s)
    return s


class _RedactingStream:
    """File-like wrapper that redacts before delegating to the underlying stream."""

    def __init__(self, inner):
        self._inner = inner

    def write(self, data):
        try:
            if isinstance(data, str):
                return self._inner.write(redact(data))
        except Exception:
            pass
        return self._inner.write(data)

    def flush(self):
        try:
            return self._inner.flush()
        except Exception:
            return None

    def __getattr__(self, name):
        return getattr(self._inner, name)


class _RedactingLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.msg, str):
                record.msg = redact(record.msg)
            if record.args:
                if isinstance(record.args, dict):
                    record.args = {k: redact(v) if isinstance(v, str) else v
                                   for k, v in record.args.items()}
                elif isinstance(record.args, tuple):
                    record.args = tuple(
                        redact(a) if isinstance(a, str) else a for a in record.args
                    )
        except Exception:
            pass
        return True


_installed = False


def install() -> None:
    """Idempotent. Wraps sys.stdout/stderr and installs a root-logger filter."""
    global _installed
    if _installed:
        return
    _installed = True

    try:
        if not isinstance(sys.stdout, _RedactingStream):
            sys.stdout = _RedactingStream(sys.stdout)
        if not isinstance(sys.stderr, _RedactingStream):
            sys.stderr = _RedactingStream(sys.stderr)
    except Exception as e:
        print(f"[LogGuard] stream wrap failed: {e}")

    try:
        logging.getLogger().addFilter(_RedactingLogFilter())
    except Exception as e:
        print(f"[LogGuard] logger filter install failed: {e}")
