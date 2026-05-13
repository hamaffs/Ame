"""
Amé Memory Package — Three-layer memory system.
Layer 1: Identity (structured facts)
Layer 2: Graph (temporal knowledge graph)
Layer 3: Episodic (conversation history with FTS5 search)

This __init__.py exposes the exact function signatures that
live_session.py and server.py expect. Do not change these signatures.
"""

from __future__ import annotations
import threading

from backend.memory.core import AmeMemory
from backend.memory import identity as identity_layer  # re-exported as `identity`
from backend.memory import episodic as episodic_layer  # re-exported as `episodic`
from backend.memory import graph as graph_layer        # re-exported as `graph`

# Re-export submodules so callers can write `from backend.memory import episodic`.
identity = identity_layer
episodic = episodic_layer
graph    = graph_layer

_instance: AmeMemory | None = None
_lock = threading.Lock()


def _get_instance() -> AmeMemory:
    global _instance
    with _lock:
        if _instance is None:
            _instance = AmeMemory()
    return _instance


def load_memory() -> AmeMemory:
    """Returns the AmeMemory instance (has .get_memory_context_string())."""
    return _get_instance()


def _get_memory() -> AmeMemory:
    """Returns the AmeMemory instance. Used internally."""
    return _get_instance()


def update_structured_memory(category: str, key: str, value) -> None:
    """Update a single structured fact in Layer 1."""
    _get_instance().update_structured(category, key, value)


def update_memory(patch: dict) -> None:
    """Merge a partial structured_facts patch into Layer 1."""
    _get_instance().update_from_patch(patch)


def maybe_extract_memory_bg(user_text: str, assistant_text: str) -> None:
    """Background memory extraction after each turn. Non-blocking."""
    threading.Thread(
        target=_get_instance().extract_and_store,
        args=(user_text, assistant_text),
        daemon=True,
        name="mem-extract",
    ).start()


def maybe_extract_personality_bg(user_text: str, assistant_text: str) -> None:
    """Background personality refinement. Non-blocking, runs less often."""
    threading.Thread(
        target=_get_instance().extract_personality,
        args=(user_text, assistant_text),
        daemon=True,
        name="mem-personality",
    ).start()


def clear_memory() -> None:
    """Clear all three memory layers."""
    _get_instance().clear_all()
