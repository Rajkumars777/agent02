"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Command, Sparkles, Mic } from "lucide-react";
import { cn } from "@/lib/utils";

import { getApiBase } from "@/lib/api";

interface InputConsoleProps {
    onSend: (message: string) => void;
    loading: boolean;
    lastCommand?: string;  // For edit functionality
}

export function InputConsole({ onSend, loading, lastCommand }: InputConsoleProps) {
    const [input, setInput] = useState("");
    const [isFocused, setIsFocused] = useState(false);
    const [isRecording, setIsRecording] = useState(false);
    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const audioChunksRef = useRef<Blob[]>([]);
    const inputRef = useRef<HTMLTextAreaElement>(null);
    const appliedCommandRef = useRef("");

    // When lastCommand changes (user clicked Edit), populate input
    useEffect(() => {
        if (lastCommand && lastCommand !== appliedCommandRef.current && !loading) {
            setInput(lastCommand);
            appliedCommandRef.current = lastCommand;
            if (inputRef.current) {
                inputRef.current.focus();
                // Reset height for the text
                inputRef.current.style.height = 'auto';
                inputRef.current.style.height = `${inputRef.current.scrollHeight}px`;
            }
        }
    }, [lastCommand, loading]);

    // Auto-resize effect
    useEffect(() => {
        if (inputRef.current) {
            inputRef.current.style.height = 'auto';
            inputRef.current.style.height = `${inputRef.current.scrollHeight}px`;
        }
    }, [input]);


    const handleSubmit = (e?: React.FormEvent) => {
        e?.preventDefault();
        if (!input.trim() || loading) return;
        onSend(input);
        setInput("");
        // setWebStatus(""); // Clear web status on new chat
        // setWebResult(null);
        // setScreenshotPath(null);
    };

    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const mediaRecorder = new MediaRecorder(stream);
            mediaRecorderRef.current = mediaRecorder;
            audioChunksRef.current = [];

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunksRef.current.push(event.data);
                }
            };

            mediaRecorder.onstop = async () => {
                // Create audio blob
                const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });

                // Send to backend for transcription
                await transcribeAudio(audioBlob);

                // Stop all tracks
                stream.getTracks().forEach(track => track.stop());
            };

            mediaRecorder.start();
            setIsRecording(true);

            // Auto-stop after 5 seconds (you can adjust this)
            setTimeout(() => {
                if (mediaRecorderRef.current?.state === 'recording') {
                    stopRecording();
                }
            }, 5000);

        } catch (error) {
            console.error('Microphone error:', error);
            alert('Could not access microphone. Please allow microphone permissions.');
        }
    };

    const stopRecording = () => {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
            mediaRecorderRef.current.stop();
            setIsRecording(false);
        }
    };

    const transcribeAudio = async (audioBlob: Blob) => {
        try {
            const formData = new FormData();
            formData.append('file', audioBlob, 'voice_command.wav');

            const base = await getApiBase();
            const response = await fetch(`${base}/api/voice/transcribe`, {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                throw new Error('Transcription failed');
            }

            const data = await response.json();

            if (data.text) {
                // CRITICAL: Put text in input box, do NOT execute
                setInput(data.text);
            }

        } catch (error) {
            console.error('Transcription error:', error);
            alert('Voice transcription failed. Make sure the backend is running with Faster-Whisper installed.');
        }
    };

    const handleVoiceClick = () => {
        if (isRecording) {
            stopRecording();
        } else {
            startRecording();
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
        }
    };



    return (
        <div className="w-full max-w-3xl mx-auto relative z-[60] flex flex-col gap-3">
            <div className="relative">
                {/* Ambient Glow behind the bar */}
                <div
                    className={cn(
                        "absolute -inset-2 bg-primary/15 rounded-[1.5rem] blur-2xl opacity-0 transition-all duration-1000 -z-10",
                        (isFocused || input.length > 0) && "opacity-100 scale-102"
                    )}
                />

                <motion.form
                    onSubmit={handleSubmit}
                    className={cn(
                        "relative flex items-center gap-3 p-1.5 rounded-[1.5rem] border transition-all duration-500",
                        "glass-pane items-end", // Changed items-center to items-end for better multi-line look
                        isFocused
                            ? "border-primary/40 shadow-[0_0_30px_-10px_oklch(0.68_0.28_280/0.3)] scale-[1.005]"
                            : "border-border/60 hover:border-border/80"
                    )}
                    initial={{ y: 20, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    transition={{ delay: 0.8, type: "spring", stiffness: 100 }}
                >
                    {/* Visual Anchor / Icon */}
                    <div className={cn(
                        "ml-2 mb-2 p-2 rounded-full transition-all duration-500", // Added mb-2
                        isFocused
                            ? "bg-primary/15 text-primary scale-105 rotate-6"
                            : "bg-secondary text-muted-foreground/60"
                    )}>
                        <Command className="w-4 h-4" />
                    </div>

                    <textarea
                        ref={inputRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        onFocus={() => setIsFocused(true)}
                        onBlur={() => setIsFocused(false)}
                        placeholder={isRecording ? "🎤 Listening..." : "Ask NEXUS to do anything..."}
                        className={cn(
                            "flex-1 bg-transparent border-none outline-none text-base placeholder:text-muted-foreground/40 py-3 text-foreground font-normal tracking-tight focus:ring-0 resize-none",
                            "min-h-[44px] max-h-[200px] overflow-y-auto custom-scrollbar"
                        )}
                        rows={1}
                    />

                    <div className="mr-1 mb-1.5 flex items-center gap-2"> {/* Added mb-1.5 */}
                        {/* Voice Button */}
                        <button
                            type="button"
                            onClick={handleVoiceClick}
                            className={cn(
                                "w-9 h-9 rounded-full flex items-center justify-center transition-all duration-300 relative group overflow-hidden",
                                isRecording
                                    ? "bg-red-500 animate-pulse"
                                    : "bg-secondary hover:bg-blue-500/10 text-muted-foreground hover:text-blue-500"
                            )}
                            title={isRecording ? "Stop" : "Speak"}
                        >
                            <Mic className={cn("w-4 h-4 transition-transform duration-300", !isRecording && "group-hover:scale-110")} />
                            {isRecording && (
                                <span className="absolute inset-0 bg-red-600 rounded-full animate-ping opacity-20" />
                            )}
                        </button>

                        <AnimatePresence>
                            {(input.length > 0 || loading) && (
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

            {/* Helper Text */}
            {isRecording && (
                <motion.div
                    initial={{ opacity: 0, y: -5 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="text-center text-[10px] text-red-400 font-bold uppercase tracking-widest"
                >
                    🎤 Recording...
                </motion.div>
            )}
        </div>
    );
}
