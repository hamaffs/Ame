# Source Generated with Decompyle++
# File: file_reader.pyc (Python 3.11)

'''File ingestion for Am├⌐ ΓÇö PDF / Excel / Word / image / text.

Single public entry point: `read_file(path_or_token, prompt=None)`. The
dispatcher routes by detected file kind (extension + magic bytes, which
must agree ΓÇö mismatch means quarantine). All extracted text is wrapped
through `untrusted.wrap` before it\'s returned to the model: uploaded
files are third-party content and may carry prompt-injection payloads.

Tokens issued by the `/upload` endpoint are opaque UUIDs registered via
`register_token(token, real_path, filename)`. Tools only ever see the
token, never the absolute path ΓÇö keeps prompt-injected "read /etc/shadow"
attempts out of reach of the model.
'''
from __future__ import annotations
import os
import re
import threading
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from backend import untrusted
from backend import path_guard
_token_lock = threading.Lock()
_tokens: 'dict[str, dict]' = { }

def register_token(token = None, path = None, filename = None, kind = ('',)):
    pass
# WARNING: Decompyle incomplete


def resolve_token(token = None):
    pass
# WARNING: Decompyle incomplete


def forget_token(token = None):
    pass
# WARNING: Decompyle incomplete

MAX_PDF_PAGES = 20
MAX_XLSX_PREVIEW_ROWS = 50
MAX_XLSX_FULL_ROWS = 500
MAX_TEXT_CHARS = 200000
MAX_FILE_BYTES = 26214400
_TEXT_EXTS = {
    '.c',
    '.h',
    '.cs',
    '.go',
    '.js',
    '.md',
    '.py',
    '.rb',
    '.rs',
    '.sh',
    '.ts',
    '.bat',
    '.cpp',
    '.css',
    '.csv',
    '.hpp',
    '.ini',
    '.jsx',
    '.log',
    '.php',
    '.ps1',
    '.tsx',
    '.txt',
    '.xml',
    '.yml',
    '.html',
    '.java',
    '.json',
    '.scss',
    '.toml',
    '.yaml'}
_IMAGE_EXTS = {
    '.bmp',
    '.gif',
    '.jpg',
    '.png',
    '.jpeg',
    '.webp'}
_MAGIC = {
    'pdf': (b'%PDF-',),
    'xlsx': (b'PK\x03\x04',),
    'docx': (b'PK\x03\x04',),
    'png': (b'\x89PNG\r\n\x1a\n',),
    'jpg': (b'\xff\xd8\xff',),
    'gif': (b'GIF87a', b'GIF89a'),
    'webp': (b'RIFF',),
    'bmp': (b'BM',) }

def _sniff_kind(path = None, head = None):
    """Return a normalized kind: pdf / xlsx / docx / image / text / unknown.
    Cross-checks extension against magic bytes; mismatches return 'mismatch'."""
    pass
# WARNING: Decompyle incomplete

Quarantine = <NODE:12>()

def _quarantine_check(path = None, kind = None, raw = dataclass):
    '''Return a Quarantine reason, or None if the file is clean enough to read.

    Covers the cheap-to-detect nasties: oversized files, PDF embedded JS,
    XLSX macro streams, explicit extension/magic mismatch.
    '''
    if path.stat().st_size > MAX_FILE_BYTES:
        return Quarantine(reason = f'''File is too large ({path.stat().st_size} bytes, cap {MAX_FILE_BYTES}).''')
    if None == 'mismatch':
        return Quarantine(reason = "File extension doesn't match its contents ΓÇö refusing to read.")
    if None == 'pdf' and re.search(b'/JavaScript\\b|/JS\\b|/OpenAction\\b', raw[:4194304]):
        return Quarantine(reason = 'PDF contains embedded JavaScript or auto-open actions.')
# WARNING: Decompyle incomplete


def read_pdf(path = None):
    '''Extract text from a PDF (capped at MAX_PDF_PAGES). Falls back to
    Gemini Vision per-page for image-only / scanned PDFs.'''
    PdfReader = PdfReader
    import pypdf
# WARNING: Decompyle incomplete


def _pdf_vision_ocr(path = None, pages = None):
    '''Render each page to PNG and send to Gemini Vision. Best-effort.'''
    PdfReader = PdfReader
    import pypdf
# WARNING: Decompyle incomplete


def read_excel(path = None, sheet = None, full = None):
    '''Read an .xlsx. Returns preview rows + sheet list + per-sheet row counts.'''
    pass
# WARNING: Decompyle incomplete


def read_docx(path = None):
    Document = Document
    import docx
# WARNING: Decompyle incomplete


def read_image(path = None, prompt = None):
    route = route
    Purpose = Purpose
    import backend.providers
    _call_gemini_vision = _call_gemini_vision
    import backend.vision
# WARNING: Decompyle incomplete


def read_text(path = None):
    pass
# WARNING: Decompyle incomplete


def read_file(path_or_token = None, prompt = None):
    '''Resolve a token or path and route to the correct reader.

    Token form: short opaque UUID registered via register_token. Raw path
    form is also accepted but must pass path_guard.
    '''
    if not path_or_token:
        return {
            'success': False,
            'error': 'No path or token provided.' }
    info = None(path_or_token)
    if info:
        real_path = Path(info['path'])
        friendly_source = f'''upload:{info.get('filename', 'file')}'''
    else:
        real_path = Path(path_or_token).expanduser().resolve()
# WARNING: Decompyle incomplete

AUTO_READ_PREVIEW_CHARS = 8000

def resolve_image_bytes(path_or_token = None):
    '''Resolve an upload token ΓåÆ raw image bytes + MIME, after running the
    same safety pipeline as `read_file` (path_guard + magic-byte quarantine).

    Used by the Live-direct image ingest path, which hands bytes straight to
    Gemini Live so there\'s no separate vision round-trip. Returns:
        { success: True, bytes: bytes, mime_type: str, kind: "image",
          filename: str, path: str }
    or { success: False, error: str, quarantined: bool? }
    '''
    if not path_or_token:
        return {
            'success': False,
            'error': 'No path or token provided.' }
    info = None(path_or_token)
    if info:
        real_path = Path(info['path'])
        filename = info.get('filename', real_path.name)
    else:
        real_path = Path(path_or_token).expanduser().resolve()
# WARNING: Decompyle incomplete


def auto_read_preview(path_or_token = None):
    """Read a file and return a short preview for auto-injection after upload.

    Same safety pipeline as `read_file` (path_guard, quarantine, untrusted.wrap),
    just truncates to `AUTO_READ_PREVIEW_CHARS` so the live session isn't
    flooded with a huge document on every upload. Full read is still available
    via the normal `read_file` tool call if the user asks for depth.
    """
    result = read_file(path_or_token)
    if not result.get('success'):
        return result
    text = None.get('text', '')
    if len(text) > AUTO_READ_PREVIEW_CHARS:
        head = text[:AUTO_READ_PREVIEW_CHARS]
        result['text'] = head + "\n[...preview truncated ΓÇö ask for 'read the full file' to see more...]"
        result['preview'] = True
    else:
        result['preview'] = False
    return result

