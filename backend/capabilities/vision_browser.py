"""
vision_browser.py
=================
Visual page analysis: take a Kapture screenshot → send to Gemini Vision →
return element descriptions, selector hints, and disruption detection.

Used by the browser REST endpoints to give the agent true visual understanding
of what's on screen, not just raw DOM text.
"""

import asyncio
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Module-level cache: built once on first use, reused for all subsequent calls.
_vision_client = None
_vision_model: Optional[str] = None
_vision_initialized = False


def _get_vision_client():
    """
    Build (or return the cached) OpenAI-compatible vision client.
    Reads the provider (openai/google) and API key from NEXUS config.json.
    Result is cached at module level — disk I/O only happens once per process.
    Returns: (client, default_model)
    """
    global _vision_client, _vision_model, _vision_initialized
    if _vision_initialized:
        return _vision_client, _vision_model

    _vision_initialized = True  # Mark even on failure to avoid repeated attempts

    try:
        from openai import OpenAI

        # Try NEXUS app config first
        config_candidates = [
            os.environ.get("NEXUS_CONFIG_PATH", ""),
            os.path.join(os.path.expanduser("~"), "AppData", "Local", "NEXUS", "config.json"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json"),
        ]
        api_key = ""
        provider = "google"

        for path in config_candidates:
            if path and os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                    provider = cfg.get("ai_provider", "google")
                    if provider == "openai":
                        api_key = cfg.get("openai_api_key") or cfg.get("api_key", "")
                    else:
                        api_key = cfg.get("api_key", "")

                    # Fallback: check auth profiles in openclaw config if no key found
                    if not api_key:
                        profiles = cfg.get("auth", {}).get("profiles", {})
                        if provider == "openai":
                            api_key = profiles.get("openai:default", {}).get("apiKey", "")
                        else:
                            api_key = profiles.get("google:default", {}).get("apiKey", "")
                    if api_key:
                        break
                except Exception:
                    continue

        if not api_key:
            # Env var fallbacks
            api_key = os.getenv("OPENAI_API_KEY") if provider == "openai" else os.getenv("GEMINI_API_KEY", "")

        if not api_key:
            logger.warning(f"[Vision] No API key found for provider {provider} — vision analysis unavailable")
            _vision_client, _vision_model = None, None
            return None, None

        if provider == "openai":
            _vision_client = OpenAI(api_key=api_key)
            _vision_model = "gpt-4o-mini"
        else:
            _vision_client = OpenAI(
                api_key=api_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            )
            _vision_model = "gemini-2.0-flash"

        logger.info(f"[Vision] Client initialized (provider={provider}, model={_vision_model})")
        return _vision_client, _vision_model

    except Exception as e:
        logger.error(f"[Vision] Failed to build Vision client: {e}")
        _vision_client, _vision_model = None, None
        return None, None


async def analyze_page(
    question: str,
    tab_id: Optional[int] = None,
    model: Optional[str] = None,
) -> dict:
    """
    Screenshot the current browser page, send it to Gemini Vision,
    and get a structured answer about what's visible.

    Args:
        question: What to ask about the page. Examples:
                  "What is the CSS selector for the login button?"
                  "Is there a CAPTCHA or login wall? What does it need?"
                  "List all form fields visible and their selectors."
        tab_id:   Specific Chrome tab ID (uses active tab if None).
        model:    Gemini model to use (gemini-2.0-flash is fast + vision-capable).

    Returns:
        {"success": True, "analysis": <str>, "screenshot_b64": <str>, "mime_type": <str>}
      | {"success": False, "error": <str>}
    """
    from capabilities.kapture_client import screenshot as kapture_screenshot

    # 1. Capture screenshot via Kapture
    ss = await kapture_screenshot(tab_id)
    if not ss.get("success"):
        return {"success": False, "error": f"Screenshot failed: {ss.get('error', 'unknown')}"}

    image_b64 = ss.get("result", "")
    mime_type = ss.get("mimeType", "image/webp")

    if not image_b64:
        return {"success": False, "error": "Screenshot returned empty image"}

    # 2. Send to Vision API
    client, default_model = _get_vision_client()
    if not client:
        return {"success": False, "error": "AI API key not configured for vision analysis"}
        
    use_model = model or default_model

    system_prompt = (
        "You are a precise web automation analyst. "
        "You inspect browser screenshots and provide actionable guidance for web automation agents. "
        "Be specific: provide exact CSS selectors, element text, IDs, or class names when possible. "
        "If you see a disruption (login wall, CAPTCHA, password prompt, 2FA, cookie consent, popup), "
        "explicitly call it out and describe exactly what user input is needed to proceed."
    )

    user_prompt = (
        f"{question}\n\n"
        "Please respond with:\n"
        "1. **Direct Answer** — precise response to the question\n"
        "2. **Selectors** — CSS selectors or XPath for relevant elements (if applicable)\n"
        "3. **Page State** — brief description of the current page state\n"
        "4. **Action Needed** — if user input is required (password, OTP, CAPTCHA solve), "
        "state exactly what is needed so the automation agent can ask the user"
    )

    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=use_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_b64}",
                            },
                        },
                        {"type": "text", "text": user_prompt},
                    ],
                },
            ],
            max_tokens=1024,
        )

        analysis = response.choices[0].message.content
        logger.info(f"[Vision] Analysis complete ({len(analysis)} chars)")

        return {
            "success": True,
            "analysis": analysis,
            "screenshot_b64": image_b64,
            "mime_type": mime_type,
        }

    except Exception as e:
        logger.error(f"[Vision] Vision API error: {e}")
        return {"success": False, "error": f"Vision analysis failed: {e}"}


async def detect_disruption(tab_id: Optional[int] = None) -> dict:
    """
    Check if the current page has a disruption that needs user input:
    login walls, CAPTCHAs, password prompts, 2FA, cookie banners, etc.

    Returns:
        {
          "disruption": True/False,
          "type": "login"|"password"|"otp"|"captcha"|"cookie_consent"|"popup"|None,
          "message": "<what to ask the user>",
          "analysis": "<full vision response>"
        }
    """
    result = await analyze_page(
        "Is there any disruption on this page that requires user input before automation can continue? "
        "Look for: login forms, password prompts, OTP/2FA requests, CAPTCHAs, cookie consent banners, "
        "popups, age verification, or any blocking overlay. "
        "If yes, classify the type and state exactly what the user must provide.",
        tab_id=tab_id,
    )

    if not result.get("success"):
        return {"disruption": False, "type": None, "message": "", "analysis": result.get("error", "")}

    analysis = result.get("analysis", "").lower()

    disruption_keywords = {
        "captcha": ["captcha", "recaptcha", "i am not a robot", "verify you are human"],
        "login": ["sign in", "log in", "login form", "username", "email address", "create account"],
        "password": ["password", "enter your password", "confirm password"],
        "otp": ["otp", "one-time", "verification code", "sms code", "6-digit", "authenticator"],
        "cookie_consent": ["accept cookies", "cookie policy", "gdpr", "consent"],
        "popup": ["popup", "modal", "overlay", "dialog", "dismiss", "close this"],
    }

    detected_type = None
    for dtype, keywords in disruption_keywords.items():
        if any(kw in analysis for kw in keywords):
            detected_type = dtype
            break

    is_disruption = detected_type is not None

    message = ""
    if detected_type == "captcha":
        message = "⚠️ A CAPTCHA is blocking the page. I need you to solve it manually in Chrome, then let me know to continue."
    elif detected_type == "login":
        message = "🔐 A login form is blocking automation. Please provide your username/email and password."
    elif detected_type == "password":
        message = "🔑 A password prompt appeared. Please provide the password."
    elif detected_type == "otp":
        message = "📱 A one-time password (OTP) or 2FA code is required. Please check your phone/email and provide the code."
    elif detected_type == "cookie_consent":
        message = "🍪 A cookie consent banner appeared. I'll try to accept it automatically."
    elif detected_type == "popup":
        message = "💬 A popup or dialog is blocking the page. I'll try to close it automatically."

    return {
        "disruption": is_disruption,
        "type": detected_type,
        "message": message,
        "analysis": result.get("analysis", ""),
    }
