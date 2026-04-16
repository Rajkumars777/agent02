"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Command, Sparkles, Mic, Loader2, Square, X, Paperclip, FileText, Image as ImageIcon, Globe } from "lucide-react";
import { cn } from "@/lib/utils";
import { useWhisperRecording } from "@/hooks/useWhisperRecording";

interface InputConsoleProps {
  onSend: (message: string, files?: any[], useWeb?: boolean) => void;
  loading: boolean;
  lastCommand?: string;
}

export function InputConsole({ onSend, loading, lastCommand }: InputConsoleProps) {
  const [input, setInput] = useState("");
  const [attachedFiles, setAttachedFiles] = useState<{ name: string; type: string; data: string }[]>([]);
  const [isFocused, setIsFocused] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [useWeb, setUseWeb] = useState(false);
  
  useEffect(() => setMounted(true), []);

  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const appliedCommandRef = useRef("");

  // Base64 helper
  const readFileAsBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    const newFiles = await Promise.all(
      Array.from(files).map(async (file) => ({
        name: file.name,
        type: file.type,
        data: await readFileAsBase64(file),
      }))
    );

    setAttachedFiles((prev) => [...prev, ...newFiles]);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const removeFile = (index: number) => {
    setAttachedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const onWhisperFinal = useCallback(
    (result: { text: string; language?: string }) => {
      setInput((prev) => (prev ? prev + " " + result.text : result.text).trim());
      setTimeout(() => inputRef.current?.focus(), 50);
    },
    []
  );

  const {
    isRecording: isWhisperRecording,
    isBusy: isWhisperBusy,
    error: whisperError,
    state: whisperState,
    isSupported: whisperSupported,
    startRecording: startWhisper,
    stopRecording: stopWhisper,
    reset: resetWhisper,
  } = useWhisperRecording(onWhisperFinal);

  const isWhisperActive = isWhisperRecording || isWhisperBusy;

  useEffect(() => {
    if (lastCommand && lastCommand !== appliedCommandRef.current && !loading) {
      setInput(lastCommand);
      appliedCommandRef.current = lastCommand;
      if (inputRef.current) {
        inputRef.current.focus();
        inputRef.current.style.height = "auto";
        inputRef.current.style.height = `${inputRef.current.scrollHeight}px`;
      }
    }
  }, [lastCommand, loading]);

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
      inputRef.current.style.height = `${inputRef.current.scrollHeight}px`;
    }
  }, [input]);

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    const text = input.trim();
    if ((!text && attachedFiles.length === 0) || loading) return;
    if (isWhisperRecording) stopWhisper();
    onSend(text, attachedFiles, useWeb);
    setInput("");
    setAttachedFiles([]);
    resetWhisper();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const placeholder = !mounted
    ? "Ask NEXUS to do anything..."
    : isWhisperRecording
    ? "🔴 Recording… click stop to finish"
    : isWhisperBusy
    ? "⚙️ Transcribing with Whisper…"
    : "Ask NEXUS or attach files…";

  const borderClass =
    isWhisperRecording
      ? "border-red-500/40 shadow-[0_0_30px_-10px_rgba(239,68,68,0.3)]"
      : isWhisperBusy
      ? "border-indigo-500/40 shadow-[0_0_30px_-10px_rgba(99,102,241,0.3)]"
      : isFocused
      ? "border-primary/40 shadow-[0_0_30px_-10px_oklch(0.68_0.28_280/0.3)] scale-[1.005]"
      : "border-border/60 hover:border-border/80";

  const activeError = whisperError;
  const statusLabel = isWhisperRecording
    ? { text: "Listening — click stop to transcribe", color: "text-red-400" }
    : isWhisperBusy
    ? {
        text: whisperState === "uploading" ? "Uploading audio…" : "Transcribing with Whisper AI…",
        color: "text-indigo-400",
      }
    : null;

  return (
    <div className="w-full max-w-3xl mx-auto relative z-[60] flex flex-col gap-2">
      
      {/* ── File Preview Area ── */}
      <AnimatePresence>
        {attachedFiles.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.95 }}
            className="flex flex-wrap gap-2 px-2 pb-2"
          >
            {attachedFiles.map((file, idx) => (
              <motion.div
                key={idx}
                layout
                className="group relative flex items-center gap-2 px-3 py-1.5 bg-white/5 border border-white/10 rounded-xl backdrop-blur-md"
              >
                {file.type.startsWith("image/") ? (
                  <div className="w-6 h-6 rounded-md overflow-hidden border border-white/10">
                    <img src={file.data} alt={file.name} className="w-full h-full object-cover" />
                  </div>
                ) : (
                  <FileText className="w-4 h-4 text-primary" />
                )}
                <span className="text-[10px] font-bold text-slate-300 max-w-[100px] truncate">
                  {file.name}
                </span>
                <button
                  type="button"
                  onClick={() => removeFile(idx)}
                  className="ml-1 p-0.5 rounded-full hover:bg-red-500/20 text-slate-500 hover:text-red-400 transition-colors"
                >
                  <X className="w-3 h-3" />
                </button>
              </motion.div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      <div className="relative">
        <div
          className={cn(
            "absolute -inset-2 rounded-[1.5rem] blur-2xl opacity-0 transition-all duration-1000 -z-10",
            isWhisperRecording && "opacity-100 bg-red-500/10",
            isWhisperBusy && "opacity-100 bg-indigo-500/10",
            isFocused && !isWhisperActive && "opacity-100 bg-primary/15"
          )}
        />

        <motion.form
          onSubmit={handleSubmit}
          className={cn(
            "relative flex items-center gap-3 p-1.5 rounded-[1.5rem] border transition-all duration-500 glass-pane items-end",
            borderClass
          )}
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.8, type: "spring", stiffness: 100 }}
        >
          {/* Left icon: Upload Button */}
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileSelect}
            className="hidden"
            multiple
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className={cn(
              "ml-2 mb-2 p-2 rounded-full transition-all duration-500 flex-shrink-0 group/clip",
              attachedFiles.length > 0
                ? "bg-primary/20 text-primary scale-110"
                : isFocused
                ? "bg-white/10 text-primary"
                : "bg-secondary text-muted-foreground/60 hover:text-primary hover:bg-primary/10"
            )}
            title="Attach files (Images, Docs)"
          >
            <Paperclip className="w-4 h-4 transition-transform group-hover/clip:rotate-12" />
          </button>

          {/* Textarea */}
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            placeholder={placeholder}
            className={cn(
              "flex-1 bg-transparent border-none outline-none text-base placeholder:text-muted-foreground/40 py-3 text-foreground font-normal tracking-tight focus:ring-0 resize-none",
              "min-h-[44px] max-h-[200px] overflow-y-auto custom-scrollbar",
              isWhisperBusy && "text-muted-foreground/50"
            )}
            rows={1}
            readOnly={isWhisperBusy}
          />

          {/* Right buttons */}
          <div className="mr-1 mb-1.5 flex items-center gap-1.5">

            {/* ── Button: Web Automation Toggle ── */}
            <button
              type="button"
              onClick={() => setUseWeb(!useWeb)}
              title={useWeb ? "Web Automation: Enabled" : "Web Automation: Disabled"}
              className={cn(
                "w-9 h-9 rounded-full flex items-center justify-center transition-all duration-300 relative overflow-hidden flex-shrink-0",
                useWeb
                  ? "bg-blue-500/20 text-blue-400 shadow-lg shadow-blue-500/20 border-blue-500/50"
                  : "bg-secondary hover:bg-blue-500/10 text-muted-foreground hover:text-blue-400"
              )}
            >
              <Globe className={cn("w-4 h-4 transition-transform", useWeb && "animate-pulse")} />
            </button>

            {/* ── Button: Whisper Offline Voice ── */}
            {mounted && whisperSupported && (
              <button
                type="button"
                onClick={() => isWhisperRecording ? stopWhisper() : isWhisperBusy ? resetWhisper() : startWhisper()}
                disabled={false}
                title={
                  isWhisperRecording
                    ? "Stop & transcribe"
                    : isWhisperBusy
                    ? "Cancel transcription"
                    : "Speak using Whisper (Offline)"
                }
                className={cn(
                  "w-9 h-9 rounded-full flex items-center justify-center transition-all duration-300 relative overflow-hidden flex-shrink-0",
                  isWhisperRecording
                    ? "bg-red-500 text-white shadow-lg shadow-red-500/40"
                    : isWhisperBusy
                    ? "bg-indigo-500/20 text-indigo-300 hover:bg-red-500/20 hover:text-red-400 transition-colors"
                    : "bg-secondary hover:bg-red-500/10 text-muted-foreground hover:text-red-400"
                )}
              >
                {isWhisperBusy ? (
                  <X className="w-4 h-4" />
                ) : isWhisperRecording ? (
                  <>
                    <Square className="w-3.5 h-3.5 fill-current" />
                    <span className="absolute inset-0 rounded-full bg-red-400 animate-ping opacity-20 pointer-events-none" />
                  </>
                ) : (
                  <Mic className="w-4 h-4" />
                )}
              </button>
            )}

            {/* ── Send Button ── */}
            <AnimatePresence>
              {(input.trim().length > 0 || attachedFiles.length > 0 || loading) && (
                <motion.button
                  initial={{ scale: 0.8, opacity: 0, x: 10 }}
                  animate={{ scale: 1, opacity: 1, x: 0 }}
                  exit={{ scale: 0.8, opacity: 0, x: 10 }}
                  type="submit"
                  disabled={loading}
                  className="h-9 px-4 rounded-xl bg-primary text-primary-foreground font-bold transition-all shadow-lg hover:shadow-primary/20 hover:-translate-y-0.5 active:translate-y-0 active:scale-95 flex items-center gap-2 group"
                >
                  {loading ? (
                    <Sparkles className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      <span className="text-xs tracking-widest uppercase font-black">Send</span>
                      <Send className="w-3.5 h-3.5 transition-transform duration-300 group-hover:translate-x-1 group-hover:-translate-y-1" />
                    </>
                  )}
                </motion.button>
              )}
            </AnimatePresence>
          </div>
        </motion.form>
      </div>

      {/* ── Status / Error bar ── */}
      <div className="flex items-center justify-between px-2 min-h-[20px]">
        <AnimatePresence mode="wait">
          {activeError ? (
            <motion.span
              key="err"
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="text-[10px] text-red-400 font-medium max-w-[60%]"
            >
              ⚠️ {activeError}
            </motion.span>
          ) : statusLabel ? (
            <motion.span
              key="status"
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className={cn("text-[10px] font-bold uppercase tracking-widest flex items-center gap-1.5", statusLabel.color)}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse inline-block" />
              {statusLabel.text}
            </motion.span>
          ) : (
            <span key="empty" />
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
