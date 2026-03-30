# NEXUS — Agent02

> An autonomous AI agent powered by **OpenClaw Gateway** with a Next.js dashboard, FastAPI backend, and full local desktop integration.

---

## ⚡ Quick Start (New Users)

### Step 1 — Clone the project
```
git clone <your-repo-url>
cd Agent02
```

### Step 2 — Run the setup wizard
```
python setup.py
```

The wizard will automatically:
- ✅ Install Python backend dependencies (virtualenv)
- ✅ Install Node.js frontend dependencies (`npm install`)
- ✅ Download and install **OpenClaw** globally (`npm install -g openclaw`)
- ✅ Configure OpenClaw with your AI API key (OpenAI / Google / OpenRouter)
- ✅ Generate a secure gateway token and write all `.env` files

### Step 3 — Start everything
```
start.bat
```

This opens **3 color-coded terminal windows** automatically:
1. 🟦 OpenClaw Gateway (port 18789)
2. 🟨 Python FastAPI Backend (port 8000)
3. 🟣 Next.js Frontend (port 3000)

Then opens **http://localhost:3000** in your browser.

> **That's it.** You're running.

---

## 🏗️ Architecture

```
User (Browser)
    │
    ▼
Next.js Dashboard  (localhost:3000)
    │  REST + WebSocket
    ▼
FastAPI Backend    (localhost:8000)
    │  HTTP
    ▼
OpenClaw Gateway   (localhost:18789)
    │
    ▼
Local System — Files, Office, Browser, Terminal
```

---

## 📋 Requirements

| Tool | Version |
|---|---|
| Python | 3.9+ |
| Node.js | 18+ |
| npm | 8+ |
| OpenClaw | Auto-installed by setup.py |
| AI API Key | OpenAI / Google Gemini / OpenRouter |

---

## ⚙️ Manual Setup (Alternative)

If you prefer to set up manually:

```bash
# 1. Install Python deps
cd backend
python -m venv venv
venv\Scripts\pip install -r requirements.txt   # Windows
# source venv/bin/activate && pip install -r requirements.txt  # Mac/Linux

# 2. Install Node.js deps
cd ..
npm install

# 3. Install OpenClaw
npm install -g openclaw

# 4. Configure OpenClaw
openclaw onboard

# 5. Copy and fill .env files
copy .env.example .env.local
copy backend\.env.example backend\.env
# Then fill in your API key in both files

# 6. Start services (3 terminals)
openclaw gateway run
cd backend && venv\Scripts\python main.py   # Terminal 2
npm run dev                                 # Terminal 3
```

---

## 🔑 Environment Variables

### `.env.local` (frontend)
```env
OPENCLAW_URL=http://127.0.0.1:18789
OPENCLAW_TOKEN=<your_gateway_token>
```

### `backend/.env` (backend)
```env
OPENAI_API_KEY=sk-...
```

### `backend/config.json` (AI routing)
```json
{
  "ai_provider": "openclaw",
  "ai_model": "gpt-4o-mini",
  "openclaw_token": "<same_token>",
  "openai_api_key": "sk-..."
}
```

> All these are written automatically by `python setup.py`.

---

## 🎯 What NEXUS Can Do

| Capability | Examples |
|---|---|
| 📊 Excel & Data | Generate spreadsheets, calculate averages, format cells |
| 📄 Word Docs | Write multi-page reports, format headings |
| 📑 PDF Tools | Create PDFs, split/merge documents |
| 📽️ PowerPoint | Create presentations with charts |
| 🌐 Web Search | Search Google, extract content |
| 🗂️ File Manager | Organize folders, rename, move, delete |

---

## 🛠️ Development

```bash
# Frontend only (hot reload)
npm run dev

# Backend only
cd backend
venv\Scripts\python main.py

# Gateway only
openclaw gateway run
```

---

## 🤝 Contributing

1. Fork → Branch → PR
2. Run `python setup.py` on your fork to get set up
3. Test with `npm run dev` + `python backend/main.py`
