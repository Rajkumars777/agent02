"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X, Save, Key, MessageSquare, Cpu, Globe, Loader2,
  Play, Square, RefreshCw, QrCode, Wifi, WifiOff, Terminal, LogOut
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  getSettings, saveSettings,
  startOpenClawGateway, stopOpenClawGateway, getOpenClawStatus, pairOpenClawChannel, logoutOpenClawChannel
} from "@/lib/api";

interface SettingsPanelProps {
  onClose: () => void;
}

export function SettingsPanel({ onClose }: SettingsPanelProps) {
  // ─── AI Settings ───────────────────────────────────────────────────
  const [aiProvider, setAiProvider] = useState("gemini");
  const [apiKey, setApiKey] = useState("");
  const [aiModel, setAiModel] = useState("gemini-2.5-flash");

  // ─── OpenClaw Gateway ──────────────────────────────────────────────
  const [gwStatus, setGwStatus] = useState("stopped");
  const [gwPort, setGwPort] = useState(18789);
  const [gwLogs, setGwLogs] = useState<string[]>([]);
  const [gwModel, setGwModel] = useState("");
  const [gwChannels, setGwChannels] = useState<Record<string, any>>({});
  const [qrData, setQrData] = useState<string | null>(null);

  // ─── Channel Pairing ──────────────────────────────────────────────
  const [pairingChannel, setPairingChannel] = useState("whatsapp");
  const [isPairing, setIsPairing] = useState(false);
  const [pairingOutput, setPairingOutput] = useState("");
  const [telegramToken, setTelegramToken] = useState("");
  const [slackToken, setSlackToken] = useState("");

  // ─── UI State ─────────────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState<"ai" | "openclaw">("openclaw");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Load settings on mount
  useEffect(() => {
    (async () => {
      try {
        const [settingsData, statusData] = await Promise.all([
          getSettings().catch(() => ({})),
          getOpenClawStatus().catch(() => ({})),
        ]);
        const s = settingsData.settings || {};
        setAiProvider(s.ai_provider || "gemini");
        setAiModel(s.ai_model || "gemini-2.5-flash");

        setGwStatus(statusData.status || "stopped");
        setGwPort(statusData.port || 18789);
        setGwLogs(statusData.log_tail || []);
        setGwModel(statusData.model || "");
        setGwChannels(statusData.channels || {});
        setQrData(statusData.qr_data || null);

        const tgToken = statusData.channels?.telegram?.token || "";
        setTelegramToken(tgToken);
        const slToken = statusData.channels?.slack?.token || "";
        setSlackToken(slToken);
      } catch { }
      setLoading(false);
    })();
  }, []);

  // Poll gateway status every 3s when panel is open
  useEffect(() => {
    pollRef.current = setInterval(async () => {
      try {
        const data = await getOpenClawStatus();
        setGwStatus(data.status || "stopped");
        setGwLogs(data.log_tail || []);
        setGwModel(data.model || "");
        setGwChannels(data.channels || {});
        if (data.qr_data) setQrData(data.qr_data);
      } catch { }
    }, 3000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const handleStartGateway = async () => {
    setMessage("");
    try {
      const result = await startOpenClawGateway(gwPort);
      setGwStatus(result.status || "starting");
      setMessage(result.message || "Gateway starting...");
    } catch (e) {
      console.error("Failed to start gateway:", e);
      setMessage("❌ Error: Backend server unreachable. Is it running?");
      setGwStatus("stopped");
    }
  };

  const handleStopGateway = async () => {
    setMessage("");
    try {
      const result = await stopOpenClawGateway();
      setGwStatus("stopped");
      setMessage(result.message || "Gateway stopped");
    } catch (e) {
      console.error("Failed to stop gateway:", e);
      setMessage("❌ Error: Failed to contact backend.");
    }
  };

  const handlePairChannel = async () => {
    setIsPairing(true);
    setPairingOutput("");
    setQrData(null);
    try {
      const result = await pairOpenClawChannel(pairingChannel);
      setPairingOutput(result.output || "Pairing process completed");
      if (result.qr_data) setQrData(result.qr_data);
    } catch (e) {
      setPairingOutput("Failed to start channel pairing");
    }
    setIsPairing(false);
  };

  const handleLogoutChannel = async () => {
    if (!confirm(`Are you sure you want to log out of ${pairingChannel}? This will disconnect the current account.`)) return;

    setSaving(true);
    setMessage("");
    try {
      const result = await logoutOpenClawChannel(pairingChannel);
      setMessage(result.message || "Logged out successfully");
      setQrData(null);
      // Refresh status immediately
      const data = await getOpenClawStatus();
      setGwChannels(data.channels || {});
    } catch (e) {
      setMessage("❌ Logout failed");
    }
    setSaving(false);
  };

  const handleSaveChannelConfig = async () => {
    setSaving(true);
    setMessage("");
    try {
      const { saveOpenClawConfig } = await import("@/lib/api");
      await saveOpenClawConfig({
        telegram_token: telegramToken,
        slack_token: slackToken,
        telegram_enabled: !!telegramToken,
        slack_enabled: !!slackToken,
      });
      setMessage("✅ Channel config saved!");
    } catch { setMessage("❌ Failed to save"); }
    setSaving(false);
  };

  const handleSaveAI = async () => {
    setSaving(true);
    setMessage("");
    try {
      const payload: Record<string, string> = { ai_provider: aiProvider, ai_model: aiModel };
      if (apiKey) payload.api_key = apiKey;
      await saveSettings(payload);
      setMessage("✅ AI settings saved!");
      setApiKey("");
    } catch { setMessage("❌ Failed to save"); }
    setSaving(false);
  };
  const modelOptions: Record<string, string[]> = {
    gemini: ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"],
    openrouter: ["google/gemini-2.5-flash", "google/gemini-2.0-flash-001", "anthropic/claude-3.5-sonnet", "openai/gpt-4o"],
    openai: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
    groq: ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
  };

  const statusColor = gwStatus === "running" ? "text-emerald-600" : gwStatus === "starting" ? "text-amber-500" : "text-rose-500";
  const statusDot = gwStatus === "running" ? "bg-emerald-500 ring-emerald-500/30" : gwStatus === "starting" ? "bg-amber-500 ring-amber-500/30 animate-pulse" : "bg-rose-500 ring-rose-500/30";

  return (
    <motion.div
      initial={{ x: "100%" }}
      animate={{ x: 0 }}
      exit={{ x: "100%" }}
      transition={{ type: "spring", damping: 25, stiffness: 200 }}
      className="fixed top-0 right-0 bottom-0 w-[460px] bg-white/95 backdrop-blur-2xl border-l border-slate-200/60 z-[101] shadow-[0_0_50px_-12px_rgba(0,0,0,0.15)] flex flex-col font-sans"
    >
      {/* Header */}
      <div className="p-6 border-b border-slate-100 flex items-center justify-between bg-white text-slate-900 rounded-tl-3xl">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-violet-50 text-violet-600 shadow-sm border border-violet-100/50">
            <Cpu className="w-5 h-5" />
          </div>
          <h2 className="text-xl font-semibold tracking-tight">Settings</h2>
        </div>
        <button onClick={onClose} className="p-2.5 rounded-full hover:bg-slate-100 text-slate-400 hover:text-slate-700 transition-colors">
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex px-4 pt-3 bg-slate-50/50 border-b border-slate-200 shadow-sm z-10">
        {[
          { id: "openclaw" as const, label: "Nexus", icon: Globe },
          { id: "ai" as const, label: "AI Config", icon: Key },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "flex-1 py-3 px-1 text-[13px] font-semibold uppercase tracking-wider transition-all border-b-2 flex items-center justify-center gap-2",
              activeTab === tab.id
                ? "border-violet-600 text-violet-700 bg-white rounded-t-xl"
                : "border-transparent text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-t-xl"
            )}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex-1 flex items-center justify-center bg-slate-50/50">
          <Loader2 className="w-6 h-6 animate-spin text-violet-500" />
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-6 space-y-8 bg-slate-50/50 custom-scrollbar">

          {/* ─── OpenClaw Tab ─── */}
          {activeTab === "openclaw" && (
            <div className="animate-in fade-in slide-in-from-bottom-2 duration-300 space-y-6">
              {/* Gateway Status Card */}
              <div className="p-5 rounded-[22px] bg-white border border-slate-200 shadow-sm space-y-4 relative overflow-hidden">
                <div className="absolute top-0 left-0 w-1.5 h-full bg-gradient-to-b from-violet-400 to-indigo-500 opacity-60" />
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={cn("w-2.5 h-2.5 rounded-full ring-4 bg-clip-padding", statusDot)} />
                    <span className={cn("text-sm font-semibold tracking-tight", statusColor)}>
                      Gateway {gwStatus === "running" ? "Running" : gwStatus === "starting" ? "Starting..." : "Stopped"}
                    </span>
                  </div>
                  <div className="flex items-center gap-2.5">
                    <button
                      onClick={gwStatus === "running" ? handleStopGateway : handleStartGateway}
                      className="p-2 rounded-xl bg-white border border-slate-200 shadow-sm hover:border-slate-300 hover:shadow transition-all text-slate-700 focus:outline-none focus:ring-4 focus:ring-slate-100"
                    >
                      {gwStatus === "running" ? <Square className="w-3.5 h-3.5 fill-rose-500 text-rose-500" /> : <Play className="w-3.5 h-3.5 fill-emerald-500 text-emerald-500 ml-0.5" />}
                    </button>
                    <span className="text-xs text-slate-400 font-mono font-semibold bg-slate-100 px-2 py-1 rounded-lg border border-slate-200">:{gwPort}</span>
                  </div>
                </div>

                {gwModel && (
                  <div className="text-sm text-slate-500 flex items-center gap-2 mt-2">
                    Model: <span className="text-slate-800 font-mono font-medium bg-slate-50 px-2.5 py-1 rounded-lg border border-slate-200/70">{gwModel}</span>
                  </div>
                )}

                <p className="text-xs text-slate-400 font-medium pt-1">
                  Auto-managed — gateway launches gracefully with the application.
                </p>
              </div>

              {/* Gateway Logs */}
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-xs font-bold text-slate-400 uppercase tracking-widest pl-1">
                  <Terminal className="w-4 h-4 text-slate-400" /> Console Logs
                </div>
                <div className="bg-slate-900 rounded-[20px] border border-slate-800 p-5 max-h-[250px] overflow-y-auto font-mono text-xs text-emerald-400/90 shadow-inner custom-scrollbar ring-1 ring-inset ring-black/20">
                  {gwLogs.length === 0 ? (
                    <span className="text-slate-500 italic">No logs yet...</span>
                  ) : (
                    gwLogs.map((line, i) => (
                      <div key={i} className="leading-relaxed mb-1.5 opacity-90 break-all">{line}</div>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}

          {/* ─── AI Config Tab ─── */}
          {activeTab === "ai" && (
            <div className="animate-in fade-in slide-in-from-bottom-2 duration-300 space-y-6">
              <div className="p-6 rounded-[24px] bg-white shadow-sm border border-slate-200/80 space-y-5">
                <div className="space-y-2">
                  <label className="text-[11px] text-slate-400 font-bold uppercase tracking-widest ml-1">AI Provider</label>
                  <div className="relative">
                    <select
                      value={aiProvider}
                      onChange={(e) => {
                        setAiProvider(e.target.value);
                        setAiModel(modelOptions[e.target.value]?.[0] || "");
                      }}
                      className="w-full appearance-none bg-slate-50 hover:bg-slate-100/50 border border-slate-200 cursor-pointer rounded-2xl px-4 py-3.5 text-sm font-semibold text-slate-800 outline-none focus:ring-4 focus:ring-violet-500/10 focus:border-violet-500 transition-all"
                    >
                      <option value="gemini">Google Gemini</option>
                      <option value="openrouter">OpenRouter</option>
                      <option value="openai">OpenAI</option>
                      <option value="groq">Groq</option>
                    </select>
                    <div className="absolute inset-y-0 right-4 flex items-center pointer-events-none text-slate-400">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
                    </div>
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="text-[11px] text-slate-400 font-bold uppercase tracking-widest ml-1">Foundation Model</label>
                  <div className="relative">
                    <select
                      value={aiModel}
                      onChange={(e) => setAiModel(e.target.value)}
                      className="w-full appearance-none bg-slate-50 hover:bg-slate-100/50 border border-slate-200 cursor-pointer rounded-2xl px-4 py-3.5 text-sm font-semibold text-slate-800 outline-none focus:ring-4 focus:ring-violet-500/10 focus:border-violet-500 transition-all"
                    >
                      {(modelOptions[aiProvider] || []).map((m) => (
                        <option key={m} value={m}>{m}</option>
                      ))}
                    </select>
                    <div className="absolute inset-y-0 right-4 flex items-center pointer-events-none text-slate-400">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
                    </div>
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="text-[11px] text-slate-400 font-bold uppercase tracking-widest ml-1">Access Token</label>
                  <input
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="sk-..."
                    className="w-full bg-slate-50 border border-slate-200 rounded-2xl px-4 py-3.5 text-sm font-semibold text-slate-800 placeholder:text-slate-300 placeholder:font-medium outline-none focus:ring-4 focus:ring-violet-500/10 focus:border-violet-500 transition-all"
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="p-6 border-t border-slate-200 bg-white space-y-3 shadow-[0_-4px_20px_-10px_rgba(0,0,0,0.03)] z-10">
        {message && (
          <motion.p
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            className={cn(
              "text-[13px] text-center font-bold tracking-wide",
              message.startsWith("✅") ? "text-emerald-500" : message.startsWith("❌") ? "text-rose-500" : "text-violet-500"
            )}
          >
            {message}
          </motion.p>
        )}
        {activeTab === "ai" && (
           <button
             onClick={handleSaveAI}
             disabled={saving}
             className={cn(
               "w-full py-4 rounded-[20px] font-bold text-[15px] tracking-wide flex items-center justify-center gap-2.5 transition-all outline-none",
               saving
                 ? "bg-slate-100 text-slate-400 cursor-not-allowed border border-slate-200"
                 : "bg-gradient-to-r from-violet-600 to-indigo-600 focus:ring-4 focus:ring-violet-500/30 text-white shadow-lg shadow-violet-500/25 hover:shadow-xl hover:shadow-violet-500/40 hover:-translate-y-0.5 active:translate-y-0 disabled:opacity-50"
             )}
           >
             {saving ? <Loader2 className="w-5 h-5 animate-spin" /> : <Save className="w-5 h-5" />}
             {saving ? "Deploying Configuration..." : "Save & Restart Agent"}
           </button>
        )}
      </div>
    </motion.div>
  );
}
