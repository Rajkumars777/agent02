"use client";

import { motion, AnimatePresence } from "framer-motion";
import {
  Bot, CheckCircle2, Edit2, Copy, Check, Volume2, Square,
  AlertTriangle, FolderOpen, FileText, ExternalLink, Download, Image as ImageIcon
} from "lucide-react";
import { cn } from "@/lib/utils";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import React, { useState, useEffect, useRef, useCallback } from "react";
import { openPath } from "@/lib/api";
import { useSpeechSynthesis } from "@/hooks/useSpeech";
import { ChartBlock } from "@/components/ChartBlock";

export type Step = {
  type: "Reasoning" | "Decision" | "Action" | "User";
  content: string;
  timestamp: string;
  attachment?: {
    type: "image" | "video" | "audio" | "options" | "web_result";
    url?: string;
    name?: string;
    data?: any;
    screenshot?: string;
  };
  files?: { name: string; type: string; data: string }[];
};

interface TimelineFeedProps {
  steps: Step[];
  onOptionSelect?: (value: string) => void;
  onEdit?: (content: string) => void;
  isLoading?: boolean;
}

// ─── Content Sanitizer ────────────────────────────────────────────────────────

const SENSITIVE_PATTERNS: [RegExp, string][] = [
  [/python\s+script(?:s)?(?:\s+(?:generation|generated|created|wrote|written))?/gi, "automation"],
  [/openclaw\s*(?:gateway|channel|token|api)?/gi, "gateway"],
  [/running\s+the\s+(?:python\s+)?script/gi, "executing task"],
  [/(?:calling|invoking)\s+the\s+(?:python\s+)?script/gi, "processing"],
  [/openclaw/gi, "nexus bridge"],
];

function sanitizeContent(text: string): string {
  if (typeof text !== "string") return text;
  let result = text;
  for (const [pattern, replacement] of SENSITIVE_PATTERNS) {
    result = result.replace(pattern, replacement);
  }
  return result;
}

// ─── Error Detection ──────────────────────────────────────────────────────────

const ERROR_PATTERNS = [
  /\b(?:error|failed|failure|exception|traceback|❌|✗|could not|unable to|not found|denied|rejected|timeout|crashed|fatal)\b/i,
  /^⏹️\s*Operation\s+cancelled/i,
];

function isErrorContent(content: string): boolean {
  return ERROR_PATTERNS.some((p) => p.test(content));
}

// ─── Best Content Picker ──────────────────────────────────────────────────────
// From all AI steps in a group, pick the richest single content to display.

function pickBestContent(steps: Step[]): { content: string; isError: boolean; isCancelled: boolean } {
  // Prefer Decision > Action > Reasoning, in that priority
  const decision = [...steps].reverse().find((s) => s.type === "Decision");
  const action = [...steps].reverse().find((s) => s.type === "Action");
  const best = decision ?? action ?? steps[steps.length - 1];

  const isError = isErrorContent(best.content);
  const isCancelled = /operation\s+cancelled/i.test(best.content);

  return { content: sanitizeContent(best.content), isError, isCancelled };
}

// ─── File Chip ────────────────────────────────────────────────────────────────

interface ParsedPath {
  fullPath?: string;
  dirPath?: string;
  fileName?: string;
  isAbsolute: boolean;
}

function parsePath(token: string): ParsedPath {
  if (/^[a-zA-Z]:\\/.test(token)) {
    const lastSlash = Math.max(token.lastIndexOf("\\"), token.lastIndexOf("/"));
    if (lastSlash > 2) {
      const dir = token.substring(0, lastSlash + 1);
      const file = token.substring(lastSlash + 1);
      if (file.includes(".")) {
        return { fullPath: token, dirPath: dir, fileName: file, isAbsolute: true };
      }
    }
    return { dirPath: token, isAbsolute: true };
  }
  return { fileName: token, isAbsolute: false };
}

function FileChip({ token }: { token: string }) {
  const parsed = parsePath(token);
  const [folderHover, setFolderHover] = useState(false);
  const [fileHover, setFileHover] = useState(false);

  const openFolder = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    openPath(parsed.dirPath ?? parsed.fullPath ?? token).catch(console.error);
  };

  const openFile = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    openPath(parsed.fullPath ?? token).catch(console.error);
  };

  // Relative filename only
  if (!parsed.isAbsolute && parsed.fileName) {
    return (
      <span
        onClick={openFile}
        onMouseEnter={() => setFileHover(true)}
        onMouseLeave={() => setFileHover(false)}
        className={cn(
          "inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[11px] font-mono font-semibold cursor-pointer transition-all duration-150 border",
          "bg-cyan-500/10 text-cyan-300 border-cyan-500/20",
          fileHover && "bg-cyan-500/20 border-cyan-400/40 scale-105"
        )}
        title={`Click to open ${token}`}
      >
        <FileText className="w-2.5 h-2.5 flex-shrink-0" />
        {parsed.fileName}
        <ExternalLink className="w-2 h-2 flex-shrink-0 opacity-60" />
      </span>
    );
  }

  // Absolute path with folder + filename
  if (parsed.isAbsolute && parsed.fileName && parsed.dirPath) {
    return (
      <span className="inline-flex items-center gap-0 rounded-md overflow-hidden border border-emerald-500/20 font-mono text-[11px] font-semibold bg-emerald-500/5">
        <span
          onClick={openFolder}
          onMouseEnter={() => setFolderHover(true)}
          onMouseLeave={() => setFolderHover(false)}
          className={cn(
            "inline-flex items-center gap-1 px-1.5 py-0.5 cursor-pointer transition-all duration-150 text-emerald-400 border-r border-emerald-500/20",
            folderHover && "bg-emerald-500/20 text-emerald-300"
          )}
          title={`Open folder: ${parsed.dirPath}`}
        >
          <FolderOpen className="w-2.5 h-2.5 flex-shrink-0" />
          <span className="max-w-[160px] truncate">{parsed.dirPath}</span>
        </span>
        <span
          onClick={openFile}
          onMouseEnter={() => setFileHover(true)}
          onMouseLeave={() => setFileHover(false)}
          className={cn(
            "inline-flex items-center gap-1 px-1.5 py-0.5 cursor-pointer transition-all duration-150 text-cyan-300",
            fileHover && "bg-cyan-500/20 text-cyan-200"
          )}
          title={`Open file: ${parsed.fullPath}`}
        >
          <FileText className="w-2.5 h-2.5 flex-shrink-0" />
          {parsed.fileName}
          <ExternalLink className="w-2 h-2 flex-shrink-0 opacity-60" />
        </span>
      </span>
    );
  }

  // Directory only
  return (
    <span
      onClick={openFolder}
      onMouseEnter={() => setFolderHover(true)}
      onMouseLeave={() => setFolderHover(false)}
      className={cn(
        "inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[11px] font-mono font-semibold cursor-pointer transition-all duration-150 border",
        "bg-emerald-500/10 text-emerald-300 border-emerald-500/20",
        folderHover && "bg-emerald-500/20 border-emerald-400/40"
      )}
      title={`Open folder: ${token}`}
    >
      <FolderOpen className="w-2.5 h-2.5 flex-shrink-0" />
      {token}
    </span>
  );
}

// ─── Linkify ──────────────────────────────────────────────────────────────────

function linkifyText(text: string): (string | React.ReactNode)[] {
  if (typeof text !== "string") return [text];
  const combinedRegex =
    /([a-zA-Z]:\\(?:[\w\s.-]+\\)*[\w\s.-]*\.\w+|[a-zA-Z]:\\(?:[\w\s.-]+\\)+|\b[\w.-]+\.(?:pdf|txt|png|jpg|jpeg|docx|xlsx|exe|md|py|js|ts|tsx|json|csv|html|css|mp4|mp3|zip|log)\b)/g;

  const parts: (string | React.ReactNode)[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = combinedRegex.exec(text)) !== null) {
    if (match.index > lastIndex) parts.push(text.slice(lastIndex, match.index));
    parts.push(<FileChip key={`chip-${match.index}`} token={match[0]} />);
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return parts.length > 0 ? parts : [text];
}

const processChildren = (children: any): any =>
  React.Children.map(children, (child) => {
    if (typeof child === "string") return linkifyText(child);
    if (React.isValidElement(child) && (child.props as any).children) {
      return React.cloneElement(child, {
        children: processChildren((child.props as any).children),
      } as any);
    }
    return child;
  });

// ─── TypingDots ───────────────────────────────────────────────────────────────

const STATUS_MESSAGES = ["Thinking", "Planning", "Executing"];

function TypingDots() {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setIndex((prev) => (prev + 1) % STATUS_MESSAGES.length);
    }, 1500);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="flex items-center gap-3 py-1 pl-1">
      <div className="flex items-center gap-1.5">
        {[0, 1, 2].map((i) => (
          <motion.div
            key={i}
            className="w-2 h-2 rounded-full bg-primary/60"
            animate={{ y: [0, -5, 0], opacity: [0.4, 1, 0.4] }}
            transition={{ duration: 0.7, repeat: Infinity, delay: i * 0.18, ease: "easeInOut" }}
          />
        ))}
      </div>
      <AnimatePresence mode="wait">
        <motion.span
          key={index}
          initial={{ opacity: 0, x: -5 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: 5 }}
          transition={{ duration: 0.2 }}
          className="text-[11px] font-bold text-primary/80 uppercase tracking-widest"
        >
          {STATUS_MESSAGES[index]}...
        </motion.span>
      </AnimatePresence>
    </div>
  );
}

// ─── CopyButton ───────────────────────────────────────────────────────────────

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button
      onClick={handleCopy}
      className="transition-all duration-200 p-1.5 rounded-lg hover:bg-white/10 text-muted-foreground hover:text-foreground"
      title="Copy"
    >
      <AnimatePresence mode="wait">
        {copied ? (
          <motion.div key="check" initial={{ scale: 0.7 }} animate={{ scale: 1 }} exit={{ scale: 0.7 }}>
            <Check className="w-3.5 h-3.5 text-green-400" />
          </motion.div>
        ) : (
          <motion.div key="copy" initial={{ scale: 0.7 }} animate={{ scale: 1 }} exit={{ scale: 0.7 }}>
            <Copy className="w-3.5 h-3.5" />
          </motion.div>
        )}
      </AnimatePresence>
    </button>
  );
}

// ─── DownloadButton ────────────────────────────────────────────────────────────

function DownloadButton({ text, timestamp }: { text: string; timestamp: string }) {
  const handleDownload = (e: React.MouseEvent) => {
    e.stopPropagation();
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const safeTime = timestamp.replace(/[:]/g, "-").replace(/\s/g, "_");
    a.download = `nexus_response_${safeTime}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <button
      onClick={handleDownload}
      className="transition-all duration-200 p-1.5 rounded-lg hover:bg-white/10 text-muted-foreground hover:text-indigo-400"
      title="Download as TXT"
    >
      <Download className="w-3.5 h-3.5" />
    </button>
  );
}

// ─── SpeakButton ─────────────────────────────────────────────────────────────

function SpeakButton({ text }: { text: string }) {
  const { state, speak, stop, isSupported } = useSpeechSynthesis();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted || !isSupported) return null;

  const isSpeaking = state === "speaking" || state === "paused";
  return (
    <button
      onClick={(e) => { e.stopPropagation(); isSpeaking ? stop() : speak(text); }}
      title={isSpeaking ? "Stop" : "Read aloud"}
      className={cn(
        "transition-all duration-200 p-1.5 rounded-lg",
        isSpeaking
          ? "opacity-100 text-indigo-400 hover:text-red-400 hover:bg-red-500/10"
          : "text-muted-foreground hover:text-indigo-400 hover:bg-indigo-500/10"
      )}
    >
      <AnimatePresence mode="wait">
        {isSpeaking ? (
          <motion.div key="stop" initial={{ scale: 0.7 }} animate={{ scale: 1 }} exit={{ scale: 0.7 }}>
            <Square className="w-3.5 h-3.5 fill-current" />
          </motion.div>
        ) : (
          <motion.div key="play" initial={{ scale: 0.7 }} animate={{ scale: 1 }} exit={{ scale: 0.7 }}>
            <Volume2 className="w-3.5 h-3.5" />
          </motion.div>
        )}
      </AnimatePresence>
    </button>
  );
}

// ─── TimelineFeed ─────────────────────────────────────────────────────────────

export function TimelineFeed({ steps, onOptionSelect, onEdit, isLoading }: TimelineFeedProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [steps, isLoading]);

  if (steps.length === 0 && !isLoading) return null;

  // Group consecutive AI steps together under one bubble
  const groups: { type: "User" | "AI"; steps: Step[] }[] = [];
  steps.forEach((step) => {
    if (step.type === "User") {
      groups.push({ type: "User", steps: [step] });
    } else {
      const last = groups[groups.length - 1];
      if (last && last.type === "AI") {
        last.steps.push(step);
      } else {
        groups.push({ type: "AI", steps: [step] });
      }
    }
  });

  return (
    <div className="w-full max-w-3xl mx-auto mt-8 px-4 relative pb-32 flex flex-col gap-5">
      <AnimatePresence mode="popLayout">
        {groups.map((group, groupIdx) => {
          const isUser = group.type === "User";
          const latestStep = group.steps[group.steps.length - 1];
          const isProcessing =
            group.type === "AI" &&
            latestStep.type === "Reasoning" &&
            groupIdx === groups.length - 1;

          // ── User bubble ──────────────────────────────────────────────────
          if (isUser) {
            return (
              <motion.div
                key={groupIdx}
                initial={{ opacity: 0, y: 14, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ duration: 0.35, ease: "easeOut" }}
                className="flex justify-end group"
              >
                <div className="max-w-[75%]">
                  <div className="relative bg-primary text-primary-foreground rounded-2xl rounded-tr-none px-4 py-3 shadow-lg shadow-primary/15">
                    <p className="text-sm leading-relaxed whitespace-pre-wrap">{latestStep.content}</p>
                    
                    {/* User Attached Files */}
                    {latestStep.files && latestStep.files.length > 0 && (
                      <div className="mt-2.5 pt-2.5 border-t border-white/10 flex flex-wrap gap-2">
                        {latestStep.files.map((file, fIdx) => (
                          <div 
                            key={fIdx} 
                            className="flex items-center gap-1.5 px-2 py-1 bg-black/10 rounded-lg border border-white/5 backdrop-blur-sm"
                            title={file.name}
                          >
                            {file.type.startsWith("image/") ? (
                              <ImageIcon className="w-3 h-3 text-white/70" />
                            ) : (
                              <FileText className="w-3 h-3 text-white/70" />
                            )}
                            <span className="text-[10px] font-bold truncate max-w-[140px] opacity-80">{file.name}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Corner nub */}
                    <div className="absolute top-0 right-[-6px] w-0 h-0 border-t-[8px] border-t-primary border-r-[6px] border-r-transparent" />
                  </div>
                  <div className="mt-1 flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity text-[10px] font-mono text-muted-foreground pr-0.5">
                    {onEdit && (
                      <button
                        onClick={() => onEdit(latestStep.content)}
                        className="flex items-center gap-1 hover:text-foreground transition-colors"
                        title="Edit and retry"
                      >
                        <Edit2 className="w-2.5 h-2.5" />
                        Edit
                      </button>
                    )}
                    <span>{latestStep.timestamp}</span>
                  </div>
                </div>
              </motion.div>
            );
          }

          // ── AI bubble ────────────────────────────────────────────────────
          const { content, isError, isCancelled } = pickBestContent(group.steps);
          const hasDecision = group.steps.some((s) => s.type === "Decision");

          const prevUserGroup = groups[groupIdx - 1];
          const queryText = prevUserGroup?.type === "User" ? prevUserGroup.steps[prevUserGroup.steps.length - 1].content : "N/A";
          const cleanBestContent = content.replace(/Forwarding request to OpenClaw Engine\.\.\.\s*/g, "").trim();
          const downloadText = `QUERY:\n${queryText}\n\nRESPONSE:\n${cleanBestContent}`;

          return (
            <motion.div
              key={groupIdx}
              initial={{ opacity: 0, y: 16, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.4, ease: "easeOut" }}
              className="flex justify-start group"
            >
              <div className="max-w-[82%] w-full">
                {/* Sender label */}
                <div className="flex items-center gap-2 mb-1.5 ml-0.5">
                  <div className="w-5 h-5 rounded-full bg-primary/20 border border-primary/30 flex items-center justify-center flex-shrink-0">
                    <Bot className="w-3 h-3 text-primary" />
                  </div>
                  <span className="text-[10px] font-semibold uppercase tracking-widest text-primary/50">Nexus</span>
                  {isError && !isCancelled && (
                    <span className="inline-flex items-center gap-1 text-[10px] font-bold text-red-400 bg-red-500/10 border border-red-500/20 px-2 py-0.5 rounded-full">
                      <AlertTriangle className="w-2.5 h-2.5" />
                      Failed
                    </span>
                  )}
                  {isCancelled && (
                    <span className="inline-flex items-center gap-1 text-[10px] font-bold text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-full">
                      Cancelled
                    </span>
                  )}
                  {!isProcessing && !isError && !isCancelled && hasDecision && (
                    <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full">
                      <CheckCircle2 className="w-2.5 h-2.5" />
                      Done
                    </span>
                  )}
                </div>

                {/* Bubble */}
                <div
                  className={cn(
                    "relative rounded-2xl rounded-tl-none px-4 py-3 shadow-xl transition-all duration-300",
                    isError && !isCancelled
                      ? "bg-red-950/25 border border-red-500/25 text-red-200"
                      : isCancelled
                      ? "bg-amber-950/20 border border-amber-500/20 text-amber-200"
                      : "glass-pane border-white/8 text-foreground"
                  )}
                >
                  {isProcessing ? (
                    <TypingDots />
                  ) : (
                    <>
                      <div
                        className={cn(
                          "prose dark:prose-invert max-w-none text-sm leading-relaxed",
                        )}
                      >
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          rehypePlugins={[rehypeRaw]}
                          components={{
                            p: (props) => (
                              <p className="mb-2 last:mb-0">{processChildren(props.children)}</p>
                            ),
                            li: (props) => (
                              <li className="mb-1">{processChildren(props.children)}</li>
                            ),
                            td: (props) => (
                              <td className="p-2 border border-white/10">{processChildren(props.children)}</td>
                            ),
                            span: (props) => <span>{processChildren(props.children)}</span>,
                            strong: (props) => (
                              <strong
                                {...props}
                                className={cn("font-bold", isError ? "text-red-200" : "text-primary")}
                              />
                            ),
                            // ── Detect ```chart blocks and render Recharts ──
                            code: ({ node, className, children, ...rest }: any) => {
                              const lang = (className ?? "").replace("language-", "");
                              const raw = String(children).trim();
                              if (lang === "chart") {
                                return <ChartBlock raw={raw} />;
                              }
                              // Regular code block
                              return (
                                <code
                                  className={cn(
                                    "rounded px-1 py-0.5 text-[0.82em] font-mono",
                                    lang
                                      ? "block w-full overflow-x-auto bg-black/40 border border-white/10 p-3 my-2 rounded-xl"
                                      : "bg-white/10 text-indigo-300"
                                  )}
                                  {...rest}
                                >
                                  {children}
                                </code>
                              );
                            },
                            pre: ({ children }: any) => <>{children}</>,
                          }}
                        >
                          {content}
                        </ReactMarkdown>
                      </div>

                      {/* Options */}
                      {latestStep.attachment?.type === "options" && onOptionSelect && (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {latestStep.attachment.data?.map((opt: { label: string; value: string }) => (
                            <button
                              key={opt.value}
                              onClick={() => onOptionSelect(opt.value)}
                              className="px-3 py-1.5 rounded-xl text-xs font-semibold bg-primary/15 text-primary border border-primary/30 hover:bg-primary/25 transition-all hover:scale-[1.02]"
                            >
                              {opt.label}
                            </button>
                          ))}
                        </div>
                      )}

                      {/* Footer */}
                      <div className="mt-2 pt-1.5 border-t border-white/5 flex items-center gap-1">
                        <span className="text-[10px] font-mono text-muted-foreground/30 mr-auto">
                          {latestStep.timestamp}
                        </span>
                        <DownloadButton text={downloadText} timestamp={latestStep.timestamp} />
                        <CopyButton text={downloadText} />
                        <SpeakButton text={content} />
                      </div>
                    </>
                  )}
                </div>
              </div>
            </motion.div>
          );
        })}

        {/* Global typing indicator */}
        {isLoading && (groups.length === 0 || groups[groups.length - 1]?.type === "User") && (
          <motion.div
            key="typing"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="flex justify-start"
          >
            <div className="ml-7 glass-pane border-white/10 rounded-2xl rounded-tl-none px-5 py-3.5 shadow-xl">
              <TypingDots />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div ref={bottomRef} />
    </div>
  );
}
