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
  const [activeTab, setActiveTab] = useState<"ai" | "openclaw" | "channels">("openclaw");
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

  const statusColor = gwStatus === "running" ? "text-green-400" : gwStatus === "starting" ? "text-yellow-400" : "text-red-400";
  const statusDot = gwStatus === "running" ? "bg-green-400" : gwStatus === "starting" ? "bg-yellow-400 animate-pulse" : "bg-red-400";

  return (
    <motion.div
      initial={{ x: "100%" }}
      animate={{ x: 0 }}
      exit={{ x: "100%" }}
      transition={{ type: "spring", damping: 25, stiffness: 200 }}
      className="fixed top-0 right-0 bottom-0 w-[460px] bg-background/95 backdrop-blur-xl border-l border-border z-[101] shadow-2xl flex flex-col"
    >
      {/* Header */}
      <div className="p-4 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-primary/10">
            <Cpu className="w-5 h-5 text-primary" />
          </div>
          <h2 className="text-lg font-bold text-foreground">Settings</h2>
        </div>
        <button onClick={onClose} className="p-2 hover:bg-secondary rounded-xl transition-colors">
          <X className="w-5 h-5 text-muted-foreground" />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border">
        {[
          { id: "openclaw" as const, label: "Nexus", icon: Globe },
          { id: "channels" as const, label: "Channels", icon: MessageSquare },
          { id: "ai" as const, label: "AI Config", icon: Key },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "flex-1 py-3 text-xs font-bold uppercase tracking-wider transition-all border-b-2",
              activeTab === tab.id
                ? "border-primary text-primary bg-primary/5"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex-1 flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-5 space-y-5 custom-scrollbar">

          {/* ─── OpenClaw Tab ─── */}
          {activeTab === "openclaw" && (
            <>
              {/* Gateway Status Card */}
              <div className="p-4 rounded-2xl bg-secondary/30 border border-border/50 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={cn("w-2.5 h-2.5 rounded-full", statusDot)} />
                    <span className={cn("text-sm font-bold", statusColor)}>
                      Gateway {gwStatus === "running" ? "Running" : gwStatus === "starting" ? "Starting..." : "Stopped"}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={gwStatus === "running" ? handleStopGateway : handleStartGateway}
                      className="p-1.5 rounded-lg bg-background border border-border hover:bg-secondary transition-colors"
                    >
                      {gwStatus === "running" ? <Square className="w-3 h-3 fill-red-400 text-red-400" /> : <Play className="w-3 h-3 fill-green-400 text-green-400" />}
                    </button>
                    <span className="text-xs text-muted-foreground font-mono">:{gwPort}</span>
                  </div>
                </div>

                {gwModel && (
                  <div className="text-xs text-muted-foreground">
                    Model: <span className="text-foreground font-mono">{gwModel}</span>
                  </div>
                )}

                <p className="text-[10px] text-muted-foreground/70 italic">
                  Auto-managed — gateway starts automatically with the application
                </p>
              </div>

              {/* Gateway Logs */}
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-xs font-bold text-muted-foreground uppercase tracking-widest">
                  <Terminal className="w-3.5 h-3.5" /> Gateway Log
                </div>
                <div className="bg-black/40 rounded-xl border border-border/30 p-3 max-h-[200px] overflow-y-auto font-mono text-[10px] text-green-300/80 custom-scrollbar">
                  {gwLogs.length === 0 ? (
                    <span className="text-muted-foreground">No logs yet — start the gateway to see output</span>
                  ) : (
                    gwLogs.map((line, i) => (
                      <div key={i} className="leading-relaxed">{line}</div>
                    ))
                  )}
                </div>
              </div>
            </>
          )}

          {/* ─── Channels Tab ─── */}
          {activeTab === "channels" && (
            <>
              {/* Active Channels */}
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-xs font-bold text-muted-foreground uppercase tracking-widest">
                  <Wifi className="w-3.5 h-3.5" /> Channel Status
                </div>
                <div className="p-4 rounded-2xl bg-secondary/30 border border-border/50 space-y-4">
                  {["whatsapp", "telegram", "slack"].map((name) => {
                    const cfg = gwChannels[name] || {};
                    const isPaired = cfg.paired || cfg.has_token;
                    return (
                      <div key={name} className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-lg bg-background border border-border flex items-center justify-center text-lg">
                            {name === "whatsapp" ? "📱" : name === "telegram" ? "✈️" : "💬"}
                          </div>
                          <div className="flex flex-col">
                            <span className="text-sm font-bold text-foreground capitalize">{name}</span>
                            <span className="text-[10px] text-muted-foreground">
                              {cfg.enabled ? (isPaired ? "Connected & Ready" : "Waiting for Pairing") : "Disabled"}
                            </span>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className={cn(
                            "w-2 h-2 rounded-full",
                            cfg.enabled && isPaired ? "bg-green-400" : cfg.enabled ? "bg-yellow-400 shadow-[0_0_8px_oklch(0.7_0.2_100/0.4)]" : "bg-muted-foreground/30"
                          )} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Bot Tokens (Telegram/Slack) */}
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-xs font-bold text-muted-foreground uppercase tracking-widest">
                  <Key className="w-3.5 h-3.5" /> Bot Configuration
                </div>
                <div className="p-4 rounded-2xl bg-secondary/30 border border-border/50 space-y-4">
                  <div className="space-y-1.5">
                    <label className="text-[10px] text-muted-foreground uppercase font-bold tracking-tight">Telegram Bot Token</label>
                    <input
                      type="password"
                      value={telegramToken}
                      onChange={(e) => setTelegramToken(e.target.value)}
                      placeholder="Paste your Telegram bot token..."
                      className="w-full bg-background border border-border rounded-xl p-2.5 text-sm text-foreground placeholder:text-muted-foreground/40 outline-none"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[10px] text-muted-foreground uppercase font-bold tracking-tight">Slack Bot User Token (xoxb-...)</label>
                    <input
                      type="password"
                      value={slackToken}
                      onChange={(e) => setSlackToken(e.target.value)}
                      placeholder="Paste your Slack bot token..."
                      className="w-full bg-background border border-border rounded-xl p-2.5 text-sm text-foreground placeholder:text-muted-foreground/40 outline-none"
                    />
                  </div>
                  <button
                    onClick={handleSaveChannelConfig}
                    className="w-full py-2.5 rounded-xl bg-primary/10 text-primary border border-primary/20 hover:bg-primary/20 transition-all font-bold text-[10px] uppercase"
                  >
                    Save Bot Tokens
                  </button>
                </div>
              </div>

              {/* WhatsApp Pairing */}
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-xs font-bold text-muted-foreground uppercase tracking-widest">
                  <QrCode className="w-3.5 h-3.5" /> WhatsApp Pairing
                </div>
                <div className="p-4 rounded-2xl bg-secondary/30 border border-border/50 space-y-3">
                  <button
                    onClick={handlePairChannel}
                    disabled={isPairing || gwStatus !== "running"}
                    className={cn(
                      "w-full py-2.5 rounded-xl font-bold text-xs flex items-center justify-center gap-2 transition-all",
                      gwStatus !== "running"
                        ? "bg-secondary text-muted-foreground cursor-not-allowed"
                        : isPairing
                          ? "bg-primary/50 cursor-not-allowed"
                          : "bg-primary hover:bg-primary/90 text-primary-foreground shadow-lg shadow-primary/20"
                    )}
                  >
                    {isPairing ? (
                      <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Starting Pairing...</>
                    ) : (
                      <><QrCode className="w-3.5 h-3.5" /> {qrData ? "Refresh QR Code" : "Generate WhatsApp QR"}</>
                    )}
                  </button>

                  {/* Logout Button */}
                  {gwChannels?.whatsapp?.paired && !isPairing && (
                    <button
                      onClick={handleLogoutChannel}
                      className="w-full py-2 px-3 rounded-xl text-[10px] font-bold uppercase tracking-wider text-red-400 hover:bg-red-400/10 border border-red-400/20 transition-all flex items-center justify-center gap-2 mt-2"
                    >
                      <LogOut className="w-3 h-3" /> Logout / Change Number
                    </button>
                  )}

                  {/* QR Code Display */}
                  {qrData && !isPairing && (
                    <motion.div
                      initial={{ opacity: 0, scale: 0.9 }}
                      animate={{ opacity: 1, scale: 1 }}
                      className="mt-4 p-4 rounded-2xl bg-white border border-border/50 flex flex-col items-center gap-3"
                    >
                      <p className="text-xs font-bold text-gray-800 uppercase tracking-widest">Scan with WhatsApp</p>
                      <img src={qrData} alt="QR Code" className="w-48 h-48 rounded-lg" />
                      <p className="text-[10px] text-gray-500">Open WhatsApp → Linked Devices → Scan</p>
                    </motion.div>
                  )}
                </div>
              </div>
              {/* Pairing Output */}
              {pairingOutput && (
                <div className="bg-black/40 rounded-xl border border-border/30 p-3 max-h-[150px] overflow-y-auto font-mono text-[10px] text-blue-300/80">
                  {pairingOutput}
                </div>
              )}
            </>
          )}

          {/* ─── AI Config Tab ─── */}
          {activeTab === "ai" && (
            <div className="space-y-4">
              <div className="space-y-3 p-4 rounded-2xl bg-secondary/30 border border-border/50">
                <div>
                  <label className="text-xs text-muted-foreground mb-1.5 block">Provider</label>
                  <select
                    value={aiProvider}
                    onChange={(e) => {
                      setAiProvider(e.target.value);
                      setAiModel(modelOptions[e.target.value]?.[0] || "");
                    }}
                    className="w-full bg-background border border-border rounded-xl p-2.5 text-sm text-foreground outline-none"
                  >
                    <option value="gemini">Google Gemini</option>
                    <option value="openrouter">OpenRouter</option>
                    <option value="openai">OpenAI</option>
                    <option value="groq">Groq</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs text-muted-foreground mb-1.5 block">Model</label>
                  <select
                    value={aiModel}
                    onChange={(e) => setAiModel(e.target.value)}
                    className="w-full bg-background border border-border rounded-xl p-2.5 text-sm text-foreground outline-none"
                  >
                    {(modelOptions[aiProvider] || []).map((m) => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-muted-foreground mb-1.5 block">API Key</label>
                  <input
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="Paste your API key..."
                    className="w-full bg-background border border-border rounded-xl p-2.5 text-sm text-foreground placeholder:text-muted-foreground/40 outline-none"
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="p-4 border-t border-border space-y-2">
        {message && (
          <motion.p
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            className={cn(
              "text-xs text-center font-medium",
              message.startsWith("✅") ? "text-green-400" : message.startsWith("❌") ? "text-red-400" : "text-blue-400"
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
              "w-full py-3 rounded-2xl font-bold text-sm flex items-center justify-center gap-2 transition-all",
              saving
                ? "bg-primary/50 cursor-not-allowed"
                : "bg-primary hover:bg-primary/90 shadow-[0_8px_20px_-5px_oklch(0.68_0.28_280/0.4)] hover:-translate-y-0.5 active:translate-y-0"
            )}
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            {saving ? "Saving..." : "Save & Restart Agent"}
          </button>
        )}
      </div>
    </motion.div>
  );
}
