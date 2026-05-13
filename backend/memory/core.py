"""
Core memory orchestrator for Ame.
Single entry point that coordinates all three memory layers.
"""

import sys, os
os.environ.setdefault('PYTHONUTF8', '1')
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'): sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import json
import threading
from datetime import date
from typing import List, Dict, Any

from backend.memory import identity as layer1
from backend.memory import graph as layer2
from backend.memory import episodic as layer3

_MAX_TOTAL_CHARS = 2800  # ~800 tokens


class AmeMemory:
    """
    Three-layer memory system for AME.
    Layer 1: Identity (identity.py) — fast structured facts, always loaded
    Layer 2: Graph (graph.py) — digital life knowledge graph, queried on demand
    Layer 3: Episodic (episodic.py) — verbatim conversation history, semantic search
    """

    def __init__(self):
        self._identity_data = layer1.load_identity()
        self._identity_lock = threading.Lock()
        # extract_personality / extract_and_store run in background threads and
        # increment these counters to gate "every-Nth-turn" extraction work.
        # The lock protects them across concurrent turns.
        self._counter_lock = threading.Lock()
        self._extract_turn_counter = 0
        self._personality_turn_counter = 0

    def get_memory_context_string(self) -> str:
        """
        Assemble the full memory context for injection into the system prompt.
        Always includes Layer 1 identity block.
        Includes Layer 2 graph context block.
        Does NOT include Layer 3 episodic here — that's queried on demand.
        Total stays under ~800 tokens.
        """
        try:
            # Build identity section (like old memory.py)
            with self._identity_lock:
                data = self._identity_data

            sf_name = (data.get("identity", {}).get("name") or {}).get("value")
            display_name = sf_name if sf_name else "User"
            pref_lang = (data.get("identity", {}).get("preferred_language") or {}).get("value", "en")

            lines = [
                f"User name: {display_name}",
                f"Preferred language: {pref_lang}",
            ]

            # Layer 1 facts block
            facts_str = layer1.get_prompt_block(data)
            if facts_str:
                lines.append(facts_str)

            identity_block = "\n".join(lines)

            # Layer 2 graph block
            try:
                graph_block = layer2.get_context_block()
            except Exception as e:
                print(f"[memory:core] graph context error: {e}")
                graph_block = ""

            # Combine and cap
            if graph_block:
                combined = identity_block + "\n\n" + graph_block
            else:
                combined = identity_block

            # If over budget, trim graph first
            if len(combined) > _MAX_TOTAL_CHARS and graph_block:
                available = _MAX_TOTAL_CHARS - len(identity_block) - 2
                if available > 50:
                    combined = identity_block + "\n\n" + graph_block[:available]
                else:
                    combined = identity_block[:_MAX_TOTAL_CHARS]

            return combined
        except Exception as e:
            print(f"[memory:core] get_memory_context_string error: {e}")
            return "User name: User\nPreferred language: en"

    def update_structured(self, category: str, key: str, value: str) -> None:
        """Update a fact in Layer 1 identity store."""
        try:
            layer1.update_fact(category, key, value)
            with self._identity_lock:
                self._identity_data = layer1.load_identity()
        except Exception as e:
            print(f"[memory:core] update_structured error: {e}")

    def update_from_patch(self, patch: dict) -> None:
        """Apply a structured_facts-format patch dict to Layer 1."""
        try:
            with self._identity_lock:
                self._identity_data = layer1.update_from_patch(self._identity_data, patch)
                layer1.save_identity(self._identity_data)
        except Exception as e:
            print(f"[memory:core] update_from_patch error: {e}")

    def store_conversation_turn(self, user_text: str, ame_text: str) -> None:
        """Store a completed turn into Layer 3 episodic store."""
        try:
            layer3.store_turn(user_text, ame_text)
        except Exception as e:
            print(f"[memory:core] store_turn error: {e}")

    def search_episodes(self, query: str) -> str:
        """Search Layer 3 for relevant past conversations."""
        try:
            return layer3.search_relevant(query)
        except Exception as e:
            print(f"[memory:core] search_episodes error: {e}")
            return ""

    def extract_and_store(self, user_text: str, ame_text: str) -> None:
        """
        Background extraction pipeline — called after every turn.
        1. Check if conversation contains memorable facts
        2. If yes: extract structured facts and update Layer 1
        3. Extract entities and relationships and update Layer 2 graph
        4. Store the turn verbatim in Layer 3
        """
        try:
            # Step 4: Always store in episodic
            self.store_conversation_turn(user_text, ame_text)

            # Step 1: Check if worth extracting
            if not self._should_extract(user_text, ame_text):
                return

            # Step 2: Extract and update Layer 1
            patch = self._extract_facts(user_text, ame_text)
            if patch:
                self.update_from_patch(patch)
                print(f"[memory] Extracted facts: {list(patch.keys())}")

            # Step 3: Extract entities/relationships for Layer 2
            self._extract_graph(user_text, ame_text)

        except Exception as e:
            print(f"[memory] Background extraction error: {e}")

    def extract_personality(self, user_text: str, ame_text: str) -> None:
        """Background personality extraction — stores into identity layer."""
        with self._counter_lock:
            self._personality_turn_counter += 1
            if self._personality_turn_counter % 3 != 0:
                return

        try:
            patch = self._extract_personality_data(user_text, ame_text)
            personality = patch.get("personality", {})
            if personality:
                with self._identity_lock:
                    existing = self._identity_data.get("personality", {})
                    for k, v in personality.items():
                        if isinstance(v, dict) and v.get("value"):
                            existing[k] = v
                    self._identity_data["personality"] = existing
                    layer1.save_identity(self._identity_data)
                print(f"[memory] Personality updated: {list(personality.keys())}")
        except Exception as e:
            print(f"[memory] Personality extraction error: {e}")

    def clear_all(self) -> None:
        """Clear all three layers."""
        try:
            # Layer 1
            with self._identity_lock:
                self._identity_data = {c: {} for c in layer1.CATEGORIES}
                layer1.save_identity(self._identity_data)

            # Layer 2
            layer2.clear()

            # Layer 3
            layer3.clear()

            print("[memory] All memory cleared.")
        except Exception as e:
            print(f"[memory] clear error: {e}")

    # ---------- Private extraction helpers using Groq via providers.py ----------

    def _should_extract(self, user_text: str, ame_text: str) -> bool:
        try:
            import asyncio
            from backend.providers import provider_manager

            prompt = f"""Does this conversation contain memorable personal facts?
Facts worth remembering: name, age, city, job, hobbies, relationships, projects, preferences, plans.

User: {user_text}
Assistant: {ame_text}

Answer only YES or NO."""

            messages = [{"role": "user", "content": prompt}]

            loop = asyncio.new_event_loop()
            try:
                resp = loop.run_until_complete(
                    provider_manager.chat(messages=messages, max_tokens=10)
                )
            finally:
                loop.close()

            text = resp["choices"][0]["message"].get("content", "").upper()
            return "YES" in text
        except Exception as e:
            print(f"[memory] should_extract error: {e}")
            return False

    def _extract_facts(self, user_text: str, ame_text: str) -> dict:
        try:
            import asyncio
            from backend.providers import provider_manager

            today = date.today().isoformat()
            cats = ", ".join(f'"{c}"' for c in layer1.CATEGORIES)
            prompt = f"""Extract memorable personal facts from this conversation.
Return ONLY valid JSON. Categories: [{cats}]
Each fact format: {{"value": "...", "updated": "{today}"}}
Omit empty categories.

User: {user_text}
Assistant: {ame_text}

JSON only, no explanation:"""

            messages = [{"role": "user", "content": prompt}]

            loop = asyncio.new_event_loop()
            try:
                resp = loop.run_until_complete(
                    provider_manager.chat(messages=messages, max_tokens=300)
                )
            finally:
                loop.close()

            raw = resp["choices"][0]["message"].get("content", "")
            if raw.startswith("```"):
                parts = raw.split("```")
                raw = parts[1] if len(parts) > 1 else raw
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw.strip())
        except Exception as e:
            print(f"[memory] extract facts error: {e}")
            return {}

    def _extract_graph(self, user_text: str, ame_text: str) -> None:
        """Extract entities and relationships from conversation and update the graph."""
        try:
            import asyncio
            from backend.providers import provider_manager

            prompt = f"""Extract entities and relationships from this conversation.
Return ONLY valid JSON in this format:
{{
  "entities": [
    {{"name": "...", "type": "person|project|service|device|place|media|order"}}
  ],
  "relationships": [
    {{"subject": "User", "predicate": "uses|watches|ordered|works_on|subscribes_to|knows|likes|...", "object": "entity name"}}
  ]
}}
Only include clear facts. If nothing extractable, return {{"entities": [], "relationships": []}}.

User: {user_text}
Assistant: {ame_text}

JSON only:"""

            messages = [{"role": "user", "content": prompt}]

            loop = asyncio.new_event_loop()
            try:
                resp = loop.run_until_complete(
                    provider_manager.chat(messages=messages, max_tokens=300)
                )
            finally:
                loop.close()

            raw = resp["choices"][0]["message"].get("content", "")
            if raw.startswith("```"):
                parts = raw.split("```")
                raw = parts[1] if len(parts) > 1 else raw
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json.loads(raw.strip())

            # Add entities
            for ent in data.get("entities", []):
                if ent.get("name") and ent.get("type"):
                    layer2.add_entity(ent["name"], ent["type"])

            # Add relationships
            for rel in data.get("relationships", []):
                if rel.get("subject") and rel.get("predicate") and rel.get("object"):
                    layer2.add_relationship(rel["subject"], rel["predicate"], rel["object"])

        except Exception as e:
            print(f"[memory] graph extraction error: {e}")

    def _extract_personality_data(self, user_text: str, ame_text: str) -> dict:
        try:
            import asyncio
            from backend.providers import provider_manager

            today = date.today().isoformat()
            prompt = f"""Based on this conversation, what can you infer about this person's personality, communication style, and preferences? Extract personality insights, not facts.

Return JSON:
{{
  "personality": {{
    "communication_style": {{"value": "...", "updated": "{today}"}},
    "humor": {{"value": "...", "updated": "{today}"}},
    "expertise_level": {{"value": "...", "updated": "{today}"}},
    "response_preference": {{"value": "...", "updated": "{today}"}},
    "work_style": {{"value": "...", "updated": "{today}"}}
  }}
}}
Only include keys where you have clear evidence from this conversation.

User: {user_text}
Assistant: {ame_text}

JSON only, no explanation:"""

            messages = [{"role": "user", "content": prompt}]

            loop = asyncio.new_event_loop()
            try:
                resp = loop.run_until_complete(
                    provider_manager.chat(messages=messages, max_tokens=300)
                )
            finally:
                loop.close()

            raw = resp["choices"][0]["message"].get("content", "")
            if raw.startswith("```"):
                parts = raw.split("```")
                raw = parts[1] if len(parts) > 1 else raw
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw.strip())
        except Exception as e:
            print(f"[memory] personality extract error: {e}")
            return {}
