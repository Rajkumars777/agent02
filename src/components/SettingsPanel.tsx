"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X, Save, Key, Cpu, Globe, Loader2,
  Play, Square, RefreshCw, Terminal, LogOut,
  Monitor, Battery, BatteryCharging, HardDrive, Activity, Smartphone,
  Eye, EyeOff, ChevronDown, CheckCircle2, Zap, Bot, Sparkles
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  getSettings, saveSettings, getSystemInfo,
  startOpenClawGateway, stopOpenClawGateway, getOpenClawStatus,
  pairOpenClawChannel, logoutOpenClawChannel
} from "@/lib/api";

interface SettingsPanelProps {
  onClose: () => void;
}

// ── Provider → model mapping (kept in sync with backend) ──────────────────────

const MODEL_CATALOGUE: Record<string, string[]> = {
  google: [
    "gemini-3.1-pro",
    "gemini-3.1-flash",
    "gemini-3.1-flash-lite-preview",
    "gemini-3.1-flash-live-preview",
    "gemini-3-pro",
    "gemini-3-flash",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemma-4-26b-it",
    "gemma-4-31b-it",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-1.0-pro",
  ],
  openai: [
    "gpt-5.1-codex-mini",
    "codex-mini-latest",
    "gpt-4",
    "gpt-4-turbo",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "gpt-4o",
    "gpt-4o-2024-05-13",
    "gpt-4o-2024-08-06",
    "gpt-4o-2024-11-20",
    "gpt-4o-mini",
    "gpt-5",
    "gpt-5-chat-latest",
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-5-pro",
    "gpt-5-codex",
    "gpt-5.1",
    "gpt-5.1-chat-latest",
    "gpt-5.1-codex",
    "gpt-5.1-codex-max",
    "gpt-5.2",
    "gpt-5.2-chat-latest",
    "gpt-5.2-codex",
    "gpt-5.2-pro",
    "gpt-5.3-codex",
    "gpt-5.3-codex-spark",
    "gpt-5.4",
    "gpt-5.4-pro",
    "o1",
    "o1-pro",
    "o3",
    "o3-deep-research",
    "o3-mini",
    "o3-pro",
    "o4-mini",
    "o4-mini-deep-research",
  ],
  anthropic: [
    "claude-opus-4.6",
    "claude-sonnet-4.6",
    "claude-haiku-4.5",
    "claude-opus-4.5",
    "claude-sonnet-4.5",
    "claude-3-7-sonnet",
    "claude-3-7-haiku",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307",
  ],
  openrouter: [
    "google/gemini-3.1-pro",
    "google/gemini-3.1-flash",
    "anthropic/claude-4.6-opus",
    "anthropic/claude-4.6-sonnet",
    "openai/gpt-5.4-pro",
    "openai/gpt-5.4-mini",
    "deepseek/deepseek-r1",
    "perplexity/sonar-reasoning",
    "meta-llama/llama-4-400b",
    "meta-llama/llama-4-70b",
    "mistralai/pixtral-large",
    "qwen/qwen-2.5-72b-instruct",
    "google/gemini-pro-1.5",
    "anthropic/claude-3.5-sonnet",
    "openai/gpt-4o",
    "qwen/qwq-32b:free",
  ],
  groq: [
    "llama-3.3-70b-versatile",
    "llama-3.1-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
    "qwen-2.5-72b",
    "deepseek-r1-distill-llama-70b",
    "deepseek-r1-distill-qwen-32b",
    "llama-guard-3-8b",
  ],
};

const PROVIDER_DISPLAY: Record<string, string> = {
  google:     "Google Gemini",
  openai:     "OpenAI",
  anthropic:  "Anthropic Claude",
  openrouter: "OpenRouter",
  groq:       "Groq",
};

const PROVIDER_BADGE_COLOR: Record<string, string> = {
  google:     "from-blue-500/20 to-cyan-500/20 border-blue-500/30 text-blue-400",
  openai:     "from-emerald-500/20 to-teal-500/20 border-emerald-500/30 text-emerald-400",
  anthropic:  "from-amber-500/20 to-orange-500/20 border-amber-500/30 text-amber-400",
  openrouter: "from-violet-500/20 to-fuchsia-500/20 border-violet-500/30 text-violet-400",
  groq:       "from-rose-500/20 to-pink-500/20 border-rose-500/30 text-rose-400",
};

const KEY_HINTS: Record<string, string> = {
  google:     "AIza...  →  aistudio.google.com",
  openai:     "sk-...  →  platform.openai.com",
  anthropic:  "sk-ant-...  →  console.anthropic.com",
  openrouter: "sk-or-...  →  openrouter.ai",
  groq:       "gsk_...  →  console.groq.com",
};

// ── Custom select component ────────────────────────────────────────────────────

function StyledSelect({
  value, onChange, options, placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const selected = options.find((o) => o.value === value);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between gap-2 bg-slate-50/80 dark:bg-slate-950/60 hover:bg-white dark:bg-slate-900 border border-slate-300/80 dark:border-slate-700/60 hover:border-violet-500/40 rounded-xl px-4 py-3 text-sm font-medium text-slate-800 dark:text-slate-200 outline-none transition-all focus:ring-2 focus:ring-violet-500/30"
      >
        <span className={!selected ? "text-slate-500" : ""}>
          {selected?.label || placeholder || "Select…"}
        </span>
        <ChevronDown className={cn("w-4 h-4 text-slate-500 transition-transform duration-200", open && "rotate-180")} />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.97 }}
            transition={{ duration: 0.15 }}
            className="absolute z-50 top-full mt-1.5 left-0 right-0 bg-white dark:bg-slate-900 border border-slate-300/80 dark:border-slate-700/60 rounded-xl shadow-2xl shadow-black/40 overflow-hidden max-h-52 overflow-y-auto custom-scrollbar"
          >
            {options.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => { onChange(opt.value); setOpen(false); }}
                className={cn(
                  "w-full flex items-center justify-between px-4 py-2.5 text-sm transition-colors text-left hover:bg-violet-600/15",
                  opt.value === value ? "text-violet-300 bg-violet-600/10 font-semibold" : "text-slate-700 dark:text-slate-300"
                )}
              >
                <span className="truncate">{opt.label}</span>
                {opt.value === value && <CheckCircle2 className="w-3.5 h-3.5 text-violet-400 shrink-0 ml-2" />}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

export function SettingsPanel({ onClose }: SettingsPanelProps) {
  // ─── AI Settings
  const [aiProvider, setAiProvider] = useState("openai");
  const [apiKey, setApiKey] = useState("");
  const [apiKeyMasked, setApiKeyMasked] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [aiModel, setAiModel] = useState("gpt-5.1-codex-mini");
  const [browserEngine, setBrowserEngine] = useState("");
  const [availableBrowsers, setAvailableBrowsers] = useState<{name: string, path: string}[]>([]);

  // ─── OpenClaw Gateway
  const [gwStatus, setGwStatus] = useState("stopped");
  const [gwPort, setGwPort] = useState(18789);
  const [gwLogs, setGwLogs] = useState<string[]>([]);
  const [gwModel, setGwModel] = useState("");

  // ─── System Data
  const [sysInfo, setSysInfo] = useState<any>(null);

  // ─── UI State
  const [activeTab, setActiveTab] = useState<"ai" | "openclaw" | "system">("ai");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [msgType, setMsgType] = useState<"ok" | "err" | "info">("ok");
  const [loading, setLoading] = useState(true);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const logsRef = useRef<HTMLDivElement>(null);

  // Auto-scroll logs
  useEffect(() => {
    if (logsRef.current) {
      logsRef.current.scrollTop = logsRef.current.scrollHeight;
    }
  }, [gwLogs]);

  // Load settings on mount
  useEffect(() => {
    (async () => {
      try {
        const [settingsData, statusData, sysData] = await Promise.all([
          getSettings().catch(() => ({})),
          getOpenClawStatus().catch(() => ({})),
          getSystemInfo().catch(() => null),
        ]);
        const s = settingsData?.settings || {};

        // Normalise legacy "gemini" → "google"
        const prov = s.ai_provider === "gemini" ? "google" : (s.ai_provider || "google");
        setAiProvider(prov);

        const savedModel = s.ai_model || "";
        const stripped = savedModel.includes("/") ? savedModel.split("/").pop()! : savedModel;
        // Pick stripped if it exists in catalogue, else first in list
        const catalogue = MODEL_CATALOGUE[prov] || [];
        setAiModel(catalogue.includes(stripped) ? stripped : catalogue.includes(savedModel) ? savedModel : catalogue[0] || "");
        setApiKeyMasked(s.api_key_masked || "");
        setBrowserEngine(s.browser_engine || "");

        const bData = settingsData?.available_browsers || [];
        setAvailableBrowsers(bData);

        if (sysData && !sysData.detail) setSysInfo(sysData);

        setGwStatus(statusData.status || "stopped");
        setGwPort(statusData.port || 18789);
        setGwLogs(statusData.log_tail || []);
        setGwModel(statusData.model || "");
      } catch {}
      setLoading(false);
    })();
  }, []);

  // Poll gateway status every 3s
  useEffect(() => {
    pollRef.current = setInterval(async () => {
      try {
        const data = await getOpenClawStatus();
        setGwStatus(data.status || "stopped");
        setGwLogs(data.log_tail || []);
        setGwModel(data.model || "");
      } catch {}
      try {
        const sys = await getSystemInfo();
        if (sys && !sys.detail) setSysInfo(sys);
      } catch {}
    }, 3000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  // When provider changes → reset to first model in list
  const handleProviderChange = (p: string) => {
    setAiProvider(p);
    setAiModel(MODEL_CATALOGUE[p]?.[0] || "");
    setApiKey("");
    setShowKey(false);
  };

  const showMsg = (text: string, type: "ok" | "err" | "info" = "ok") => {
    setMessage(text);
    setMsgType(type);
    setTimeout(() => setMessage(""), 4000);
  };

  const handleStartGateway = async () => {
    try {
      const result = await startOpenClawGateway(gwPort);
      setGwStatus(result.status || "starting");
      showMsg(result.message || "Gateway starting…", "info");
    } catch {
      showMsg("❌ Backend server unreachable.", "err");
      setGwStatus("stopped");
    }
  };

  const handleStopGateway = async () => {
    try {
      const result = await stopOpenClawGateway();
      setGwStatus("stopped");
      showMsg(result.message || "Gateway stopped.", "info");
    } catch {
      showMsg("❌ Failed to contact backend.", "err");
    }
  };

  const handleSaveAI = async () => {
    setSaving(true);
    setMessage("");
    try {
      const payload: Record<string, string> = {
        ai_provider: aiProvider,
        ai_model: aiModel,
        browser_engine: browserEngine
      };
      if (apiKey.trim()) payload.api_key = apiKey.trim();

      await saveSettings(payload);
      setApiKeyMasked(apiKey.trim() ? apiKey.trim().slice(0, 4) + "•••••••" + apiKey.trim().slice(-4) : apiKeyMasked);
      setApiKey("");
      setShowKey(false);
      showMsg("✅ AI settings saved & configured!", "ok");
    } catch {
      showMsg("❌ Failed to save settings.", "err");
    }
    setSaving(false);
  };

  const statusColor = gwStatus === "running" ? "text-emerald-400" : gwStatus === "starting" ? "text-amber-400" : "text-rose-400";
  const statusDot = gwStatus === "running" ? "bg-emerald-500 shadow-[0_0_8px_2px_rgba(16,185,129,0.4)]" : gwStatus === "starting" ? "bg-amber-500 animate-pulse shadow-[0_0_8px_2px_rgba(245,158,11,0.4)]" : "bg-rose-500 shadow-[0_0_8px_2px_rgba(239,68,68,0.3)]";
  const currentBadge = PROVIDER_BADGE_COLOR[aiProvider] || PROVIDER_BADGE_COLOR.google;

  const providerOptions = Object.entries(PROVIDER_DISPLAY).map(([v, l]) => ({ value: v, label: l }));
  const modelOptions = (MODEL_CATALOGUE[aiProvider] || []).map((m) => ({ value: m, label: m }));

  return (
    <motion.div
      initial={{ x: "100%" }}
      animate={{ x: 0 }}
      exit={{ x: "100%" }}
      transition={{ type: "spring", damping: 28, stiffness: 220 }}
      className="fixed right-0 bottom-0 w-[480px] bg-white/95 dark:bg-slate-950/95 backdrop-blur-2xl border-l border-slate-200/80 dark:border-slate-800/60 z-[101] shadow-[0_0_80px_-20px_rgba(0,0,0,0.15)] dark:shadow-[0_0_80px_-20px_rgba(0,0,0,0.8)] flex flex-col font-sans"
      style={{ top: "var(--titlebar-height, 0px)" }}
    >
      {/* Gradient accent top */}
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-violet-500/60 to-transparent" />

      {/* Header */}
      <div className="px-6 py-5 border-b border-slate-200/80 dark:border-slate-800/60 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-violet-500/10 border border-violet-500/20">
            <Cpu className="w-5 h-5 text-violet-400" />
          </div>
          <div>
            <h2 className="text-[15px] font-bold text-slate-900 dark:text-slate-100 tracking-tight">Settings</h2>
            <p className="text-[11px] text-slate-500 font-medium mt-0.5">NEXUS Configuration</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-2 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500 hover:text-slate-700 dark:text-slate-300 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex px-2 pt-2 border-b border-slate-200/80 dark:border-slate-800/60 bg-slate-100/80 dark:bg-slate-950/50">
        {[
          { id: "ai" as const, label: "AI Model", icon: Bot },
          { id: "openclaw" as const, label: "Gateway", icon: Globe },
          { id: "system" as const, label: "System", icon: Activity },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "flex-1 py-3 px-2 text-[12px] font-semibold uppercase tracking-widest transition-all flex items-center justify-center gap-1.5 border-b-2 rounded-t-lg -mb-px",
              activeTab === tab.id
                ? "border-violet-500 text-violet-400 bg-violet-500/5"
                : "border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-300 hover:bg-slate-200/40 dark:bg-slate-800/40"
            )}
          >
            <tab.icon className="w-3.5 h-3.5" />
            {tab.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="w-7 h-7 animate-spin text-violet-500" />
            <p className="text-sm text-slate-500 font-medium">Loading configuration…</p>
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-5 space-y-4 custom-scrollbar">

          {/* ─── AI Model Tab ─── */}
          {activeTab === "ai" && (
            <div className="animate-in fade-in slide-in-from-bottom-3 duration-300 space-y-4">

              {/* Current config badge */}
              <div className={cn(
                "flex items-center gap-3 p-3.5 rounded-xl border bg-gradient-to-r",
                currentBadge
              )}>
                <Sparkles className="w-4 h-4 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-bold uppercase tracking-wider opacity-70 mb-0.5">Active Configuration</p>
                  <p className="text-sm font-semibold truncate">
                    {PROVIDER_DISPLAY[aiProvider] || aiProvider} · {aiModel || "—"}
                  </p>
                </div>
              </div>

              {/* Provider */}
              <div className="space-y-2">
                <label className="text-[11px] text-slate-600 dark:text-slate-400 font-bold uppercase tracking-widest flex items-center gap-1.5">
                  <Globe className="w-3 h-3" /> AI Provider
                </label>
                <StyledSelect
                  value={aiProvider}
                  onChange={handleProviderChange}
                  options={providerOptions}
                />
              </div>

              {/* Model */}
              <div className="space-y-2">
                <label className="text-[11px] text-slate-600 dark:text-slate-400 font-bold uppercase tracking-widest flex items-center gap-1.5">
                  <Zap className="w-3 h-3" /> Foundation Model
                </label>
                <StyledSelect
                  value={aiModel}
                  onChange={setAiModel}
                  options={modelOptions}
                  placeholder="Select a model…"
                />
                <p className="text-[10px] text-slate-600 font-medium pl-1">
                  {modelOptions.length} models available for {PROVIDER_DISPLAY[aiProvider] || aiProvider}
                </p>
              </div>

              {/* Browser Selection */}
              <div className="space-y-2">
                <label className="text-[11px] text-slate-600 dark:text-slate-400 font-bold uppercase tracking-widest flex items-center gap-1.5">
                  <Monitor className="w-3 h-3" /> Web Automation Browser
                </label>
                <StyledSelect
                  value={browserEngine}
                  onChange={setBrowserEngine}
                  options={[
                    { value: "", label: "Default (Bundled Chromium)" },
                    ...availableBrowsers.map(b => ({ value: b.name, label: b.name }))
                  ]}
                  placeholder="Select system browser…"
                />
                <p className="text-[10px] text-slate-500 font-medium pl-1">
                  {availableBrowsers.length > 0 
                    ? `Detected ${availableBrowsers.length} installed browsers.` 
                    : "No system browsers detected. Using bundled engine."}
                </p>
              </div>

              {/* API Key */}
              <div className="space-y-2">
                <label className="text-[11px] text-slate-600 dark:text-slate-400 font-bold uppercase tracking-widest flex items-center gap-1.5">
                  <Key className="w-3 h-3" /> API Key
                </label>

                {/* Current key display */}
                {apiKeyMasked && !showKey && (
                  <div className="flex items-center gap-2 px-4 py-2.5 bg-white/80 dark:bg-slate-900/60 border border-slate-300/60 dark:border-slate-700/40 rounded-xl">
                    <span className="text-sm font-mono text-slate-600 dark:text-slate-400 flex-1 truncate">{apiKeyMasked}</span>
                    <span className="text-[10px] text-emerald-500 font-bold uppercase tracking-wider flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3" /> Configured
                    </span>
                  </div>
                )}

                {/* Input for new key */}
                <div className="relative">
                  <input
                    id="nexus-api-key"
                    type={showKey ? "text" : "password"}
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder={apiKeyMasked ? "Enter new key to change…" : (KEY_HINTS[aiProvider] || "Paste API key…")}
                    className="w-full bg-slate-50/80 dark:bg-slate-950/60 hover:bg-white/80 dark:bg-slate-900/60 border border-slate-300/80 dark:border-slate-700/60 focus:border-violet-500/60 rounded-xl px-4 py-3 pr-12 text-sm font-mono text-slate-800 dark:text-slate-200 placeholder:text-slate-400 dark:placeholder:text-slate-600 placeholder:font-sans outline-none focus:ring-2 focus:ring-violet-500/20 transition-all"
                  />
                  <button
                    type="button"
                    onClick={() => setShowKey(!showKey)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-700 dark:text-slate-300 transition-colors"
                  >
                    {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>

                {/* Key hint */}
                <p className="text-[10px] text-slate-600 font-medium pl-1 font-mono">
                  {KEY_HINTS[aiProvider] || ""}
                </p>
              </div>

              {/* Info box */}
              <div className="flex gap-2.5 p-3.5 rounded-xl bg-slate-100/60 dark:bg-slate-900/40 border border-slate-200/80 dark:border-slate-800/60">
                <RefreshCw className="w-3.5 h-3.5 text-slate-500 mt-0.5 shrink-0" />
                <p className="text-[11px] text-slate-500 leading-relaxed">
                  Saving will immediately reconfigure the AI engine and OpenClaw auth profile on this system. No restart required.
                </p>
              </div>
            </div>
          )}

          {/* ─── Gateway Tab ─── */}
          {activeTab === "openclaw" && (
            <div className="animate-in fade-in slide-in-from-bottom-3 duration-300 space-y-4">

              {/* Status Card */}
              <div className="p-5 rounded-2xl bg-white/80 dark:bg-slate-900/60 border border-slate-200/80 dark:border-slate-800/60 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={cn("w-2.5 h-2.5 rounded-full", statusDot)} />
                    <span className={cn("text-sm font-bold tracking-tight", statusColor)}>
                      Gateway {gwStatus === "running" ? "Running" : gwStatus === "starting" ? "Starting…" : "Stopped"}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-500 font-mono bg-white dark:bg-slate-900 px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-800">
                      :{gwPort}
                    </span>
                    <button
                      onClick={gwStatus === "running" ? handleStopGateway : handleStartGateway}
                      className={cn(
                        "p-2.5 rounded-xl border transition-all",
                        gwStatus === "running"
                          ? "bg-rose-500/10 border-rose-500/20 hover:bg-rose-500/20 text-rose-400"
                          : "bg-emerald-500/10 border-emerald-500/20 hover:bg-emerald-500/20 text-emerald-400"
                      )}
                    >
                      {gwStatus === "running"
                        ? <Square className="w-3.5 h-3.5 fill-current" />
                        : <Play className="w-3.5 h-3.5 fill-current ml-0.5" />}
                    </button>
                  </div>
                </div>

                {gwModel && (
                  <div className="flex items-center gap-2 text-xs text-slate-500">
                    Model:
                    <span className="text-slate-700 dark:text-slate-300 font-mono bg-slate-100/80 dark:bg-slate-900/80 px-2 py-0.5 rounded-lg border border-slate-200 dark:border-slate-800">
                      {gwModel}
                    </span>
                  </div>
                )}

                <p className="text-[11px] text-slate-600 font-medium">
                  OpenClaw Gateway is auto-managed and starts with the application.
                </p>
              </div>

              {/* Logs */}
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                  <Terminal className="w-3.5 h-3.5" /> Console Output
                </div>
                <div
                  ref={logsRef}
                  className="bg-white dark:bg-slate-950 rounded-xl border border-slate-200/80 dark:border-slate-800/60 p-4 h-[280px] overflow-y-auto font-mono text-[11px] text-emerald-400/80 custom-scrollbar"
                >
                  {gwLogs.length === 0 ? (
                    <span className="text-slate-600 italic">No logs yet…</span>
                  ) : (
                    gwLogs.map((line, i) => (
                      <div key={i} className="leading-relaxed mb-1 break-all opacity-90">{line}</div>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}

          {/* ─── System Info Tab ─── */}
          {activeTab === "system" && (
            <div className="animate-in fade-in slide-in-from-bottom-3 duration-300 space-y-4 pb-4">
              {sysInfo ? (
                <>
                  {/* CPU */}
                  <div className="p-5 rounded-2xl bg-white/80 dark:bg-slate-900/60 border border-slate-200/80 dark:border-slate-800/60 flex items-center gap-4">
                    <div className="p-3 bg-violet-500/10 rounded-xl border border-violet-500/20">
                      <Cpu className="w-5 h-5 text-violet-400" />
                    </div>
                    <div className="flex-1">
                      <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">Processor</p>
                      <div className="flex items-baseline gap-2 mb-2">
                        <span className="text-2xl font-black text-slate-900 dark:text-slate-100">{sysInfo.cpu?.percent ?? 0}%</span>
                        <span className="text-xs text-slate-500">{sysInfo.cpu?.cores || "?"} Cores</span>
                      </div>
                      <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                        <div className="bg-violet-500 h-full transition-all duration-700 ease-out rounded-full" style={{ width: `${sysInfo.cpu?.percent ?? 0}%` }} />
                      </div>
                    </div>
                  </div>

                  {/* RAM */}
                  <div className="p-5 rounded-2xl bg-white/80 dark:bg-slate-900/60 border border-slate-200/80 dark:border-slate-800/60 flex items-center gap-4">
                    <div className="p-3 bg-blue-500/10 rounded-xl border border-blue-500/20">
                      <HardDrive className="w-5 h-5 text-blue-400" />
                    </div>
                    <div className="flex-1">
                      <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">Memory</p>
                      <div className="flex items-baseline gap-2 mb-2">
                        <span className="text-2xl font-black text-slate-900 dark:text-slate-100">{sysInfo.memory?.percent ?? 0}%</span>
                        <span className="text-xs text-slate-500">
                          {((sysInfo.memory?.used || 0) / 1073741824).toFixed(1)} / {((sysInfo.memory?.total || 0) / 1073741824).toFixed(1)} GB
                        </span>
                      </div>
                      <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                        <div className="bg-blue-500 h-full transition-all duration-700 ease-out rounded-full" style={{ width: `${sysInfo.memory?.percent ?? 0}%` }} />
                      </div>
                    </div>
                  </div>

                  {/* Battery */}
                  {sysInfo.battery?.percent !== null && (
                    <div className="p-5 rounded-2xl bg-white/80 dark:bg-slate-900/60 border border-slate-200/80 dark:border-slate-800/60 flex items-center gap-4">
                      <div className="p-3 bg-emerald-500/10 rounded-xl border border-emerald-500/20">
                        {sysInfo.battery?.plugged ? <BatteryCharging className="w-5 h-5 text-emerald-400" /> : <Battery className="w-5 h-5 text-emerald-400" />}
                      </div>
                      <div className="flex-1">
                        <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">Battery</p>
                        <div className="flex items-baseline gap-2 mb-2">
                          <span className="text-2xl font-black text-slate-900 dark:text-slate-100">{Math.round(sysInfo.battery?.percent)}%</span>
                          <span className="text-xs text-slate-500">{sysInfo.battery?.plugged ? "Plugged In" : "On Battery"}</span>
                        </div>
                        <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                          <div className="bg-emerald-500 h-full transition-all duration-700 ease-out rounded-full" style={{ width: `${Math.round(sysInfo.battery?.percent)}%` }} />
                        </div>
                      </div>
                    </div>
                  )}

                  {/* System Specs */}
                  <div className="p-5 rounded-2xl bg-white/80 dark:bg-slate-900/60 border border-slate-200/80 dark:border-slate-800/60 space-y-3">
                    <div className="flex items-center gap-2 text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                      <Smartphone className="w-3.5 h-3.5" /> System Specs
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      {[
                        { label: "Host", value: sysInfo.os?.node || "Unknown" },
                        { label: "Platform", value: sysInfo.os?.system || "Unknown" },
                      ].map((item) => (
                        <div key={item.label} className="bg-slate-50/80 dark:bg-slate-950/60 p-3 rounded-xl border border-slate-200/80 dark:border-slate-800/60">
                          <p className="text-[9px] font-bold text-slate-600 uppercase tracking-wider mb-1">{item.label}</p>
                          <p className="text-xs font-semibold text-slate-700 dark:text-slate-300 truncate">{item.value}</p>
                        </div>
                      ))}
                    </div>
                    {sysInfo.gpu?.length > 0 && (
                      <div className="bg-slate-50/80 dark:bg-slate-950/60 p-3 rounded-xl border border-slate-200/80 dark:border-slate-800/60">
                        <p className="text-[9px] font-bold text-slate-600 uppercase tracking-wider mb-1">GPU</p>
                        {sysInfo.gpu.map((g: string, i: number) => (
                          <p key={i} className="text-xs font-semibold text-slate-700 dark:text-slate-300 truncate">{g}</p>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <div className="flex flex-col items-center justify-center py-16 gap-3 text-slate-600">
                  <Monitor className="w-8 h-8 opacity-40" />
                  <p className="text-sm font-medium">Gathering system metrics…</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="p-5 border-t border-slate-200/80 dark:border-slate-800/60 bg-slate-950/80 space-y-3">
        {/* Status message */}
        <AnimatePresence>
          {message && (
            <motion.p
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 4 }}
              className={cn(
                "text-[12px] text-center font-bold tracking-wide py-2 px-4 rounded-xl",
                msgType === "ok"   && "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20",
                msgType === "err"  && "bg-rose-500/10 text-rose-400 border border-rose-500/20",
                msgType === "info" && "bg-violet-500/10 text-violet-400 border border-violet-500/20",
              )}
            >
              {message}
            </motion.p>
          )}
        </AnimatePresence>

        {/* Save button — only on AI tab */}
        {activeTab === "ai" && (
          <button
            onClick={handleSaveAI}
            disabled={saving}
            className={cn(
              "w-full py-3.5 rounded-2xl font-bold text-[14px] tracking-wide flex items-center justify-center gap-2.5 transition-all",
              saving
                ? "bg-slate-800 text-slate-500 cursor-not-allowed"
                : "bg-gradient-to-r from-violet-600 to-indigo-600 text-white shadow-lg shadow-violet-900/40 hover:shadow-xl hover:shadow-violet-900/60 hover:-translate-y-0.5 active:translate-y-0"
            )}
          >
            {saving
              ? <><Loader2 className="w-4 h-4 animate-spin" /> Saving configuration…</>
              : <><Save className="w-4 h-4" /> Save &amp; Apply</>}
          </button>
        )}
      </div>
    </motion.div>
  );
}
