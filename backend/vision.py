"""
Vision tools for Ame.
analyze_screen — captures desktop, sends to Claude → OpenAI → Gemini
analyze_webcam — captures webcam frame, sends to Gemini Vision
"""

import sys, os
os.environ.setdefault('PYTHONUTF8', '1')
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'): sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import time
import threading

# Shared screenshot state — screen_watcher populates these for its own use.
_vision_state_lock = threading.Lock()
_last_screenshot_bytes = None
_last_screenshot_time = 0


def _call_gemini_vision(image_bytes: bytes, prompt: str, mime_type: str = "image/jpeg") -> dict:
    """Send an image to Gemini Vision and return the response."""
    import base64
    from backend.gemini_client import call_task_model, extract_text, AllModelsExhaustedError

    api_key = os.getenv("GOOGLE_AI_STUDIO_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[Vision] No API key configured")
        return {"success": False, "message": "No Gemini API key configured."}

    contents = [
        {
            "parts": [
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": base64.b64encode(image_bytes).decode(),
                    }
                },
                {"text": prompt},
            ]
        }
    ]

    print(f"[Vision] Sending to Gemini... ({len(image_bytes)} bytes)")
    try:
        resp_json = call_task_model(contents, api_key=api_key, timeout=12)
        print("[Vision] Raw response received")
        text = extract_text(resp_json)
        print(f"[Vision] Result: {text[:100]}")
        return {"success": True, "description": text}
    except AllModelsExhaustedError as e:
        print(f"[Vision] Exception: AllModelsExhaustedError: {e}")
        return {"success": False, "message": "I'm a bit overwhelmed right now, give me a second."}
    except Exception as e:
        print(f"[Vision] Exception: {type(e).__name__}: {e}")
        return {"success": False, "message": f"Vision failed: {type(e).__name__}: {e}"}


def _compress_image(pil_img, max_width: int = 1280, max_height: int = 720, quality: int = 70) -> bytes:
    """Resize and JPEG-compress a PIL image."""
    import io
    from PIL import Image

    img = pil_img.copy()
    img.thumbnail((max_width, max_height), Image.LANCZOS)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def _call_claude_vision(image_bytes: bytes, prompt: str) -> dict:
    """Send an image to Claude Vision and return the response."""
    import httpx
    import base64

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {"success": False, "message": "No Anthropic key"}

    b64 = base64.b64encode(image_bytes).decode()

    try:
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 300,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": b64
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            },
            timeout=10
        )
        if resp.status_code == 200:
            content = resp.json().get("content", [])
            if content:
                text = content[0].get("text", "").strip()
                print(f"[Vision] Claude result: {text[:80]}")
                return {"success": True, "description": text}
        print(f"[Vision] Claude failed: {resp.status_code} {resp.text[:100]}")
        return {"success": False, "message": f"Claude {resp.status_code}"}
    except Exception as e:
        print(f"[Vision] Claude error: {e}")
        return {"success": False, "message": str(e)}


def analyze_screen(prompt: str) -> dict:
    """Capture the full screen and analyze it with vision (Claude → OpenAI → Gemini)."""
    print("[Vision] Taking fresh screenshot...")

    # Capture screenshot — always fresh, no cache
    try:
        import mss
        from PIL import Image

        with mss.mss() as sct:
            if len(sct.monitors) > 1:
                monitor = sct.monitors[1]
            else:
                monitor = sct.monitors[0]
            shot = sct.grab(monitor)
            pil_img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

        print(f"[Vision] Screenshot captured: {pil_img.size}")
        image_bytes = _compress_image(pil_img)

    except ImportError as e:
        return {"success": False, "message": f"Missing dependency: {e}. Install: pip install mss pillow"}
    except Exception as e:
        return {"success": False, "message": f"Screenshot failed: {e}"}

    # Try Claude first
    claude_result = _call_claude_vision(image_bytes, prompt)
    if claude_result.get("success"):
        return claude_result

    # Try OpenAI second
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        import httpx, base64
        try:
            b64 = base64.b64encode(image_bytes).decode()
            resp = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": [
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/jpeg;base64,{b64}",
                            "detail": "low"
                        }},
                        {"type": "text", "text": prompt}
                    ]}],
                    "max_tokens": 300,
                    "temperature": 0.1
                },
                timeout=10
            )
            if resp.status_code == 200:
                choices = resp.json().get("choices", [])
                if choices:
                    text = choices[0].get("message", {}).get("content", "").strip()
                    print(f"[Vision] OpenAI described: {text[:100]}")
                    return {"success": True, "description": text}
            if resp.status_code == 429:
                print(f"[Vision] OpenAI 429 body: {resp.text[:200]}")
            else:
                print(f"[Vision] OpenAI failed: {resp.status_code}")
        except Exception as e:
            print(f"[Vision] OpenAI error: {e}")

    # Fall back to Gemini if OpenAI fails
    result = _call_gemini_vision(image_bytes, prompt)
    return result


def analyze_webcam(prompt: str) -> dict:
    """Capture a frame from the webcam and analyze it with Gemini Vision."""
    try:
        import cv2
        from PIL import Image

        cap = None
        for idx in range(6):
            test = cv2.VideoCapture(idx)
            if test.isOpened():
                ret, frame = test.read()
                if ret and frame is not None:
                    cap = test
                    break
                test.release()

        if cap is None:
            return {"success": False, "message": "No webcam found. Tried camera indices 0-5."}

        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            return {"success": False, "message": "Webcam capture failed — no frame received."}

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        image_bytes = _compress_image(pil_img)

        return _call_gemini_vision(image_bytes, prompt)

    except ImportError as e:
        return {"success": False, "message": f"Missing dependency: {e}. Install: pip install opencv-python pillow"}
    except Exception as e:
        return {"success": False, "message": f"Webcam analysis failed: {e}"}
