"use client";

import { useState, useEffect, useRef } from "react";

/* ══════════════════════════════════════════════
   TAURI WINDOW SIZING (Dynamic OS Widget)
══════════════════════════════════════════════ */
async function syncWindowSize(mode: "pet" | "panel" | "fs") {
    try {
        if (typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__) {
            const { getCurrentWindow, LogicalSize } = await import("@tauri-apps/api/window");
            const win = getCurrentWindow();
            if (mode === "fs") {
                await win.setFullscreen(true);
            } else if (mode === "panel") {
                await win.setFullscreen(false);
                await win.setSize(new LogicalSize(440, 450));
            } else {
                await win.setFullscreen(false);
                await win.setSize(new LogicalSize(100, 100));
            }
        }
    } catch (e) {
        console.error("Window resize failed:", e);
    }
}

async function triggerDrag() {
    try {
        if (typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__) {
            const { getCurrentWindow } = await import("@tauri-apps/api/window");
            await getCurrentWindow().startDragging();
        }
    } catch (e) {
        console.error("Drag failed:", e);
    }
}

/* ══════════════════════════════════════════════
   PET SVG
══════════════════════════════════════════════ */
function PetSvg({ id = "" }: { id?: string }) {
    // Uses data-tauri-drag-region so clicking any part of the SVG drags the actual OS window!
    return (
        <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" style={{ width: "100%", height: "100%" }} data-tauri-drag-region="true">
            <defs data-tauri-drag-region="true">
                <radialGradient id={`bg${id}`} cx="40%" cy="35%" r="60%">
                    <stop offset="0%" stopColor="#1a8fff" />
                    <stop offset="100%" stopColor="#5b0fff" />
                </radialGradient>
                <filter id={`gw${id}`}>
                    <feGaussianBlur stdDeviation="2.5" result="blur" />
                    <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
                </filter>
            </defs>
            <ellipse cx="50" cy="72" rx="30" ry="8" fill="rgba(0,102,255,0.3)" data-tauri-drag-region="true" />
            <path d="M66 65 Q80 55 78 45 Q76 38 70 42 Q74 48 68 58 Z" fill="#1a6fff" opacity=".8" data-tauri-drag-region="true" />
            <ellipse cx="50" cy="54" rx="28" ry="26" fill={`url(#bg${id})`} filter={`url(#gw${id})`} data-tauri-drag-region="true" />
            <ellipse cx="50" cy="60" rx="14" ry="11" fill="rgba(255,255,255,0.12)" data-tauri-drag-region="true" />
            <path d="M26 40 Q20 22 30 20 Q36 24 34 36 Z" fill="#1a6fff" data-tauri-drag-region="true" />
            <path d="M27 38 Q23 26 30 24 Q34 27 32 36 Z" fill="rgba(0,245,255,0.4)" data-tauri-drag-region="true" />
            <path d="M74 40 Q80 22 70 20 Q64 24 66 36 Z" fill="#1a6fff" data-tauri-drag-region="true" />
            <path d="M73 38 Q77 26 70 24 Q66 27 68 36 Z" fill="rgba(0,245,255,0.4)" data-tauri-drag-region="true" />
            <circle cx="50" cy="40" r="22" fill={`url(#bg${id})`} data-tauri-drag-region="true" />
            <ellipse cx="50" cy="40" rx="16" ry="12" fill="rgba(0,0,0,0.55)" stroke="rgba(0,245,255,0.3)" strokeWidth="1" data-tauri-drag-region="true" />
            <circle cx="43" cy="39" r="3.5" fill="#00f5ff" data-tauri-drag-region="true" /><circle cx="43" cy="39" r="2" fill="white" data-tauri-drag-region="true" />
            <circle cx="57" cy="39" r="3.5" fill="#00f5ff" data-tauri-drag-region="true" /><circle cx="57" cy="39" r="2" fill="white" data-tauri-drag-region="true" />
            <ellipse cx="50" cy="44" rx="2" ry="1.2" fill="rgba(0,245,255,0.7)" data-tauri-drag-region="true" />
            <path d="M45 47 Q50 51 55 47" stroke="rgba(0,245,255,0.6)" strokeWidth="1.2" fill="none" strokeLinecap="round" data-tauri-drag-region="true" />
            <circle cx="50" cy="56" r="2" fill="#00f5ff" opacity=".8" data-tauri-drag-region="true" />
            <ellipse cx="30" cy="72" rx="7" ry="5" fill="#1a6fff" opacity=".9" data-tauri-drag-region="true" />
            <ellipse cx="70" cy="72" rx="7" ry="5" fill="#1a6fff" opacity=".9" data-tauri-drag-region="true" />
            <line x1="50" y1="18" x2="50" y2="10" stroke="rgba(0,245,255,0.7)" strokeWidth="1.5" data-tauri-drag-region="true" />
            <circle cx="50" cy="9" r="2.5" fill="#00f5ff" data-tauri-drag-region="true">
                <animate attributeName="r" values="2.5;3.5;2.5" dur="1.5s" repeatCount="indefinite" />
            </circle>
        </svg>
    );
}

function getReply(text: string): string {
    const t = text.toLowerCase();
    if (t.includes("hello") || t.includes("hi")) return "Hello! Great to see you! 👋";
    if (t.includes("help")) return "Of course! I'm here to help. 🤖";
    if (t.includes("time")) return `Current time: ${new Date().toLocaleTimeString()}`;
    if (t.includes("date")) return `Today is ${new Date().toLocaleDateString()}`;
    if (t.includes("name")) return "I'm Nexus, your virtual assistant! 🌟";
    if (t.includes("boost")) return "Performance boost applied! 🚀";
    if (t.includes("scan")) return "Scanning… all clear! ✅";
    return ["Got it! Let me check that…", "Sure, one moment!", "On it! ⚡"][Math.floor(Math.random() * 3)];
}

const C = { cyan: "#00f5ff", blue: "#0066ff", purple: "#7b2fff", panel: "rgba(6,12,28,0.95)", glass: "rgba(0,245,255,0.06)", border: "rgba(0,245,255,0.18)", text: "#c8e8ff", dim: "rgba(200,232,255,0.45)" };

/* ══════════════════════════════════════════════
   MAIN COMPONENT
══════════════════════════════════════════════ */
interface Props { onSendToAgent?: (input: string) => void; }

export default function AriaAssistant({ onSendToAgent }: Props) {
    const [mounted, setMounted] = useState(false);
    const [viewMode, setViewMode] = useState<"pet" | "panel" | "fs">("pet");
    const [bubble, setBubble] = useState("Hey! I'm <strong style='color:#00f5ff'>Nexus</strong>. How can I help?");
    const [cpu, setCpu] = useState(35);
    const [ram, setRam] = useState(52);
    const [timeStr, setTimeStr] = useState("--");
    const [bat, setBat] = useState("~80%");
    const [batPct, setBatPct] = useState(80);
    const [cpuDash, setCpuDash] = useState("0 100");
    const [ramDash, setRamDash] = useState("0 100");
    const [msgs, setMsgs] = useState<{ text: string; who: "n" | "u" }[]>([
        { text: "Hello! I'm Nexus, your AI assistant. Ready to help! 🚀", who: "n" },
    ]);
    const [mood, setMood] = useState("ONLINE · READY");
    const [online, setOnline] = useState(true);

    const cpuR = useRef(35);
    const ramR = useRef(52);
    const miniIn = useRef<HTMLInputElement>(null);
    const fsIn = useRef<HTMLInputElement>(null);
    const fsEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => { setMounted(true); }, []);

    // Sync Window Size whenever ViewMode changes!
    useEffect(() => {
        syncWindowSize(viewMode);
    }, [viewMode]);

    /* Stats Loop */
    useEffect(() => {
        const iv = setInterval(() => {
            cpuR.current = Math.max(5, Math.min(95, cpuR.current + (Math.random() * 10 - 5)));
            ramR.current = Math.max(20, Math.min(90, ramR.current + (Math.random() * 4 - 2)));
            const c = Math.round(cpuR.current), r = Math.round(ramR.current);
            setCpu(c); setRam(r);
            const circ = 2 * Math.PI * 15.9;
            setCpuDash(`${(c / 100 * circ).toFixed(1)} ${circ}`);
            setRamDash(`${(r / 100 * circ).toFixed(1)} ${circ}`);
            setTimeStr(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
            setOnline(navigator.onLine);
            if ((navigator as any).getBattery) {
                (navigator as any).getBattery().then((b: any) => {
                    const p = Math.round(b.level * 100);
                    setBat((b.charging ? "⚡" : "🔋") + p + "%");
                    setBatPct(p);
                });
            }
        }, 2000);
        return () => clearInterval(iv);
    }, []);

    /* Scroll chat */
    useEffect(() => { fsEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

    /* Chat Send */
    const miniSend = () => {
        const v = miniIn.current?.value.trim(); if (!v) return;
        miniIn.current!.value = "";
        setBubble(`<strong style='color:#00f5ff'>You:</strong> ${v}<br/><br/>${getReply(v)}`);
        onSendToAgent?.(v);
    };

    const fsSend = () => {
        const v = fsIn.current?.value.trim(); if (!v) return;
        fsIn.current!.value = "";
        setMsgs(p => [...p, { text: v, who: "u" }]);
        onSendToAgent?.(v);
        setTimeout(() => setMsgs(p => [...p, { text: getReply(v), who: "n" }]), 600);
    };

    const say = (t: string) => setMsgs(p => [...p, { text: t, who: "n" }]);

    if (!mounted) return null;

    return (
        <>
            <style>{`
        @keyframes nexusFloat { 0%,100%{transform:translateY(0) rotate(-1deg)} 50%{transform:translateY(-8px) rotate(1deg)} }
        @keyframes nexusStatus{ 0%,100%{opacity:1;box-shadow:0 0 8px #00ff88} 50%{opacity:.4} }
        @keyframes nexusRing  { 0%{transform:translate(-50%,-55%) scale(.6);opacity:.6} 100%{transform:translate(-50%,-55%) scale(1.6);opacity:0} }
        /* Hide scrollbars */
        ::-webkit-scrollbar { width: 0px; background: transparent; }
      `}</style>

            {/* OS Widget Root container (matches window bounds exactly) */}
            <div style={{ position: "relative", width: "100%", height: "100%", fontFamily: "var(--font-outfit, sans-serif)", overflow: "hidden" }}>

                {/* ── FLOATING PET (Top Left of OS window) ───────────────────────────── */}
                {viewMode !== "fs" && (
                    <div
                        onPointerDown={triggerDrag}
                        onClick={() => setViewMode(viewMode === "pet" ? "panel" : "pet")}
                        style={{
                            position: "absolute",
                            left: 0, top: 0,
                            width: 100, height: 100,
                            cursor: "grab",
                            filter: "drop-shadow(0 0 16px rgba(0,245,255,0.6))",
                            animation: "nexusFloat 3.5s ease-in-out infinite",
                            zIndex: 10
                        }}
                    >
                        <PetSvg id="sm" />
                    </div>
                )}

                {/* ── MINI PANEL (Appears to the right of the pet) ─────────────────── */}
                <div style={{
                    position: "absolute",
                    left: viewMode === "panel" ? 110 : -400, // Slide in from behind pet 
                    top: 0,
                    width: 310,
                    height: 420,
                    background: C.panel, border: `1px solid ${C.border}`,
                    borderRadius: "16px",
                    backdropFilter: "blur(24px)",
                    boxShadow: `-8px 0 48px rgba(0,102,255,0.3)`,
                    transition: "left .4s cubic-bezier(.34,1.56,.64,1)",
                    overflow: "hidden",
                    display: "flex", flexDirection: "column"
                }}>
                    {/* Panel Header */}
                    <div style={{
                        display: "flex", alignItems: "center", justifyItems: "center", justifyContent: "space-between",
                        padding: "14px 16px", borderBottom: `1px solid ${C.border}`,
                        background: "linear-gradient(90deg,rgba(0,102,255,0.15),rgba(0,245,255,0.05))",
                        flexShrink: 0
                    }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, color: C.cyan, fontWeight: 700, fontSize: "1rem", letterSpacing: ".12em" }}>
                            <div style={{ width: 7, height: 7, borderRadius: "50%", background: "#00ff88", boxShadow: "0 0 8px #00ff88", animation: "nexusStatus 2s ease-in-out infinite" }} />
                            NEXUS
                        </div>
                        <div style={{ display: "flex", gap: 6 }}>
                            <button onClick={async () => {
                                if (typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__) {
                                    try {
                                        const { Window } = await import("@tauri-apps/api/window");
                                        const overlayWindow = await Window.getByLabel("overlay");
                                        const mainWindow = await Window.getByLabel("main");
                                        if (overlayWindow && mainWindow) {
                                            await mainWindow.show();
                                            await mainWindow.setFocus();
                                            await overlayWindow.hide();
                                        }
                                    } catch (e) {
                                        console.error("Failed to restore main mode", e);
                                    }
                                }
                                setViewMode("pet");
                            }} style={{ width: 28, height: 28, borderRadius: 8, border: `1px solid ${C.border}`, background: C.glass, color: C.dim, cursor: "pointer", fontSize: 13 }}>⛶</button>
                            <button onClick={() => setViewMode("pet")} style={{ width: 28, height: 28, borderRadius: 8, border: `1px solid ${C.border}`, background: C.glass, color: C.dim, cursor: "pointer", fontSize: 13 }}>✕</button>
                        </div>
                    </div>

                    {/* Panel Form / Stats Body */}
                    <div style={{ padding: "12px 16px 16px", flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 12 }}>

                        {/* Context Bubble */}
                        <div style={{ display: "flex", gap: 10 }}>
                            <div style={{ width: 32, height: 32, flexShrink: 0, borderRadius: "50%", background: `linear-gradient(135deg,${C.blue},${C.purple})`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14 }}>🤖</div>
                            <div style={{ background: C.glass, border: `1px solid ${C.border}`, borderRadius: "4px 12px 12px 12px", padding: "8px 12px", fontSize: ".8rem", lineHeight: 1.55, color: C.text, flex: 1 }} dangerouslySetInnerHTML={{ __html: bubble }} />
                        </div>

                        {/* Live Stats */}
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                            {[
                                { label: "CPU", val: cpu + "%", pct: cpu },
                                { label: "RAM", val: ram + "%", pct: ram },
                                { label: "Time", val: timeStr, pct: 100 },
                                { label: "Battery", val: bat, pct: batPct },
                            ].map((s, i) => (
                                <div key={i} style={{ background: C.glass, border: `1px solid ${C.border}`, borderRadius: 10, padding: "8px 10px" }}>
                                    <div style={{ fontSize: ".65rem", letterSpacing: ".12em", textTransform: "uppercase", color: C.dim, marginBottom: 3 }}>{s.label}</div>
                                    <div style={{ fontWeight: 700, fontSize: "1.05rem", color: C.cyan }}>{s.val}</div>
                                    <div style={{ marginTop: 4, height: 3, background: "rgba(0,245,255,0.1)", borderRadius: 2, overflow: "hidden" }}>
                                        <div style={{ height: "100%", width: `${s.pct}%`, background: `linear-gradient(90deg,${C.blue},${C.cyan})`, borderRadius: 2, transition: "width 1s" }} />
                                    </div>
                                </div>
                            ))}
                        </div>

                        {/* Quick Actions Grid */}
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
                            {[
                                { icon: "⚙️", label: "Settings", msg: "Settings opened!" },
                                { icon: "🔍", label: "Scan", msg: "Scanning system…" },
                                { icon: "⚡", label: "Boost", msg: "Boosting performance!" },
                                { icon: "🛡️", label: "Status", msg: "All systems normal." },
                            ].map((b, i) => (
                                <button key={i} onClick={() => setBubble(b.msg)} style={{ padding: "6px 4px", borderRadius: 8, border: `1px solid ${C.border}`, background: C.glass, color: C.text, cursor: "pointer", fontSize: ".75rem", fontWeight: 600, textAlign: "center" as const }}>
                                    <div style={{ fontSize: "1rem", marginBottom: 2 }}>{b.icon}</div>{b.label}
                                </button>
                            ))}
                        </div>

                        {/* Ask / Chat input pinned to bottom natively */}
                        <div style={{ display: "flex", gap: 6, marginTop: "auto" }}>
                            <input ref={miniIn} placeholder="Ask Nexus…" onKeyDown={e => { if (e.key === "Enter") miniSend(); }} style={{ flex: 1, background: C.glass, border: `1px solid ${C.border}`, borderRadius: 10, padding: "7px 12px", color: C.text, fontSize: ".8rem", outline: "none", fontFamily: "var(--font-outfit, sans-serif)", minWidth: 0 }} />
                            <button onClick={miniSend} style={{ width: 34, height: 34, borderRadius: 10, border: `1px solid ${C.border}`, background: `linear-gradient(135deg,${C.blue},${C.purple})`, color: "#fff", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>➤</button>
                        </div>

                    </div>
                </div>

                {/* ── FULLSCREEN OVERLAY ──────────────────────── */}
                {viewMode === "fs" && (
                    <div style={{ position: "fixed", inset: 0, zIndex: 2147483647, background: "rgba(4,8,20,0.97)", backdropFilter: "blur(32px)", display: "flex", flexDirection: "column", fontFamily: "var(--font-outfit,sans-serif)" }}>
                        {/* FS Header */}
                        <div onPointerDown={triggerDrag} style={{ cursor: "grab", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "18px 28px", borderBottom: `1px solid ${C.border}`, background: "linear-gradient(90deg,rgba(0,102,255,0.12),transparent)", flexShrink: 0 }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                                <div style={{ width: 42, height: 42, background: `linear-gradient(135deg,${C.blue},${C.purple})`, borderRadius: 12, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22 }}>🤖</div>
                                <div>
                                    <div style={{ fontWeight: 700, fontSize: "1.5rem", letterSpacing: ".15em", color: C.cyan }}>NEXUS</div>
                                    <div style={{ fontSize: ".68rem", letterSpacing: ".2em", color: C.dim, textTransform: "uppercase" as const }}>Virtual Assistant v2.0</div>
                                </div>
                            </div>
                            <button onClick={() => setViewMode("pet")} style={{ width: 40, height: 40, borderRadius: 10, border: `1px solid ${C.border}`, background: C.glass, color: C.dim, cursor: "pointer", fontSize: 18, display: "flex", alignItems: "center", justifyContent: "center" }}>✕</button>
                        </div>

                        {/* FS Body */}
                        <div style={{ flex: 1, display: "grid", gridTemplateColumns: "280px 1fr 280px", gridTemplateRows: "1fr 1fr", gap: 1, background: C.border, overflow: "hidden" }}>
                            {/* LEFT — Chat */}
                            <div style={{ gridRow: "1/3", gridColumn: 1, background: "#060a14", padding: 20, display: "flex", flexDirection: "column" }}>
                                <div style={{ fontSize: ".82rem", fontWeight: 600, letterSpacing: ".15em", color: C.dim, textTransform: "uppercase" as const, marginBottom: 12 }}>💬 Chat with Nexus</div>
                                <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 10 }}>
                                    {msgs.map((m, i) => (
                                        <div key={i} style={{ padding: "9px 13px", borderRadius: m.who === "n" ? "4px 12px 12px 12px" : "12px 4px 12px 12px", fontSize: ".8rem", lineHeight: 1.55, background: m.who === "n" ? "rgba(0,102,255,0.12)" : "rgba(0,245,255,0.08)", border: `1px solid ${m.who === "n" ? "rgba(0,102,255,0.25)" : C.border}`, color: m.who === "n" ? C.text : C.cyan, alignSelf: m.who === "n" ? "flex-start" : "flex-end", maxWidth: "90%" }}>{m.text}</div>
                                    ))}
                                    <div ref={fsEndRef} />
                                </div>
                                <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
                                    <input ref={fsIn} placeholder="Type a message to Nexus…" onKeyDown={e => { if (e.key === "Enter") fsSend(); }} style={{ flex: 1, background: C.glass, border: `1px solid ${C.border}`, borderRadius: 10, padding: "9px 13px", color: C.text, fontSize: ".8rem", outline: "none", fontFamily: "inherit" }} />
                                    <button onClick={fsSend} style={{ padding: "0 14px", borderRadius: 10, border: "none", background: `linear-gradient(135deg,${C.blue},${C.purple})`, color: "#fff", cursor: "pointer", fontWeight: 700, fontSize: ".82rem" }}>SEND</button>
                                </div>
                            </div>

                            {/* CENTER — Large Pet */}
                            <div style={{ gridRow: "1/3", gridColumn: 2, background: "#060a14", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", position: "relative" }}>
                                {[0, 1.3, 2.6].map((d, i) => (
                                    <div key={i} style={{ position: "absolute", width: 260, height: 260, top: "50%", left: "50%", transform: "translate(-50%,-55%)", borderRadius: "50%", border: "1px solid rgba(0,245,255,0.12)", animation: `nexusRing 4s ease-out ${d}s infinite` }} />
                                ))}
                                <div style={{ width: 160, height: 160, filter: "drop-shadow(0 0 32px rgba(0,245,255,0.6))", animation: "nexusFloat 3.5s ease-in-out infinite", marginBottom: 20 }}><PetSvg id="lg" /></div>
                                <div style={{ fontWeight: 700, fontSize: "1.8rem", letterSpacing: ".2em", color: C.cyan, textShadow: "0 0 24px rgba(0,245,255,0.5)" }}>NEXUS</div>
                                <div style={{ fontSize: ".75rem", letterSpacing: ".2em", color: C.dim, marginTop: 4 }}>{mood}</div>
                            </div>

                            {/* RIGHT TOP — Stats */}
                            <div style={{ gridRow: 1, gridColumn: 3, background: "#060a14", padding: 20, display: "flex", flexDirection: "column", gap: 10, overflowY: "auto" }}>
                                <div style={{ fontWeight: 600, fontSize: ".82rem", letterSpacing: ".15em", color: C.dim, textTransform: "uppercase" as const }}>⚡ System Status</div>
                                {[{ label: "CPU Usage", val: cpu, dash: cpuDash, color: C.blue }, { label: "Memory", val: ram, dash: ramDash, color: C.purple }].map((r, i) => (
                                    <div key={i} style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 12px", background: C.glass, border: `1px solid ${C.border}`, borderRadius: 10 }}>
                                        <div style={{ width: 54, height: 54, position: "relative", flexShrink: 0 }}>
                                            <svg viewBox="0 0 36 36" style={{ width: "100%", height: "100%", transform: "rotate(-90deg)" }}>
                                                <circle cx="18" cy="18" r="15.9" fill="none" stroke="rgba(0,245,255,0.1)" strokeWidth="3" />
                                                <circle cx="18" cy="18" r="15.9" fill="none" stroke={r.color} strokeWidth="3" strokeDasharray={r.dash} strokeLinecap="round" />
                                            </svg>
                                            <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: ".75rem", color: C.cyan }}>{r.val}%</div>
                                        </div>
                                        <div style={{ fontSize: ".75rem", letterSpacing: ".1em", color: C.dim, textTransform: "uppercase" as const }}>{r.label}</div>
                                    </div>
                                ))}
                                {[{ icon: "🕐", label: "Time", val: timeStr, color: C.cyan }, { icon: "🔋", label: "Battery", val: bat, color: C.cyan }, { icon: "🌐", label: "Online", val: online ? "Online ✅" : "Offline ❌", color: online ? "#00ff88" : "#ff4466" }].map((s, i) => (
                                    <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "9px 12px", background: C.glass, border: `1px solid ${C.border}`, borderRadius: 10 }}>
                                        <span style={{ fontSize: ".76rem", color: C.dim }}>{s.icon} {s.label}</span>
                                        <span style={{ fontWeight: 700, color: s.color }}>{s.val}</span>
                                    </div>
                                ))}
                                <div style={{ fontWeight: 600, fontSize: ".82rem", letterSpacing: ".15em", color: C.dim, textTransform: "uppercase" as const, marginTop: 2 }}>🎮 Quick Actions</div>
                                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                                    {[{ icon: "🔍", label: "Scan", msg: "Scanning system…" }, { icon: "⚡", label: "Boost", msg: "Boost mode activated!" }, { icon: "🛡️", label: "Security", msg: "All clear." }, { icon: "🧹", label: "Clean", msg: "Optimizing memory…" }, { icon: "📊", label: "Report", msg: "Performance report!" }, { icon: "⚙️", label: "Settings", msg: "Settings coming soon!" }].map((b, i) => (
                                        <button key={i} onClick={() => say(b.msg)} style={{ padding: "10px 6px", borderRadius: 10, border: `1px solid ${C.border}`, background: C.glass, color: C.text, cursor: "pointer", textAlign: "center" as const, fontSize: ".78rem", fontWeight: 600 }}>
                                            <div style={{ fontSize: "1.1rem", marginBottom: 3 }}>{b.icon}</div>{b.label}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* RIGHT BOTTOM — Mood */}
                            <div style={{ gridRow: 2, gridColumn: 3, background: "#060a14", borderTop: `1px solid ${C.border}`, padding: 20, display: "flex", flexDirection: "column", gap: 10 }}>
                                <div style={{ fontWeight: 600, fontSize: ".82rem", letterSpacing: ".15em", color: C.dim, textTransform: "uppercase" as const }}>🎨 Nexus Mood</div>
                                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" as const }}>
                                    {[{ label: "😊 Happy", m: "HAPPY · CHEERFUL", e: "😊" }, { label: "🎯 Focus", m: "FOCUSED · WORKING", e: "🎯" }, { label: "😴 Sleep", m: "SLEEPY · RESTING", e: "😴" }, { label: "⚡ Hype", m: "EXCITED · ENERGIZED", e: "⚡" }].map((b, i) => (
                                        <button key={i} onClick={() => { setMood(b.m); say(`Mood changed to: ${b.m} ${b.e}`); }} style={{ padding: "7px 12px", borderRadius: 8, border: `1px solid ${C.border}`, background: C.glass, color: C.text, cursor: "pointer", fontSize: ".8rem", fontWeight: 600 }}>{b.label}</button>
                                    ))}
                                </div>
                                <div style={{ display: "flex", justifyContent: "space-between", padding: "9px 12px", background: C.glass, border: `1px solid ${C.border}`, borderRadius: 10 }}>
                                    <span style={{ fontSize: ".76rem", color: C.dim }}>Current Mood</span>
                                    <span style={{ fontWeight: 700, fontSize: ".78rem", color: C.cyan }}>{mood}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </>
    );
}
