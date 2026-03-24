"use client";

import { useState, useCallback, useEffect } from "react";
import { HeroSection } from "@/components/HeroSection";
import { InputConsole } from "@/components/InputConsole";
import { TimelineFeed, Step } from "@/components/TimelineFeed";
import { RecentsHistory } from "@/components/RecentsHistory";
import BrowserViewport from "@/components/BrowserViewport";
import { SettingsPanel } from "@/components/SettingsPanel";

import { chatWithAgent, cancelOperation, generateTaskId, resumeTask, getHistory, getFolders } from "@/lib/api";
import { useWebsocket, WebSocketEvent } from "@/hooks/useWebsocket";
import { motion, AnimatePresence } from "framer-motion";
import { StopCircle, Edit3, RotateCcw, Globe, Sun, Moon, Settings } from "lucide-react";
import { cn } from "@/lib/utils";

export default function Dashboard() {
  const [steps, setSteps] = useState<Step[]>([]);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<string[]>([]);
  const [lastCommand, setLastCommand] = useState<string>("");
  const [cancelled, setCancelled] = useState(false);
  const [isAssistantMode, setIsAssistantMode] = useState(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [isDark, setIsDark] = useState(true);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [folders, setFolders] = useState<any[]>([]);

  // Load history and folders on mount
  useEffect(() => {
    const loadMemory = async () => {
      try {
        const [historyRes, foldersRes] = await Promise.all([getHistory(), getFolders()]);
        if (historyRes.history) setHistory(historyRes.history);
        if (foldersRes.folders) setFolders(foldersRes.folders);
      } catch (err) {
        console.error("Failed to load memory:", err);
      }
    };
    loadMemory();
  }, []);

  // Sync theme with document class
  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [isDark]);

  // Handle real-time events from WebSocket
  const handleWebSocketEvent = useCallback((event: WebSocketEvent) => {
    const { type, data } = event;
    const timestamp = new Date().toLocaleTimeString();
    // Safely coerce unknown event data fields to strings
    const toStr = (v: unknown, fallback = "") =>
      typeof v === "string" ? v : v != null ? String(v) : fallback;

    setSteps(prev => {
      // 1. Map thinking/analysis
      if (type === "Thinking" || type === "NLU_Success") {
        const content = type === "Thinking" ? toStr(data.message) : "NLU Analysis complete.";
        // Avoid duplicate identical thinking blocks
        if (prev.length > 0 && prev[prev.length - 1].content === content) return prev;
        return [...prev, { type: "Reasoning", content, timestamp }];
      }

      // 2. Map Screen Agent actions
      if (type === "AgentStep" || type === "ActionStarted" || type === "ScreenTaskStarted") {
        const content = toStr(data.desc || data.action || data.task, "Executing action...");
        return [...prev, { type: "Action", content, timestamp }];
      }

      // 3. Map Results
      if (type === "ActionResult" || type === "AgentStepDone" || type === "AgentDone") {
        const content = toStr(data.result || data.message, "Action completed.");
        // Update the last "Action" step with result if possible, or add new
        if (prev.length > 0 && prev[prev.length - 1].type === "Action") {
          const last = prev[prev.length - 1];
          return [...prev.slice(0, -1), { ...last, content: `${last.content}\n\n${content}` }];
        }
        return [...prev, { type: "Decision", content, timestamp }];
      }

      // 4. Handle Questions (Interactive)
      if (type === "AgentQuestion" || type === "REQUIRE_HELP") {
        return [...prev, {
          type: "Decision",
          content: toStr(data.prompt || data.question, "Agent requires input."),
          timestamp,
          attachment: { type: "options", data: [{ label: "Reply to Agent", value: "REPLY_TRIGGER" }] }
        }];
      }

      return prev;
    });
  }, []);

  useWebsocket(activeTaskId, handleWebSocketEvent);

  // Handle cancel operation
  const handleCancel = useCallback(async () => {
    setCancelled(true);
    await cancelOperation();
    setLoading(false);
    setActiveTaskId(null);
    setSteps(prev => [...prev, {
      type: "Action",
      content: "⏹️ Operation cancelled by user",
      timestamp: new Date().toLocaleTimeString()
    }]);
  }, []);

  // Handle edit/retry with modification
  const handleEdit = useCallback(() => {
    // This will be handled by InputConsole - we just need to pass lastCommand
    setCancelled(false);
  }, []);

  // Keep track of the latest agent thought process
  const handleSend = async (input: string) => {
    if (!input.trim()) return;

    setLoading(true);
    setCancelled(false);
    setLastCommand("");

    const timestamp = new Date().toLocaleTimeString();
    
    // 1. Add User message to the feed immediately (Persistent history)
    setSteps(prev => [...prev, { type: "User", content: input, timestamp }]);

    // Add to specific history (prevent duplicates at top)
    setHistory(prev => {
      const newHist = [input, ...prev.filter(h => h !== input)];
      return newHist.slice(0, 50); // Keep last 50
    });

    try {
      const taskId = generateTaskId();
      setActiveTaskId(taskId);

      const res = await chatWithAgent(input, taskId);

      if (res.cancelled) {
        if (!cancelled) {
          setSteps(prev => [...prev, {
            type: "Action",
            content: "⏹️ Operation cancelled",
            timestamp: new Date().toLocaleTimeString()
          }]);
        }
      } else if (res.steps && res.steps.length > 0) {
        // Append new steps from the agent response
        setSteps(prev => [...prev, ...res.steps]);
      }
    } catch (e) {
      if (!cancelled) {
        const errorMsg = e instanceof Error ? e.message : String(e);
        setSteps(prev => [...prev, {
          type: "Action",
          content: "❌ Error: " + errorMsg,
          timestamp: new Date().toLocaleTimeString()
        }]);
      }
    } finally {
      setLoading(false);
      setTimeout(() => setActiveTaskId(null), 2000);
      
      // Refresh history from backend to ensure last 10 limit is applied
      try {
        const historyRes = await getHistory();
        if (historyRes.history) setHistory(historyRes.history);
      } catch (err) {
        console.error("Failed to refresh history:", err);
      }
    }
  };

  // Handle clicking options in the timeline (like "Reply to Agent")
  const handleOptionSelect = async (value: string) => {
    if (value === "REPLY_TRIGGER") {
      const reply = window.prompt("Nexus requires additional information to continue:");
      if (reply && activeTaskId) {
        setLoading(true);
        try {
          await resumeTask(activeTaskId, reply);
          // The agent will resume and emit events via WebSocket
        } catch (e) {
          console.error("Resume failed", e);
        } finally {
          setLoading(false);
        }
      }
    } else {
      handleSend(value);
    }
  };



  return (
    <main className="min-h-screen bg-background relative font-sans selection:bg-primary/30 flex flex-col">
      {/* Dynamic Background Elements */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div className="absolute top-[-20%] left-[-10%] w-[60%] h-[60%] bg-primary/10 rounded-full blur-[160px] animate-pulse" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-blue-600/10 rounded-full blur-[140px] animate-pulse delay-1000" />
      </div>

      {/* Floating Controls */}
      <div className="fixed top-8 left-8 right-8 flex justify-between items-center z-[100] pointer-events-none">

        {/* Assistant Mode Button (Left) */}
        <div className="pointer-events-auto">
          <button
            onClick={() => setIsAssistantMode(!isAssistantMode)}
            className={cn(
              "flex items-center gap-2 px-4 py-2 rounded-xl font-bold text-[10px] uppercase tracking-[0.15em] transition-all shadow-xl backdrop-blur-xl border",
              isAssistantMode
                ? "bg-blue-500/20 text-blue-500 dark:text-blue-400 border-blue-500/40 shadow-blue-500/10"
                : "bg-secondary/80 text-muted-foreground/60 border-border/40 hover:bg-secondary hover:border-border/60"
            )}
          >
            <div className={cn("w-1.5 h-1.5 rounded-full", isAssistantMode ? "bg-blue-400 animate-pulse" : "bg-slate-500")} />
            {isAssistantMode ? "Active" : "Assistant"}
          </button>
        </div>

        <div className="flex gap-2.5 pointer-events-auto">
          {/* Settings Button */}
          <button
            onClick={() => setIsSettingsOpen(true)}
            className="p-2.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/5 text-slate-400 transition-all hover:scale-105 shadow-xl backdrop-blur-xl group relative overflow-hidden"
            title="Settings"
          >
            <Settings className="w-4 h-4 text-slate-400 group-hover:text-primary transition-all duration-500" />
          </button>

          {/* Theme Toggle */}
          <button
            onClick={() => setIsDark(!isDark)}
            className="p-2.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/5 text-slate-400 transition-all hover:scale-105 shadow-xl backdrop-blur-xl group relative overflow-hidden"
          >
            <AnimatePresence mode="wait">
              {isDark ? (
                <motion.div
                  key="moon"
                  initial={{ y: 10, opacity: 0 }}
                  animate={{ y: 0, opacity: 1 }}
                  exit={{ y: -10, opacity: 0 }}
                >
                  <Moon className="w-4 h-4 text-blue-400" />
                </motion.div>
              ) : (
                <motion.div
                  key="sun"
                  initial={{ y: 10, opacity: 0 }}
                  animate={{ y: 0, opacity: 1 }}
                  exit={{ y: -10, opacity: 0 }}
                >
                  <Sun className="w-4 h-4 text-amber-400" />
                </motion.div>
              )}
            </AnimatePresence>
          </button>

          <button
            onClick={() => setIsHistoryOpen(true)}
            className="p-2.5 rounded-xl bg-secondary/80 hover:bg-secondary border border-border/40 text-muted-foreground/60 transition-all hover:scale-105 shadow-xl backdrop-blur-xl group"
          >
            <RotateCcw className="w-4 h-4 group-hover:rotate-[-45deg] transition-transform duration-300" />
          </button>
        </div>
      </div>

      {/* Top Section: Hero + Input */}
      <div className={cn(
        "relative w-full max-w-4xl mx-auto transition-all duration-700 ease-in-out z-20",
        steps.length > 0 ? "pt-16 pb-4" : "pt-24 pb-8 flex flex-col items-center"
      )}>
        <AnimatePresence>
          {steps.length === 0 && (
            <motion.div
              initial={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -50, height: 0 }}
              transition={{ duration: 0.5 }}
              className="w-full"
            >
              <HeroSection />
            </motion.div>
          )}
        </AnimatePresence>

        <div className={cn(
          "w-full transition-all duration-500",
          steps.length > 0 ? "fixed bottom-8 left-1/2 -translate-x-1/2 max-w-xl px-4" : "mt-8"
        )}>
          <InputConsole
            onSend={handleSend}
            loading={loading}
            lastCommand={lastCommand}
          />

          {/* Stop/Edit Controls */}
          <AnimatePresence>
            {loading && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 10 }}
                className="flex justify-center gap-4 mt-4"
              >
                <button
                  onClick={handleCancel}
                  className="flex items-center gap-2 px-4 py-2 bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 rounded-full text-red-400 text-xs font-bold uppercase tracking-wider transition-all"
                >
                  <StopCircle className="w-4 h-4" />
                  Cancel
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Main Content Area: Chat Feed */}
      <div className={cn(
        "flex-1 w-full max-w-5xl mx-auto z-10 transition-all duration-700",
        steps.length > 0 ? "opacity-100" : "opacity-0 pointer-events-none"
      )}>
        <div className="w-full h-full overflow-y-auto pb-48 pt-4 custom-scrollbar">
          <TimelineFeed 
            steps={steps} 
            onOptionSelect={handleOptionSelect} 
            onEdit={(content) => {
              setLastCommand(""); // Force re-trigger of useEffect in InputConsole
              setTimeout(() => setLastCommand(content), 10);
            }}
          />
        </div>
      </div>
      {/* History Sidebar Drawer */}
      <AnimatePresence>
        {
          isHistoryOpen && (
            <>
              {/* Backdrop */}
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                onClick={() => setIsHistoryOpen(false)}
                className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[100]"
              />
              {/* Drawer */}
              <motion.div
                initial={{ x: "100%" }}
                animate={{ x: 0 }}
                exit={{ x: "100%" }}
                transition={{ type: "spring", damping: 25, stiffness: 200 }}
                className="fixed top-0 right-0 bottom-0 w-80 bg-background border-l border-border z-[101] shadow-2xl"
              >
                <div className="h-full flex flex-col">
                  {/* Drawer Header */}
                  <div className="p-4 border-b border-border flex items-center justify-between">
                    <h2 className="text-sm font-semibold text-foreground uppercase tracking-wider">History</h2>
                    <button
                      onClick={() => setIsHistoryOpen(false)}
                      className="p-1 hover:bg-secondary rounded-md transition-colors"
                    >
                      <RotateCcw className="w-4 h-4 text-muted-foreground rotate-45" /> {/* Using rotate as close icon substitute for now */}
                    </button>
                  </div>

                  {/* Drawer Content */}
                    <div className="flex-1 overflow-y-auto custom-scrollbar">
                      <RecentsHistory
                        recents={history}
                        folders={folders}
                        onFoldersChange={setFolders}
                        onHistoryChange={setHistory}
                        onSelect={(cmd) => {
                          handleSend(cmd);
                          setIsHistoryOpen(false);
                        }}
                        onEdit={(cmd) => {
                          setLastCommand("");
                          setTimeout(() => setLastCommand(cmd), 10);
                          setIsHistoryOpen(false);
                        }}
                      />
                    </div>
                </div>
              </motion.div>
            </>
          )
        }
      </AnimatePresence >

      {/* Settings Panel Drawer */}
      <AnimatePresence>
        {isSettingsOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsSettingsOpen(false)}
              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[100]"
            />
            <SettingsPanel onClose={() => setIsSettingsOpen(false)} />
          </>
        )}
      </AnimatePresence>

    </main >
  );
}
