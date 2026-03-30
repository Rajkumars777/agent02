"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Bot, CheckCircle2, Edit2, Copy, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import React, { useState, useEffect, useRef } from "react";
import { openPath } from "@/lib/api";

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
};

interface TimelineFeedProps {
    steps: Step[];
    onOptionSelect?: (value: string) => void;
    onEdit?: (content: string) => void;
    isLoading?: boolean;
}

const linkify = (text: string) => {
    if (typeof text !== 'string') return text;
    const pathRegex = /([a-zA-Z]:\\[\\\w\s.-]+|\b[\w.-]+\.(?:pdf|txt|png|jpg|jpeg|docx|xlsx|exe|md)\b)/g;
    const parts = text.split(pathRegex);
    const matches = text.match(pathRegex);
    if (!matches) return text;
    const result: (string | React.ReactNode)[] = [];
    let matchIndex = 0;
    parts.forEach((part, i) => {
        if (matchIndex < matches.length && matches[matchIndex] === part) {
            const path = part;
            result.push(
                <span
                    key={`${i}-${matchIndex}`}
                    onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        openPath(path).catch(console.error);
                    }}
                    className="text-blue-500 hover:text-blue-400 font-bold underline cursor-pointer decoration-dotted underline-offset-4 bg-blue-500/10 px-1 rounded-sm border border-blue-500/20"
                    title={`Click to open ${path}`}
                >
                    {part}
                </span>
            );
            matchIndex++;
        } else {
            result.push(part);
        }
    });
    return result;
};

const processChildren = (children: any): any => {
    return React.Children.map(children, (child) => {
        if (typeof child === 'string') return linkify(child);
        if (React.isValidElement(child) && (child.props as any).children) {
            return React.cloneElement(child, {
                children: processChildren((child.props as any).children)
            } as any);
        }
        return child;
    });
};


/** Typing indicator — 3 bouncing dots */
function TypingDots() {
    return (
        <div className="flex items-center gap-1 px-1 py-1">
            {[0, 1, 2].map((i) => (
                <motion.div
                    key={i}
                    className="w-2 h-2 rounded-full bg-primary/60"
                    animate={{ y: [0, -6, 0] }}
                    transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.15, ease: "easeInOut" }}
                />
            ))}
        </div>
    );
}

/** Copy-to-clipboard button for AI messages */
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
            className="opacity-0 group-hover:opacity-100 transition-all duration-200 p-1.5 rounded-lg hover:bg-white/10 text-muted-foreground hover:text-foreground"
            title="Copy response"
        >
            <AnimatePresence mode="wait">
                {copied ? (
                    <motion.div key="check" initial={{ scale: 0.7 }} animate={{ scale: 1 }} exit={{ scale: 0.7 }}>
                        <Check className="w-3 h-3 text-green-400" />
                    </motion.div>
                ) : (
                    <motion.div key="copy" initial={{ scale: 0.7 }} animate={{ scale: 1 }} exit={{ scale: 0.7 }}>
                        <Copy className="w-3 h-3" />
                    </motion.div>
                )}
            </AnimatePresence>
        </button>
    );
}

export function TimelineFeed({ steps, onOptionSelect, onEdit, isLoading }: TimelineFeedProps) {
    const bottomRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom whenever steps change or loading state changes
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [steps, isLoading]);

    if (steps.length === 0 && !isLoading) return null;

    // Group steps: A sequence of AI steps following a User message (or starting the chat)
    const groups: { type: "User" | "AI"; steps: Step[] }[] = [];
    steps.forEach((step) => {
        if (step.type === "User") {
            groups.push({ type: "User", steps: [step] });
        } else {
            const lastGroup = groups[groups.length - 1];
            if (lastGroup && lastGroup.type === "AI") {
                lastGroup.steps.push(step);
            } else {
                groups.push({ type: "AI", steps: [step] });
            }
        }
    });

    return (
        <div className="w-full max-w-4xl mx-auto mt-8 px-4 relative pb-32 flex flex-col gap-8">
            <AnimatePresence mode="popLayout">
                {groups.map((group, groupIdx) => {
                    const isUser = group.type === "User";
                    const latestStep = group.steps[group.steps.length - 1];
                    const isProcessing = group.type === "AI" && latestStep.type === "Reasoning" && groupIdx === groups.length - 1;

                    return (
                        <motion.div
                            key={groupIdx}
                            initial={{ opacity: 0, y: 20, scale: 0.98 }}
                            animate={{ opacity: 1, y: 0, scale: 1 }}
                            transition={{ duration: 0.5, ease: "easeOut" }}
                            className={cn(
                                "flex w-full group",
                                isUser ? "justify-end" : "justify-start"
                            )}
                        >
                            <div className={cn(
                                "max-w-[80%] relative",
                                isUser ? "order-1" : "order-2"
                            )}>
                                {/* Bubble Style */}
                                <div className={cn(
                                    "p-4 rounded-2xl relative transition-all duration-300 shadow-xl",
                                    isUser
                                        ? "bg-primary text-primary-foreground rounded-tr-none shadow-primary/20"
                                        : "glass-pane border-white/10 rounded-tl-none min-w-[100px]"
                                )}>
                                    
                                    {/* AI Message Body */}
                                    <div className={cn(
                                        "prose dark:prose-invert max-w-none text-sm leading-relaxed",
                                        isUser ? "text-primary-foreground" : "text-foreground"
                                    )}>
                                        {isProcessing ? (
                                            <TypingDots />
                                        ) : (
                                            <ReactMarkdown
                                                remarkPlugins={[remarkGfm]}
                                                rehypePlugins={[rehypeRaw]}
                                                components={{
                                                    p: (props) => <p className="mb-2 last:mb-0">{processChildren(props.children)}</p>,
                                                    li: (props) => <li className="mb-1">{processChildren(props.children)}</li>,
                                                    td: (props) => <td className="p-2 border border-white/10">{processChildren(props.children)}</td>,
                                                    span: (props) => <span>{processChildren(props.children)}</span>,
                                                    strong: (props) => <strong {...props} className={cn("font-bold", isUser ? "text-white" : "text-primary")} />,
                                                }}
                                            >
                                                {latestStep.content}
                                            </ReactMarkdown>
                                        )}
                                    </div>

                                    {/* Metadata Footer */}
                                    <div className={cn(
                                        "mt-2 flex items-center gap-3 opacity-30 text-[9px] font-mono",
                                        isUser ? "justify-end text-primary-foreground" : "justify-start text-foreground"
                                    )}>
                                        {isUser && onEdit && (
                                            <button
                                                onClick={() => onEdit(latestStep.content)}
                                                className="hover:opacity-100 transition-opacity flex items-center gap-1 group/edit"
                                                title="Edit and retry"
                                            >
                                                <Edit2 className="w-2.5 h-2.5 group-hover/edit:scale-110 transition-transform" />
                                                <span className="opacity-0 group-hover/edit:opacity-100 transition-opacity">EDIT</span>
                                            </button>
                                        )}
                                        {!isUser && !isProcessing && <CheckCircle2 className="w-2.5 h-2.5" />}
                                        <span>{latestStep.timestamp}</span>
                                        {/* Copy button for AI messages */}
                                        {!isUser && !isProcessing && (
                                            <CopyButton text={latestStep.content} />
                                        )}
                                    </div>
                                </div>
                            </div>
                        </motion.div>
                    );
                })}

                {/* Typing indicator when loading and last message is from user */}
                {isLoading && (groups.length === 0 || groups[groups.length - 1]?.type === "User") && (
                    <motion.div
                        key="typing"
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0 }}
                        className="flex justify-start"
                    >
                        <div className="glass-pane border-white/10 rounded-2xl rounded-tl-none p-4 shadow-xl">
                            <TypingDots />
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Scroll anchor */}
            <div ref={bottomRef} />
        </div>
    );
}
