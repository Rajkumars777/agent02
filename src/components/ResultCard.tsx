"use client";

import { motion } from "framer-motion";
import {
    FileText,
    FileSpreadsheet,
    Globe,
    CheckCircle2,
    AlertCircle,
    Info,
    ChevronRight,
    Search,
    Download,
    FileCode
} from "lucide-react";
import { cn } from "@/lib/utils";

interface ResultCardProps {
    type: string;
    content: any;
    status?: "success" | "pending" | "error";
}

export function ResultCard({ type, content, status = "success" }: ResultCardProps) {
    // Determine the icon and title based on content analysis if type is generic "Action"
    let displayIcon = <Info className="w-5 h-5" />;
    let displayTitle = "Result";
    let accentColor = "primary";

    // Detect content type and normalize data
    let processedContent = content;
    let isFileList = false;

    // Smart Detection for string-based results
    if (typeof content === 'string') {
        const filePattern = /[a-zA-Z0-9._-]+\.(?:txt|pdf|docx|zip|exe|jpg|png|mp4|msi|csv|xlsx|json)/g;
        const matches = content.match(filePattern);

        // If many files are found, treat as a list
        if (matches && matches.length > 3) {
            isFileList = true;
            processedContent = matches;
            displayTitle = content.split(':')[0] || "Files Located"; // Extract "Files in 'downloads'..." part
            displayIcon = <Search className="w-5 h-5" />;
            accentColor = "blue";
        }
    } else if (Array.isArray(content)) {
        isFileList = content.length > 0 && typeof content[0] === 'string' && content[0].includes('.');
        if (isFileList) {
            displayIcon = <Search className="w-5 h-5" />;
            displayTitle = "Files Located";
            accentColor = "blue";
        }
    }

    const isExcelData = !isFileList && ((Array.isArray(content) && content.length > 0 && typeof content[0] === 'object') || (content?.rows));
    const isFileOp = !isFileList && !isExcelData && typeof content === 'string' && (content.toLowerCase().includes("deleted") || content.toLowerCase().includes("moved") || content.toLowerCase().includes("renamed"));

    if (isExcelData) {
        displayIcon = <FileSpreadsheet className="w-5 h-5" />;
        displayTitle = "Data Analysis";
        accentColor = "emerald";
    } else if (isFileOp) {
        displayIcon = <FileCode className="w-5 h-5" />;
        displayTitle = "File Operation";
        accentColor = "purple";
    }

    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className={cn(
                "w-full glass-pane rounded-2xl overflow-hidden border-white/5",
                status === "error" && "border-red-500/20"
            )}
        >
            {/* Header */}
            <div className="px-4 py-3 flex items-center justify-between bg-white/[0.02] border-b border-white/5">
                <div className="flex items-center gap-2.5">
                    <div className={cn(
                        "p-1.5 rounded-lg",
                        accentColor === "primary" && "bg-primary/20 text-primary",
                        accentColor === "blue" && "bg-blue-500/20 text-blue-400",
                        accentColor === "emerald" && "bg-emerald-500/20 text-emerald-400",
                        accentColor === "purple" && "bg-purple-500/20 text-purple-400"
                    )}>
                        <div className="w-4 h-4">{displayIcon}</div>
                    </div>
                    <div>
                        <h3 className="text-xs font-bold text-foreground tracking-tight">{displayTitle}</h3>
                        <p className="text-[9px] text-muted-foreground uppercase tracking-widest font-medium opacity-50">Nexus Output</p>
                    </div>
                </div>

                <div className={cn(
                    "flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider",
                    status === "success" && "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20",
                    status === "pending" && "bg-amber-500/10 text-amber-400 border border-amber-500/20",
                    status === "error" && "bg-red-500/10 text-red-400 border border-red-500/20"
                )}>
                    {status === "success" && <CheckCircle2 className="w-2.5 h-2.5" />}
                    {status === "pending" && <div className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />}
                    {status === "error" && <AlertCircle className="w-2.5 h-2.5" />}
                    {status}
                </div>
            </div>

            {/* Content Body */}
            <div className="p-0">
                {isFileList ? (
                    <div className="divide-y divide-white/5 max-h-[300px] overflow-y-auto custom-scrollbar">
                        {(processedContent as string[]).map((file: string, idx: number) => (
                            <div key={idx} className="flex items-center justify-between p-2.5 hover:bg-white/[0.03] transition-all group px-4">
                                <div className="flex items-center gap-2.5">
                                    <div className="p-1.5 bg-secondary rounded-md text-muted-foreground group-hover:text-primary transition-colors">
                                        <FileText className="w-3.5 h-3.5" />
                                    </div>
                                    <span className="text-xs text-foreground font-medium truncate max-w-[400px]">{file}</span>
                                </div>
                                <div className="flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <button className="p-1 hover:bg-secondary rounded-md text-muted-foreground hover:text-foreground transition-colors">
                                        <ChevronRight className="w-3.5 h-3.5" />
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                ) : isExcelData ? (
                    <div className="p-5">
                        <div className="overflow-hidden rounded-xl border border-white/10">
                            <table className="w-full text-left text-xs text-slate-300">
                                <thead>
                                    <tr className="bg-white/5">
                                        {Object.keys(Array.isArray(content) ? content[0] : content.rows[0]).slice(0, 5).map(key => (
                                            <th key={key} className="px-4 py-3 font-semibold text-slate-400 uppercase text-[10px] tracking-wider border-b border-white/10">{key}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-white/5">
                                    {(Array.isArray(content) ? content : content.rows).slice(0, 10).map((row: any, i: number) => (
                                        <tr key={i} className="hover:bg-white/[0.02] transition-colors">
                                            {Object.values(row).slice(0, 5).map((val: any, j: number) => (
                                                <td key={j} className="px-4 py-3 truncate max-w-[150px] text-slate-400">{String(val)}</td>
                                            ))}
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                            {(Array.isArray(content) ? content.length : content.rows.length) > 10 && (
                                <div className="p-2 text-center bg-black/20 text-[10px] text-slate-500 uppercase font-bold tracking-widest border-t border-white/5">
                                    + {(Array.isArray(content) ? content.length : content.rows.length) - 10} more rows
                                </div>
                            )}
                        </div>
                    </div>
                ) : (
                    <div className="p-5">
                        <div className="prose prose-invert prose-sm max-w-none text-slate-300 leading-relaxed font-light">
                            {typeof content === 'string' ? content : JSON.stringify(content, null, 2)}
                        </div>
                    </div>
                )}
            </div>

            {/* Footer Actions (Optional) */}
            <div className="px-5 py-3 bg-secondary/20 border-t border-border flex justify-end gap-3">
                <button className="text-[10px] font-bold text-muted-foreground hover:text-foreground uppercase tracking-widest transition-colors flex items-center gap-1.5">
                    <Download className="w-3 h-3" />
                    Export JSON
                </button>
            </div>
        </motion.div>
    );
}
