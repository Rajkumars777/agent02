# Agent02 ── Autonomous OpenClaw Gateway Interface

Agent02 is a self-hosted, triple-stack Desktop AI Assistant powered purely by the **[OpenClaw Gateway](https://openclaw.ai)**. It bypasses restrictive cloud sandboxes to provide true, unfettered autonomous desktop integration. It natively commands your local system—executing terminal commands, generating complex Microsoft Office files, searching the web, and organizing directories purely through natural language.

<br/>

## 🧊 Triple-Stack Architecture
The Agent02 system simultaneously coordinates three highly distinct functional engines on your local machine with zero human intervention.

1. **Next.js Real-time Dashboard (Port 3000):** A deeply modern UI featuring streaming Server-Sent Events (SSE), dynamic thought-visualization, and dark-glass aesthetics.
2. **FastAPI Python Orchestrator (Port 8000):** A highly concurrent ASGI backend that bridges communication between the UI and OpenClaw. 
3. **OpenClaw Executable Engine (Port 18789):** The true brain of the system. This lightweight local gateway hooks directly into your filesystem, executing local processes via natural language securely through a localized API model.

![Architecture Flow](https://via.placeholder.com/800x200.png?text=Next.js+UI+%E2%86%92+FastAPI+Orchestrator+%E2%86%92+OpenClaw+Gateway)

---

## ⚡ Zero-Touch Deployment

Agent02 is designed to be universally frictionless. We have engineered a single portable executable that automatically sets up the entire application perfectly.

### Installation via `Agent02_Setup.exe`
1. Move **`Agent02_Setup.exe`** to any Windows machine.
2. **Double-click it.**
3. The setup script will immediately:
   - Silently download and install identical **Python** and **Node.js** versions globally to perfectly align the runtime.
   - Inject the official project codebase automatically.
   - Programmatically inject the core configuration strings into the global authentication vault.
   - Spin up standard native compilers (`pip` & `npm`) in the background.
4. **Launch Agent02.** You will see a shortcut directly on your desktop.

### Standard Launching
Open **`Agent.exe`** from your desktop or root folder. The bootstrapper instantly spawns:
- The OpenClaw Gateway Daemon
- Uvicorn Python Servers 
- The Next.js UI Stream  

All in a single, perfectly timed terminal boot sequence. Open your browser to `http://localhost:3000` to interact with your Agent.

---

## ⚙️ How it Works under the Hood

Agent02 does not rely on static hardcoded capabilities like `create_word_document.py` or `search_web.js`. It delegates **100%** of logical planning and execution strictly to the OpenClaw Gateway via `asyncio`.

```yaml
# Execution Pipeline
User Prompt → Next.js API (/api/chat)
            → FastAPI Engine (main.py)
            → OpenClaw Gateway Engine (localhost:18789)
            ← Dynamic Tool Execution & System Output streamed back!
```

Wait for OpenClaw to process your requests. The interface will give you live, streaming text of exactly what the agent is planning, executing, and finalizing. 

---

## 🛠️ Modifying the Environment

If you would like to run the engines detached, or swap out the custom backend URL, reference `.env.local`:
```env
# Point to wherever OpenClaw is running locally
OPENCLAW_URL=http://localhost:18789
OPENCLAW_TOKEN=local
```

### Developing Locally
```bash
# 1. Start the OpenClaw Gateway
openclaw gateway start

# 2. Start the Backend Proxy
cd backend && python -m uvicorn main:app --port 8000

# 3. Start the UI Host
npm run dev
```

*Built specifically for true autonomous system delegation.*
