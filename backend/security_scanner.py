"""
Ame First-Time Security Scanner.
Waits for High (Autopilot) permission, performs a deep system & code audit,
and proactively delivers a personalized security report to the user.
"""
import os
import time
import threading
import subprocess
from backend.live_session import _load_settings, _save_settings

class SecurityScanner:
    def __init__(self, live_session, code_watcher):
        self.live_session = live_session
        self.code_watcher = code_watcher
        self._thread = None

    def start(self):
        # If she already did this on a previous day, don't do it again
        if _load_settings().get("security_scan_completed", False):
            return
        self._thread = threading.Thread(target=self._run_scan, daemon=True, name="SecurityScanner")
        self._thread.start()

    def _run_scan(self):
        print("[SecurityScanner] Waiting for High permission to run initial deep scan...")
        
        # 1. Wait until user grants High permission
        while True:
            if self.live_session and getattr(self.live_session, 'permission_level', 'low') == "high":
                break
            time.sleep(5)

        print("[SecurityScanner] High permission detected. Starting deep machine scan...")
        
        # Give the user a moment (60 seconds) so she doesn't interrupt immediately after they click the setting
        time.sleep(60)

        sys_info = []
        
        # 2. Gather Windows Security Info (Firewall & Defender)
        try:
            # Firewall
            fw = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-NetFirewallProfile | Select-Object Name,Enabled | ConvertTo-Json"],
                capture_output=True, text=True, timeout=10
            )
            if fw.stdout:
                sys_info.append(f"Firewall Profiles:\n{fw.stdout.strip()}")
            
            # Antivirus / Defender
            av = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-MpComputerStatus | Select-Object RealTimeProtectionEnabled,AntispywareEnabled | ConvertTo-Json"],
                capture_output=True, text=True, timeout=10
            )
            if av.stdout:
                sys_info.append(f"Windows Defender Status:\n{av.stdout.strip()}")
        except Exception as e:
            print(f"[SecurityScanner] System scan error: {e}")

        # 3. Gather Code Security Info (Exposed .env, keys, etc.)
        code_info = []
        try:
            if self.code_watcher:
                projects = self.code_watcher.get_all_projects()
                for p in projects:
                    files = p.get("files", {})
                    for fname, fpath in files.items():
                        fname_lower = fname.lower()
                        if fname_lower in {".env", "id_rsa", "credentials.json", "secret.key"}:
                            code_info.append(f"Found potentially sensitive file in project '{p['name']}': {fname}")
        except Exception as e:
            print(f"[SecurityScanner] Code scan error: {e}")

        context_data = "\n\n".join(sys_info + code_info)
        if not context_data.strip():
            context_data = "Standard Windows environment detected. No glaring immediate risks found."

        # 4. Have the LLM analyze and generate a natural, proactive message
        prompt = f"""You are AME, a personal AI assistant and cybersecurity guardian.
You just completed your first deep security scan of the user's PC and code projects after they granted you High (Autopilot) permissions.

Here is the raw data from your scan:
{context_data}

If you found any potential risks (like disabled firewalls, disabled antivirus, or exposed .env/credential files in their code projects), you need to proactively interrupt the user and warn them.
If everything looks safe, give a brief, cool confirmation that their system is secure and you're standing guard.

Write EXACTLY what you will say out loud. 
Make it sound natural, confident, and conversational — like a smart friend or a guardian, NOT a robotic security report.
Do not use markdown. Do not list items bullet by bullet. Just say it naturally as one or two sentences.
If there are issues, end by asking if they want you to fix them or explain them.

Response:"""

        try:
            from backend.gemini_client import call_task_model, extract_text
            api_key = os.getenv("GOOGLE_AI_STUDIO_KEY") or os.getenv("GEMINI_API_KEY")
            if api_key:
                resp = call_task_model([{"parts": [{"text": prompt}]}], api_key=api_key, timeout=20)
                message = extract_text(resp).strip()
                
                if message and self.live_session:
                    print(f"[SecurityScanner] Delivering report: {message}")
                    
                    # Inject into context so she remembers she said it
                    context_reason = f"You just completed an initial deep security scan of the PC and delivered this report based on this data: {context_data}"
                    self.live_session.speak_proactive(message, context_reason)
                    
                    # Mark as completed so it never runs again
                    _save_settings({"security_scan_completed": True})
        except Exception as e:
            print(f"[SecurityScanner] Scan evaluation failed: {e}")