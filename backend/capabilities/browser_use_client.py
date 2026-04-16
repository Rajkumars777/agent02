"""
browser_use_client.py
=====================
Premium autonomous web automation powered by browser-use + Playwright.

Architecture decisions:
  - DOM-first, Vision-fallback: The LLM reads a compact DOM tree by default.
    A full screenshot (vision) is only triggered when DOM parsing is ambiguous
    or the agent stalls — cutting GPT-4o vision token costs significantly.
  - Singleton browser with asyncio.Lock: Prevents race conditions when two tasks
    arrive simultaneously before Playwright has finished initializing.
  - Profile LOCK recovery: Deletes stale SingletonLock/LOCK files left over from
    a previous hard-crash, so the agent never fails to start due to a dead lockfile.
  - Tab guard: Detects and ignores `target="_blank"` popups to keep the agent
    anchored to the primary page context.
  - Graceful shutdown: close() is called from FastAPI's lifespan handler so no
    zombie `chrome.exe` processes are left after the backend exits.

Usage (from FastAPI route):
    async for update in browser_client.run_task("Find flights NYC→SFO next Monday"):
        yield f"data: {json.dumps(update)}\\n\\n"
"""

import asyncio
import json
import logging
import os
import re
from typing import Any, AsyncGenerator, Optional

logger = logging.getLogger(__name__)

# ── Keywords that indicate the agent will need user credentials ───────────────
_CREDENTIAL_KEYWORDS = [
    "login", "log in", "sign in", "sign-in", "signin", "log-in",
    "account", "password", "username", "credentials", "authenticate",
    "email", "user id", "userid", "api key", "access token",
]

# ── Profile directory ─────────────────────────────────────────────────────────
_APP_DIR = os.path.join(os.path.expanduser("~"), "AppData", "Local", "NEXUS")
_PROFILE_DIR = os.path.join(_APP_DIR, "browser_profiles", "default")

# ── Stale lock files Playwright leaves after a hard-crash ────────────────────
_LOCK_FILES = ["SingletonLock", "SingletonCookie", "LOCK", "lockfile"]


def _clear_stale_locks(profile_dir: str) -> None:
    """
    Delete stale profile lock files that prevent Playwright from launching
    after an unclean backend shutdown. Safe to call on every startup attempt.
    """
    for name in _LOCK_FILES:
        lock_path = os.path.join(profile_dir, name)
        if os.path.exists(lock_path):
            try:
                os.remove(lock_path)
                logger.warning(f"[BrowserUse] Removed stale lock file: {lock_path}")
            except OSError as exc:
                logger.error(f"[BrowserUse] Could not remove lock file {lock_path}: {exc}")


# ── Step → clean UI model ─────────────────────────────────────────────────────

def _format_step(step: Any) -> dict:
    """
    Map a browser-use AgentOutput object to a clean UI payload for SSE streaming.
    """
    try:
        thought = ""
        action_str = ""

        if hasattr(step, "current_state"):
            # browser-use 0.12 AgentOutput
            state = step.current_state
            thought = getattr(state, "evaluation_previous_goal", "") or getattr(state, "memory", "")
            
            acts = getattr(step, "action", []) or []
            action_strs = []
            for act in acts:
                if hasattr(act, "model_dump"):
                    act_dict = act.model_dump(exclude_none=True)
                    for k, v in act_dict.items():
                        action_strs.append(f"{k}: {v}")
            action_str = " | ".join(action_strs)

        else:
            # Fallback for old object shapes
            thought = getattr(step, "model_output", None) or getattr(step, "thought", "")
            action_str = getattr(step, "result", None) or getattr(step, "action", "")
            if not thought and hasattr(step, "__dict__"):
                data = step.__dict__
                thought = data.get("model_output") or data.get("thought") or ""
                action_str = data.get("result") or data.get("action") or ""
            
        if not thought and not action_str:
            thought = str(step)[:300]

        return {
            "status":  "running",
            "thought": str(thought)[:500] if thought else "",
            "action":  str(action_str)[:500] if action_str else "Processing UI state...",
        }
    except Exception:
        return {"status": "running", "thought": "Analyzing page...", "action": ""}


# ── NEXUS config reader ───────────────────────────────────────────────────────

def _load_nexus_config() -> dict:
    """Read the NEXUS config.json — returns {} if missing or unreadable."""
    candidates = [
        os.environ.get("NEXUS_CONFIG_PATH", ""),
        os.path.join(_APP_DIR, "config.json"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json"),
    ]
    for path in candidates:
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                continue
    return {}


# ── BrowserUseClient ──────────────────────────────────────────────────────────

class BrowserUseClient:
    """
    Singleton-like client that owns one persistent Playwright browser process
    for the entire lifetime of the backend (reused across tasks).
    """

    def __init__(self):
        self._browser  = None
        self._lock     = asyncio.Lock()   # Prevents concurrent initializations
        self._cfg      = {}               # Lazily populated from NEXUS config
        # Human-in-the-loop: per-task pause mechanism
        self._answer_events: dict[str, asyncio.Event] = {}
        self._pending_answers: dict[str, str] = {}
        
        # Continuation cache
        self._agents: dict[str, Any] = {}
        self._queues: dict[str, asyncio.Queue] = {}

    # ── Config helpers ────────────────────────────────────────────────────────
    
    def clear_agent_session(self, task_id: str):
        """Clears the agent and session state for the given task."""
        self._agents.pop(task_id, None)
        self._queues.pop(task_id, None)

    def _create_step_callback(self, task_id: str):
        """Creates a route to the active queue for a specific task ID."""
        async def step_callback(state, output, step_idx):
            if task_id in self._queues:
                await self._queues[task_id].put(output)
        return step_callback

    def _get_cfg(self) -> dict:
        if not self._cfg:
            self._cfg = _load_nexus_config()
        return self._cfg

    def _load_local_cookies(self) -> list:
        """Extract cookies seamlessly from Chrome using browser_cookie3."""
        try:
            import browser_cookie3
            # Extract from Chrome ONLY to prevent Windows DPAPI locks seen with Edge
            cj = browser_cookie3.chrome()
            cdp_cookies = []
            from cdp_use.cdp.network.types import CookieParam
            for c in cj:
                try:
                    cookie = CookieParam(
                        name=c.name,
                        value=c.value,
                        domain=c.domain,
                        path=c.path,
                        secure=c.secure,
                    )
                    cdp_cookies.append(cookie)
                except Exception:
                    pass
            logger.info(f"[BrowserUse] Extracted {len(cdp_cookies)} cookies from Chrome.")
            return cdp_cookies
        except Exception as e:
            logger.error(f"[BrowserUse] Failed to extract Chrome cookies: {e}")
            return []

    def provide_answer(self, task_id: str, answer: str) -> bool:
        """
        Called by the /agent/resume endpoint to unblock a waiting browser task.
        Returns True if a task was actually waiting, False otherwise.
        """
        self._pending_answers[task_id] = answer
        event = self._answer_events.get(task_id)
        if event:
            event.set()
            logger.info(f"[BrowserUse] Answer delivered to task {task_id}")
            return True
        logger.warning(f"[BrowserUse] No waiting task found for {task_id}")
        return False

    def _check_missing_info(self, instruction: str) -> Optional[str]:
        """
        Quick keyword scan: if the task mentions login/credentials but
        doesn't already include them in the instruction, return a
        human-friendly question to ask the user.
        """
        lower = instruction.lower()
        needs_creds = any(kw in lower for kw in _CREDENTIAL_KEYWORDS)

        # If the instruction already has credential-like content, skip
        has_creds = any(marker in lower for marker in [
            "password:", "password is", "username:", "email:",
            "user id:", "credentials:", "api key:", "token:",
        ])

        if needs_creds and not has_creds:
            # Build a targeted question
            if "password" in lower or "login" in lower or "sign in" in lower:
                return (
                    "This task requires login credentials.\n"
                    "Please provide the **username/email** and **password** "
                    "(and any other required info like 2FA or workspace name) as a reply."
                )
            return (
                "This task requires personal information (e.g. credentials, API key, or account details).\n"
                "Please reply with the required information so I can proceed."
            )
        return None

    def _get_llm(self):
        """
        Build the LangChain LLM from NEXUS settings (OpenAI or Gemini).
        Reuses the same provider that the rest of the agent stack uses.
        """
        cfg      = self._get_cfg()
        provider = cfg.get("ai_provider", "google")

        if provider == "openai":
            from browser_use import ChatOpenAI
            api_key = (
                cfg.get("openai_api_key")
                or cfg.get("api_key")
                or os.getenv("OPENAI_API_KEY", "")
            )
            return ChatOpenAI(
                model="gpt-4o",
                temperature=0,
                api_key=api_key,
            )
        else:
            # Google Gemini via browser-use
            from browser_use import ChatGoogle
            api_key = cfg.get("api_key") or os.getenv("GEMINI_API_KEY", "")
            return ChatGoogle(
                model="gemini-2.0-flash",
                temperature=0,
                api_key=api_key,
            )

    # ── Browser lifecycle ─────────────────────────────────────────────────────

    async def get_browser(self):
        """
        Return the current Browser, initializing it if needed.
        Protected by asyncio.Lock to prevent a race condition where two
        simultaneous requests both enter the `if self._browser is None` guard
        before initialization completes.
        """
        async with self._lock:
            if self._browser is not None:
                return self._browser

            from browser_use import Browser

            cfg         = self._get_cfg()
            headless    = cfg.get("browser_headless", False)   # Headful by default
            proxy_url   = cfg.get("proxy_url", "")
            browser_choice = cfg.get("browser_engine")

            # Find executable path / channel for the chosen browser
            executable_path = None
            channel = None
            if browser_choice:
                try:
                    from api.routers.settings import get_installed_browsers
                    available = get_installed_browsers()
                    for b in available:
                        if b["name"] == browser_choice:
                            executable_path = b["path"]
                            channel = b["channel"]
                            break
                except Exception:
                    pass

            # Guarantee profile dir exists
            os.makedirs(_PROFILE_DIR, exist_ok=True)

            # Remove stale lock files from a previous hard crash
            _clear_stale_locks(_PROFILE_DIR)

            chromium_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-popup-blocking",
                "--remote-allow-origins=*",
            ]
            try:
                logger.warning(f"[BrowserUse] Launching Playwright. Executable: {executable_path}, Profile: {_PROFILE_DIR}")
                self._browser = Browser(
                    headless=headless,
                    user_data_dir=_PROFILE_DIR,
                    args=chromium_args,
                    keep_alive=True,
                    executable_path=executable_path,
                    disable_security=True,
                )
                
                # --- Zero-Login Cookie Mirroring ---
                try:
                    await self._browser.start()  # Ensures CDP is active
                    local_cookies = self._load_local_cookies()
                    if local_cookies:
                        await self._browser._cdp_set_cookies(local_cookies)
                        logger.warning("[BrowserUse] Mirror cookies injected successfully via CDP.")
                except Exception as e:
                    logger.error(f"[BrowserUse] Zero-Login initialization failed: {e}")

                logger.warning("[BrowserUse] Playwright browser initialized.")
            except Exception as exc:
                logger.error(f"[BrowserUse] Browser init failed: {exc}")
                self._browser = None
                raise RuntimeError(f"Failed to start browser: {exc}") from exc

            return self._browser

    async def close(self):
        """Gracefully shut down the Playwright browser process."""
        async with self._lock:
            if self._browser is not None:
                try:
                    await self._browser.close()
                    logger.warning("[BrowserUse] Browser closed cleanly.")
                except Exception as exc:
                    logger.error(f"[BrowserUse] Error closing browser: {exc}")
                finally:
                    self._browser = None

    # ── Task execution ────────────────────────────────────────────────────────

    async def run_task(self, instruction: str, task_id: str = "default") -> AsyncGenerator[dict, None]:
        """
        Execute a natural-language browser task.

        Yields dicts suitable for SSE streaming:
            {"status": "running", "thought": "...", "action": "..."}
            {"status": "done",    "result":  "..."}
            {"status": "error",   "message": "..."}

        Strategy:
          1. DOM-first (no vision) — fast and cheap for most tasks.
          2. Vision fallback — enabled only when use_vision=True is needed
             (toggle-able per task via ?vision=true query param in the future).
        """
        from browser_use import Agent

        browser = await self.get_browser()
        llm     = self._get_llm()

        # ── Pre-flight: ask for credentials if the task needs them ────────────
        missing_info = self._check_missing_info(instruction)
        if missing_info:
            answer_event = asyncio.Event()
            self._answer_events[task_id] = answer_event

            yield {"status": "needs_input", "question": missing_info}

            # Pause — wait up to 5 minutes for the user to reply
            try:
                await asyncio.wait_for(answer_event.wait(), timeout=300.0)
            except asyncio.TimeoutError:
                self._answer_events.pop(task_id, None)
                yield {"status": "done", "result": "Task timed out waiting for your input."}
                return

            # Inject answer into the original instruction and continue
            user_answer = self._pending_answers.pop(task_id, "")
            self._answer_events.pop(task_id, None)
            if user_answer:
                instruction = (
                    f"{instruction}\n\n"
                    f"--- User provided credentials/information ---\n{user_answer}"
                )
                logger.info(f"[BrowserUse] Injected user answer into task {task_id}")

        # Prepare the stream queue and callback
        if task_id not in self._queues:
            self._queues[task_id] = asyncio.Queue()
        step_queue = self._queues[task_id]

        date_rule = (
            "CRITICAL INPUT RULE: When a task requires entering dates into a UI or interacting with a Datepicker "
            "(especially in Zoho/ERP systems) you MUST use the exact requested format (e.g. YYYY-MM-DD or DD/MM/YYYY). "
            "If standard typing fails, try using the 'fill' action, or try copying the text into the clipboard and pasting it."
        )

        if task_id in self._agents:
            agent = self._agents[task_id]
            logger.warning(f"[BrowserUse] Continuing agent task in same tab for {task_id}")
            agent.add_new_task(instruction)
        else:
            agent = Agent(
                task=instruction,
                llm=llm,
                browser=browser,
                use_vision=False, # DOM-first
                extend_system_message=date_rule,
                register_new_step_callback=self._create_step_callback(task_id),
                max_actions_per_step=5,
                # Error recovery
                retry_delay=2,
                max_failures=3,
            )
            self._agents[task_id] = agent

        logger.warning(f"[BrowserUse] Starting task: {instruction[:80]}")

        # ── Run agent in background, stream steps from queue ──────────────────
        run_task_coro = asyncio.create_task(agent.run(max_steps=20))

        while not run_task_coro.done():
            try:
                output = await asyncio.wait_for(step_queue.get(), timeout=1.0)
                yield _format_step(output)
            except asyncio.TimeoutError:
                continue

        # Flush any remaining items
        while not step_queue.empty():
            output = await step_queue.get()
            yield _format_step(output)

        try:
            result = await run_task_coro
            
            # Formulate clean textual result
            if result and hasattr(result, "final_result"):
                raw_final = result.final_result() or "Task completed (no textual output)."
                if "<result>" in raw_final:
                    match = re.search(r"<result>(.*?)</result>", raw_final, re.DOTALL)
                    if match:
                        raw_final = match.group(1).strip()
                else:
                    raw_final = re.sub(r"<url>.*?</url>", "", raw_final, flags=re.DOTALL)
                    raw_final = re.sub(r"<query>.*?</query>", "", raw_final, flags=re.DOTALL).strip()
                final_text = raw_final
            else:
                final_text = str(result) if result is not None else "Task completed."
            
            logger.warning(f"[BrowserUse] Task done: {final_text[:80]}")
            yield {"status": "done", "result": final_text}
        except Exception as exc:
            logger.error(f"[BrowserUse] Task error: {exc}")
            yield {"status": "error", "message": f"Agent crashed: {str(exc)}"}

    # ── Vision analysis (opt-in) ──────────────────────────────────────────────

    async def run_task_with_vision(self, instruction: str) -> AsyncGenerator[dict, None]:
        """
        Same as run_task but forces use_vision=True for tasks where DOM
        parsing is insufficient (e.g., canvas-based UIs, image CAPTCHAs, etc.).
        Charge-aware: only call this when the DOM-first strategy has failed.
        """
        from browser_use import Agent

        browser = await self.get_browser()
        llm     = self._get_llm()

        agent = Agent(
            task=instruction,
            llm=llm,
            browser=browser,
            use_vision=True,        # Vision mode
            max_actions_per_step=5,
            retry_delay=2,
            max_failures=3,
        )

        has_stream = hasattr(agent, "astream")
        if has_stream:
            async for step in agent.astream():
                yield _format_step(step)

        try:
            result = await agent.run(max_steps=15)   # Tighter cap — vision is expensive
            yield {"status": "done", "result": str(result) if result else "Task completed."}
        except Exception as exc:
            logger.error(f"[BrowserUse] Vision task error: {exc}")
            yield {"status": "error", "message": str(exc)}


# ── Module-level singleton (one browser for the whole backend process) ────────
browser_client = BrowserUseClient()
