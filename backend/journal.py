# Source Generated with Decompyle++
# File: journal.pyc (Python 3.11)

__doc__ = 'Journal ΓÇö natural-language reflection over the tool-invocation audit log.\n\nReads `audit.iter_records()` for a given window and shapes a short, warm\nsummary Am├⌐ can read back when the user asks things like "what did you\ndo yesterday?" or "what have we been up to this week?".\n\nThis is *reflective*, not diagnostic. It groups actions, counts bursts,\nnames a few standouts ΓÇö it doesn\'t dump a log. Refusals and confirmation\ndenials are surfaced briefly because they\'re part of the story.\n'
from __future__ import annotations
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from backend import audit
# WARNING: Decompyle incomplete
