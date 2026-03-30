import { useState } from "react";
import { Clock, ChevronRight, Trash2, Folder, FolderPlus, MoreHorizontal, Edit2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";

interface RecentsHistoryProps {
    recents: string[];
    onSelect: (cmd: string) => void;
    onEdit?: (cmd: string) => void;
    folders: FolderData[];
    onFoldersChange: (folders: FolderData[]) => void;
    onHistoryChange: (history: string[]) => void;
}

import { saveFolders, saveHistory } from "@/lib/api";

interface FolderData {
    id: string;
    name: string;
    items: string[];
}

export function RecentsHistory({ recents, onSelect, onEdit, folders, onFoldersChange, onHistoryChange }: RecentsHistoryProps) {
    const [isCreatingFolder, setIsCreatingFolder] = useState(false);
    const [newFolderName, setNewFolderName] = useState("");
    // Local state for main list deletion tracking is redundant now as we sync with backend
    // but we'll use a temporary state for smooth UI transitions if needed, 
    // or just use onHistoryChange immediately.
    const [deletedItems, setDeletedItems] = useState<string[]>([]);
    const [itemToDelete, setItemToDelete] = useState<string | null>(null);

    const visibleRecents = recents.filter(r => !deletedItems.includes(r));

    if (visibleRecents.length === 0 && folders.length === 0) {
        return (
            <div className="w-full h-full p-6 flex flex-col items-center justify-center text-slate-500 text-sm">
                <Clock className="w-8 h-8 mb-2 opacity-20" />
                <p>No history yet</p>
            </div>
        );
    }

    const handleDeleteClick = (item: string, e: React.MouseEvent) => {
        e.stopPropagation();
        setItemToDelete(item);
    };

    const confirmDelete = async () => {
        if (itemToDelete) {
            const newHistory = recents.filter(r => r !== itemToDelete);
            onHistoryChange(newHistory);
            saveHistory(newHistory);
            setItemToDelete(null);
        }
    };

    const cancelDelete = () => {
        setItemToDelete(null);
    };

    const handleCreateFolder = async () => {
        if (!newFolderName.trim()) return;
        const newFolders = [...folders, {
            id: Date.now().toString(),
            name: newFolderName.trim(),
            items: []
        }];
        onFoldersChange(newFolders);
        saveFolders(newFolders);
        setNewFolderName("");
        setIsCreatingFolder(false);
    };

    const addToFolder = async (item: string, folderId: string, e: React.MouseEvent) => {
        e.stopPropagation();
        const newFolders = folders.map(f => {
            if (f.id === folderId) {
                return { ...f, items: [...f.items, item] };
            }
            return f;
        });
        const newHistory = recents.filter(r => r !== item);
        
        onFoldersChange(newFolders);
        onHistoryChange(newHistory);
        
        await Promise.all([
            saveFolders(newFolders),
            saveHistory(newHistory)
        ]);
    };

    return (
        <div className="w-full h-full p-6 bg-transparent">
            {/* Delete Confirmation Modal */}
            <AnimatePresence>
                {itemToDelete && (
                    <>
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[110]"
                            onClick={cancelDelete}
                        />
                        <motion.div
                            initial={{ opacity: 0, scale: 0.95, y: 20 }}
                            animate={{ opacity: 1, scale: 1, y: 0 }}
                            exit={{ opacity: 0, scale: 0.95, y: 20 }}
                            className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-[120] w-[90%] max-w-sm"
                        >
                            <div className="relative overflow-hidden rounded-3xl bg-background/95 border border-white/10 shadow-2xl backdrop-blur-xl p-6">
                                {/* Decorative background elements */}
                                <div className="absolute -top-24 -right-24 w-48 h-48 bg-red-500/20 rounded-full blur-[80px]" />
                                <div className="absolute -bottom-24 -left-24 w-48 h-48 bg-primary/20 rounded-full blur-[80px]" />

                                <div className="relative z-10 flex flex-col items-center text-center">
                                    <div className="w-16 h-16 rounded-full bg-red-500/10 flex items-center justify-center mb-4 border border-red-500/20 shadow-[0_0_15px_rgba(239,68,68,0.1)]">
                                        <Trash2 className="w-8 h-8 text-red-500" />
                                    </div>

                                    <h3 className="text-xl font-black tracking-tight text-foreground mb-2">Delete Item</h3>
                                    <p className="text-sm text-muted-foreground mb-6 max-w-[250px]">
                                        Are you sure you want to delete this item? This action cannot be undone.
                                    </p>

                                    <div className="w-full p-4 bg-secondary/50 rounded-2xl border border-white/5 mb-8">
                                        <p className="text-sm text-foreground/80 break-words font-light line-clamp-3">
                                            "{itemToDelete}"
                                        </p>
                                    </div>

                                    <div className="flex w-full gap-3">
                                        <button
                                            onClick={cancelDelete}
                                            className="flex-1 py-3 px-4 rounded-xl text-sm font-bold text-slate-400 hover:text-white hover:bg-white/5 transition-all"
                                        >
                                            Cancel
                                        </button>
                                        <button
                                            onClick={confirmDelete}
                                            className="flex-1 py-3 px-4 rounded-xl text-sm font-bold bg-red-500/10 hover:bg-red-500/20 text-red-500 border border-red-500/20 hover:border-red-500/30 transition-all shadow-[0_0_20px_rgba(239,68,68,0.1)] hover:shadow-[0_0_30px_rgba(239,68,68,0.2)]"
                                        >
                                            Delete
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </motion.div>
                    </>
                )}
            </AnimatePresence>
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-2.5 text-muted-foreground">
                    <div className="p-1.5 rounded-lg bg-secondary border border-border">
                        <Clock className="w-3.5 h-3.5" />
                    </div>
                    <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-foreground/40">History</h3>
                </div>
                <button
                    onClick={() => setIsCreatingFolder(true)}
                    className="p-1.5 hover:bg-white/5 rounded-lg text-slate-500 hover:text-primary transition-all duration-300"
                    title="New Folder"
                >
                    <FolderPlus className="w-4 h-4" />
                </button>
            </div>

            {/* Folder Creation Input */}
            <AnimatePresence>
                {isCreatingFolder && (
                    <motion.div
                        initial={{ opacity: 0, y: -10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                        className="mb-6 p-3 glass-pane rounded-2xl border-primary/20"
                    >
                        <input
                            type="text"
                            value={newFolderName}
                            onChange={(e) => setNewFolderName(e.target.value)}
                            placeholder="Folder name..."
                            className="w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground mb-3"
                            autoFocus
                            onKeyDown={(e) => e.key === 'Enter' && handleCreateFolder()}
                        />
                        <div className="flex justify-end gap-3">
                            <button onClick={() => setIsCreatingFolder(false)} className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground hover:text-foreground transition-colors">Cancel</button>
                            <button onClick={handleCreateFolder} className="text-[10px] font-bold uppercase tracking-widest text-primary hover:text-primary/80 transition-colors">Create</button>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            <div className="space-y-6">
                {/* Folders List */}
                {folders.map(folder => (
                    <div key={folder.id} className="group">
                        <div className="flex items-center gap-2.5 text-foreground p-2 rounded-xl hover:bg-secondary/50 border border-transparent hover:border-border/40 transition-all duration-300 cursor-pointer">
                            <div className="p-1.5 bg-amber-500/10 rounded-lg">
                                <Folder className="w-3.5 h-3.5 text-amber-500" />
                            </div>
                            <span className="text-xs font-bold flex-1 tracking-tight">{folder.name}</span>
                            <span className="text-[9px] font-bold text-muted-foreground bg-secondary px-1.5 py-0.5 rounded-full">{folder.items.length}</span>
                        </div>
                        {folder.items.length > 0 && (
                            <div className="pl-6 mt-2 space-y-2 border-l-2 border-white/5 ml-5">
                                {folder.items.map((item, idx) => (
                                    <div key={idx} onClick={() => onSelect(item)} className="text-xs text-muted-foreground py-2 px-3 hover:bg-secondary rounded-xl cursor-pointer truncate transition-colors border border-transparent hover:border-border font-light">
                                        {item}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                ))}

                {/* Loose Items */}
                <div className="space-y-2">
                    {visibleRecents.length > 0 && (
                        <div className="text-[10px] font-black text-muted-foreground uppercase tracking-[0.2em] mb-4 mt-8 ml-1">Recent Commands</div>
                    )}

                    {visibleRecents.map((cmd, i) => (
                        <div
                            key={i}
                            className="group relative flex items-center p-2 rounded-xl hover:bg-secondary/50 transition-all duration-300 cursor-pointer border border-transparent hover:border-border/40"
                            onClick={() => onSelect(cmd)}
                        >
                            {/* Index badge */}
                            <span className="flex-shrink-0 w-5 h-5 rounded-full bg-secondary border border-border/50 text-[9px] font-black text-muted-foreground flex items-center justify-center mr-2 group-hover:border-primary/30 group-hover:text-primary transition-colors">
                                {i + 1}
                            </span>
                            <span className="text-xs text-foreground truncate font-normal flex-1 pr-6 tracking-tight">
                                {cmd}
                            </span>

                            {/* Actions Group */}
                            <div className="absolute right-3 opacity-0 group-hover:opacity-100 flex items-center gap-1 transition-all duration-300 translate-x-1 group-hover:translate-x-0">
                                    <button
                                        onClick={(e) => handleDeleteClick(cmd, e)}
                                        className="p-2 hover:bg-red-500/20 bg-[#0A0A12]/80 backdrop-blur-md rounded-xl text-slate-500 hover:text-red-400 border border-transparent hover:border-red-500/30 transition-all shadow-xl"
                                        title="Delete"
                                    >
                                        <Trash2 className="w-3.5 h-3.5" />
                                    </button>

                                    {onEdit && (
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                onEdit(cmd);
                                            }}
                                            className="p-2 hover:bg-primary/20 bg-[#0A0A12]/80 backdrop-blur-md rounded-xl text-slate-500 hover:text-primary border border-transparent hover:border-primary/30 transition-all shadow-xl"
                                            title="Edit"
                                        >
                                            <Edit2 className="w-3.5 h-3.5" />
                                        </button>
                                    )}

                                {folders.length > 0 && (
                                    <div className="relative group/folder">
                                        <button className="p-2 hover:bg-primary bg-[#0A0A12]/80 backdrop-blur-md rounded-xl text-slate-500 hover:text-white transition-all shadow-xl">
                                            <Folder className="w-3.5 h-3.5" />
                                        </button>
                                        <div className="absolute right-0 bottom-full mb-2 w-40 glass-pane rounded-2xl shadow-2xl overflow-hidden hidden group-hover/folder:block z-50">
                                            <div className="p-2 bg-white/5 border-b border-white/5 text-[10px] font-bold text-slate-500 uppercase tracking-widest text-center">Move to</div>
                                            {folders.map(f => (
                                                <div
                                                    key={f.id}
                                                    onClick={(e) => addToFolder(cmd, f.id, e)}
                                                    className="px-4 py-2.5 text-xs text-slate-300 hover:bg-primary/20 hover:text-white cursor-pointer truncate transition-colors"
                                                >
                                                    {f.name}
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
