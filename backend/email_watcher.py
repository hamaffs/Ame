"""
Ame VIP Email Watcher
Periodically checks for urgent emails and proactively interrupts the user.
"""

import time
import threading
import os
import json

class EmailWatcher:
    def __init__(self, live_session):
        self.live_session = live_session
        self._running = False
        self._seen_file = os.path.join(os.path.expanduser("~"), ".ame", "seen_emails.json")
        self._seen_ids = set()
        self._load_seen()

    def _load_seen(self):
        try:
            if os.path.exists(self._seen_file):
                with open(self._seen_file, "r") as f:
                    self._seen_ids = set(json.load(f))
        except Exception:
            pass
            
    def _save_seen(self):
        try:
            os.makedirs(os.path.dirname(self._seen_file), exist_ok=True)
            with open(self._seen_file, "w") as f:
                json.dump(list(self._seen_ids), f)
        except Exception:
            pass

    def start(self):
        self._running = True
        threading.Thread(target=self._run, daemon=True, name="EmailWatcher").start()
        print("[EmailWatcher] Started VIP inbox monitoring")

    def stop(self):
        self._running = False

    def _run(self):
        # Wait just 5s before first check
        time.sleep(5)
            
        vip_keywords = ["urgent", "important", "server down", "asap", "crash", "boss"]
        
        while self._running:
            # Don't trigger browser popup in the background if they haven't logged in yet
            token_path = os.path.join(os.path.expanduser("~"), ".ame", 'token.json')
            if not os.path.exists(token_path):
                time.sleep(5)
                continue
                
            try:
                from backend.email_agent import read_recent_emails
                result = read_recent_emails(limit=10, unread_only=True)
                if result.get("success"):
                    for msg in result["emails"]:
                        if msg["id"] not in self._seen_ids:
                            self._seen_ids.add(msg["id"])
                            subject = msg.get("subject", "").lower()
                            sender = msg.get("sender", "").lower()
                            
                            if any(kw in subject or kw in sender for kw in vip_keywords):
                                print(f"[EmailWatcher] VIP EMAIL DETECTED: {subject}")
                                try:
                                    from backend.music_agent import pause_spotify
                                    pause_spotify()
                                except Exception:
                                    pass
                                if hasattr(self.live_session, "speak_proactive"):
                                    self.live_session.speak_proactive(f"Hey, sorry to interrupt. You just got an urgent email from {msg.get('sender', 'someone')} about '{msg.get('subject', '')}'. Want me to read it to you?")
                                self._save_seen()
            except Exception as e:
                print(f"[EmailWatcher] Error checking emails: {e}")
            
            time.sleep(5)