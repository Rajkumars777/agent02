"use client";
/**
 * useSpeech.ts
 * ============
 * Two clean hooks powered by the browser's native Web Speech API:
 *
 *  useSpeechRecognition()  → push-to-talk speech-to-text (FAST — continuous + auto-restart)
 *  useSpeechSynthesis()    → text-to-speech playback
 *
 * No backend required. Works in Chrome, Edge, and Safari 17+.
 * Speed optimisation: continuous=true + interimResults so transcripts appear
 * in real-time and the final result is delivered immediately without waiting
 * for the full sentence to end.
 */

import { useState, useRef, useCallback, useEffect } from "react";

// ─── Types ────────────────────────────────────────────────────────────────────

interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList;
  resultIndex: number;
}

interface SpeechRecognitionErrorEvent extends Event {
  error: string;
}

interface SpeechRecognitionInstance extends EventTarget {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((e: SpeechRecognitionEvent) => void) | null;
  onerror: ((e: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  onstart: (() => void) | null;
}

// ─── useSpeechRecognition ─────────────────────────────────────────────────────

export type RecognitionState = "idle" | "listening" | "processing" | "error";

export interface UseSpeechRecognitionReturn {
  state: RecognitionState;
  transcript: string;
  interimTranscript: string;
  error: string | null;
  isSupported: boolean;
  startListening: () => void;
  stopListening: () => void;
  resetTranscript: () => void;
}

export function useSpeechRecognition(
  onFinalTranscript?: (text: string) => void
): UseSpeechRecognitionReturn {
  const [state, setState] = useState<RecognitionState>("idle");
  const [transcript, setTranscript] = useState("");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [error, setError] = useState<string | null>(null);

  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const accumulatedRef = useRef(""); // accumulate finals across continuous segments
  const stoppedByUserRef = useRef(false); // track intentional stops

  const isSupported =
    typeof window !== "undefined" &&
    ("SpeechRecognition" in window || "webkitSpeechRecognition" in window);

  const createRecognition = useCallback((): SpeechRecognitionInstance | null => {
    if (!isSupported) return null;
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const rec: SpeechRecognitionInstance = new SpeechRecognition();
    rec.lang = "en-US";
    rec.continuous = true;        // ← KEY: keeps listening without restart gaps
    rec.interimResults = true;    // ← real-time word-by-word display
    rec.maxAlternatives = 1;
    return rec;
  }, [isSupported]);

  const startListening = useCallback(() => {
    if (!isSupported) {
      setError("Speech recognition is not supported in this browser. Try Chrome or Edge.");
      setState("error");
      return;
    }

    // Abort any previous session
    if (recognitionRef.current) {
      try { recognitionRef.current.abort(); } catch { /* ignore */ }
    }

    const rec = createRecognition();
    if (!rec) return;
    recognitionRef.current = rec;

    stoppedByUserRef.current = false;
    accumulatedRef.current = "";

    setError(null);
    setTranscript("");
    setInterimTranscript("");
    setState("listening");

    rec.onstart = () => setState("listening");

    rec.onresult = (e: SpeechRecognitionEvent) => {
      let interim = "";
      let newFinal = "";

      for (let i = e.resultIndex; i < e.results.length; i++) {
        const result = e.results[i];
        if (result.isFinal) {
          newFinal += result[0].transcript;
        } else {
          interim += result[0].transcript;
        }
      }

      if (newFinal) {
        accumulatedRef.current = (accumulatedRef.current + " " + newFinal).trim();
        setTranscript(accumulatedRef.current);
        setInterimTranscript("");
        // Deliver final transcript immediately as it arrives (no waiting for stop)
        if (onFinalTranscript) onFinalTranscript(accumulatedRef.current);
      }

      if (interim) {
        setInterimTranscript(interim);
      }
    };

    rec.onerror = (e: SpeechRecognitionErrorEvent) => {
      const msgs: Record<string, string> = {
        "not-allowed":    "Microphone access denied. Click the 🔒 icon in the address bar and allow microphone, then retry.",
        "no-speech":      "No speech detected — please speak clearly and try again.",
        "audio-capture":  "No microphone found. Make sure a microphone is connected.",
        "network":        "Google's speech servers are unreachable. Check your internet connection.",
        "service-not-allowed": "Speech recognition blocked. Make sure the page is served over HTTPS or localhost.",
        "aborted":        "", // user-initiated stop, silent
        "language-not-supported": "Language not supported. Try switching your browser language to English.",
      };
      const msg = msgs[e.error] ?? `Recognition error: ${e.error}`;
      if (msg) { setError(msg); setState("error"); }
      else setState("idle");
    };

    rec.onend = () => {
      setInterimTranscript("");
      // If user didn't explicitly stop and no error, auto-restart for seamless continuous mode
      if (!stoppedByUserRef.current) {
        try {
          // Small delay to avoid Chrome's rate-limit on rapid restart
          setTimeout(() => {
            if (!stoppedByUserRef.current && recognitionRef.current) {
              try { recognitionRef.current.start(); } catch { /* might already be running */ }
            }
          }, 100);
        } catch { /* ignore */ }
      } else {
        setState("idle");
      }
    };

    try {
      rec.start();
    } catch (err) {
      setError("Could not start microphone. Check permissions.");
      setState("error");
    }
  }, [isSupported, createRecognition, onFinalTranscript]);

  const stopListening = useCallback(() => {
    stoppedByUserRef.current = true;
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch { /* ignore */ }
    }
    setState("idle");
    setInterimTranscript("");
  }, []);

  const resetTranscript = useCallback(() => {
    setTranscript("");
    setInterimTranscript("");
    setError(null);
    setState("idle");
    accumulatedRef.current = "";
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stoppedByUserRef.current = true;
      if (recognitionRef.current) {
        try { recognitionRef.current.abort(); } catch { /* ignore */ }
      }
    };
  }, []);

  return {
    state,
    transcript,
    interimTranscript,
    error,
    isSupported,
    startListening,
    stopListening,
    resetTranscript,
  };
}


// ─── useSpeechSynthesis ────────────────────────────────────────────────────────

export type SynthesisState = "idle" | "speaking" | "paused";

export interface UseSpeechSynthesisReturn {
  state: SynthesisState;
  isSupported: boolean;
  speak: (text: string) => void;
  stop: () => void;
  pause: () => void;
  resume: () => void;
  voices: SpeechSynthesisVoice[];
  selectedVoice: SpeechSynthesisVoice | null;
  setSelectedVoice: (v: SpeechSynthesisVoice | null) => void;
  rate: number;
  setRate: (r: number) => void;
  pitch: number;
  setPitch: (p: number) => void;
}

export function useSpeechSynthesis(): UseSpeechSynthesisReturn {
  const [state, setState] = useState<SynthesisState>("idle");
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [selectedVoice, setSelectedVoice] = useState<SpeechSynthesisVoice | null>(null);
  const [rate, setRate] = useState(1.0);
  const [pitch, setPitch] = useState(1.0);
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);

  const isSupported = typeof window !== "undefined" && "speechSynthesis" in window;

  // Load voices (they load async in Chrome)
  useEffect(() => {
    if (!isSupported) return;
    const load = () => {
      const v = window.speechSynthesis.getVoices();
      if (v.length) {
        setVoices(v);
        // Auto-select a good English voice
        const preferred = v.find(
          (x) => x.lang.startsWith("en") && x.name.includes("Google")
        ) || v.find((x) => x.lang.startsWith("en")) || v[0];
        setSelectedVoice((prev) => prev ?? preferred ?? null);
      }
    };
    load();
    window.speechSynthesis.addEventListener("voiceschanged", load);
    return () => window.speechSynthesis.removeEventListener("voiceschanged", load);
  }, [isSupported]);

  // Strip markdown for cleaner TTS
  const cleanText = (text: string): string => {
    return text
      .replace(/#{1,6}\s+/g, "")          // headings
      .replace(/\*\*(.*?)\*\*/g, "$1")     // bold
      .replace(/\*(.*?)\*/g, "$1")         // italic
      .replace(/`{1,3}[^`]*`{1,3}/g, "")  // code
      .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1") // links
      .replace(/>\s+/gm, "")              // blockquotes
      .replace(/[-*+]\s+/gm, "")          // list bullets
      .replace(/\n{2,}/g, ". ")           // double newlines → pause
      .replace(/\n/g, " ")
      .trim();
  };

  const speak = useCallback((text: string) => {
    if (!isSupported) return;
    window.speechSynthesis.cancel();
    setState("idle");

    const cleaned = cleanText(text);
    if (!cleaned) return;

    const utter = new SpeechSynthesisUtterance(cleaned);
    if (selectedVoice) utter.voice = selectedVoice;
    utter.rate = rate;
    utter.pitch = pitch;
    utter.lang = selectedVoice?.lang ?? "en-US";

    utter.onstart = () => setState("speaking");
    utter.onend = () => setState("idle");
    utter.onpause = () => setState("paused");
    utter.onresume = () => setState("speaking");
    utter.onerror = () => setState("idle");

    utteranceRef.current = utter;
    window.speechSynthesis.speak(utter);
  }, [isSupported, selectedVoice, rate, pitch]);

  const stop = useCallback(() => {
    if (!isSupported) return;
    window.speechSynthesis.cancel();
    setState("idle");
  }, [isSupported]);

  const pause = useCallback(() => {
    if (!isSupported) return;
    window.speechSynthesis.pause();
    setState("paused");
  }, [isSupported]);

  const resume = useCallback(() => {
    if (!isSupported) return;
    window.speechSynthesis.resume();
    setState("speaking");
  }, [isSupported]);

  return {
    state, isSupported,
    speak, stop, pause, resume,
    voices, selectedVoice, setSelectedVoice,
    rate, setRate, pitch, setPitch,
  };
}
