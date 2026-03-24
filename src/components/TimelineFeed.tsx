"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Bot, Activity, Play, CheckCircle2, Clock, Edit2, Save, X, FileText, FileSpreadsheet, File, Globe } from "lucide-react";
import { cn } from "@/lib/utils";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import React, { useState, useEffect } from "react";
// Dynamic import for Tauri to avoid SSR issues
import dynamic from 'next/dynamic';
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
    onEdit?: (content: string) => void; // Added onEdit prop
}

export function TimelineFeed({ steps, onOptionSelect, onEdit }: TimelineFeedProps) {
    if (steps.length === 0) return null;

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
                    // For AI groups, we primarily show the latest step or the result
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
                                        {isProcessing && (
                                            <div className="flex items-center gap-2 text-primary/60 mb-2">
                                                <Bot className="w-3.5 h-3.5 animate-pulse" />
                                                <span className="text-[10px] font-bold uppercase tracking-widest">Analyzing...</span>
                                            </div>
                                        )}
                                        
                                        {/* Render the core content */}
                                        <ReactMarkdown
                                            remarkPlugins={[remarkGfm]}
                                            rehypePlugins={[rehypeRaw]}
                                            components={{
                                                p: (props) => {
                                                    // Function to wrap paths/filenames in clickable spans
                                                    const linkify = (text: string) => {
                                                        if (typeof text !== 'string') return text;
                                                        
                                                        // Regex for Windows paths and filenames with specific common extensions
                                                        // Using negative lookahead to avoid matching common words that might look like files
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
                                                                        key={i}
                                                                        onClick={(e) => {
                                                                            e.preventDefault();
                                                                            e.stopPropagation();
                                                                            console.log("Opening path:", path);
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

                                                    // Recursively process children to find text nodes
                                                    const processChildren = (children: any): any => {
                                                        return React.Children.map(children, (child) => {
                                                            if (typeof child === 'string') {
                                                                return linkify(child);
                                                            }
                                                            if (React.isValidElement(child) && (child.props as any).children) {
                                                                return React.cloneElement(child, {
                                                                    children: processChildren((child.props as any).children)
                                                                } as any);
                                                            }
                                                            return child;
                                                        });
                                                    };

                                                    return <p className="mb-2 last:mb-0">{processChildren(props.children)}</p>;
                                                },
                                                strong: (props) => <strong {...props} className={cn("font-bold", isUser ? "text-white" : "text-primary")} />,
                                            }}
                                        >
                                            {latestStep.content}
                                        </ReactMarkdown>
                                    </div>

                                    {/* AI Special Result Cards (Removed for clean UI) */}
                                    {!isUser && (
                                        <div className="mt-2 text-[10px] text-primary/40 flex items-center gap-1.5 px-1 font-medium italic">
                                            {isProcessing ? null : <CheckCircle2 className="w-2.5 h-2.5" />}
                                        </div>
                                    )}

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
                                        <span>{latestStep.timestamp}</span>
                                    </div>
                                </div>
                            </div>
                        </motion.div>
                    );
                })}
            </AnimatePresence>
        </div>
    );
}


