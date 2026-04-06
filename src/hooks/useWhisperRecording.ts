"use client";
/**
 * useWhisperRecording.ts
 * ======================
 * Records audio in the browser via MediaRecorder, then POSTs the blob to the
 * backend /tools/voice/transcribe endpoint (faster-whisper, fully offline).
 *
 * No Google servers involved. Works on any browser with MediaRecorder support.
 */

import { useState, useRef, useCallback, useEffect } from "react";
import { getApiBase } from "@/lib/api";

export type WhisperState =
  | "idle"
  | "recording"
  | "uploading"
  | "transcribing"
  | "done"
  | "error"
  | "not-installed";

export interface WhisperResult {
  text: string;
  language?: string;
  duration_s?: number;
}

export interface UseWhisperRecordingReturn {
  state: WhisperState;
  transcript: string;
  error: string | null;
  isRecording: boolean;
  isBusy: boolean;
  isSupported: boolean;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
  reset: () => void;
}

export function useWhisperRecording(
  onTranscript?: (result: WhisperResult) => void
): UseWhisperRecordingReturn {
  const [state, setState] = useState<WhisperState>("idle");
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  const isSupported =
    mounted &&
    typeof window !== "undefined" &&
    typeof window.MediaRecorder !== "undefined" &&
    typeof navigator.mediaDevices?.getUserMedia === "function";

  const reset = useCallback(() => {
    setState("idle");
    setTranscript("");
    setError(null);
    chunksRef.current = [];
  }, []);

  const stopRecording = useCallback(() => {
    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state !== "inactive"
    ) {
      mediaRecorderRef.current.stop();
    }
    // Stream tracks stopped inside onstop to avoid race condition
  }, []);

  const startRecording = useCallback(async () => {
    if (!isSupported) {
      setError("MediaRecorder is not supported in this browser.");
      setState("error");
      return;
    }

    reset();

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,     // Whisper prefers 16 kHz
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      streamRef.current = stream;
    } catch (err: any) {
      const msg =
        err?.name === "NotAllowedError"
          ? "Microphone access denied. Allow microphone in browser settings and retry."
          : `Could not access microphone: ${err?.message ?? err}`;
      setError(msg);
      setState("error");
      return;
    }

    // Pick the best MIME type available
    const mimeType = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/ogg;codecs=opus",
      "audio/mp4",
    ].find((m) => MediaRecorder.isTypeSupported(m)) ?? "";

    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : {});
    mediaRecorderRef.current = recorder;
    chunksRef.current = [];

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };

    recorder.onstop = async () => {
      // Stop all tracks
      stream.getTracks().forEach((t) => t.stop());
      streamRef.current = null;

      const blob = new Blob(chunksRef.current, {
        type: mimeType || "audio/webm",
      });
      chunksRef.current = [];

      if (blob.size < 1000) {
        setError("Recording was too short or silent. Please try again.");
        setState("error");
        return;
      }

      await uploadAndTranscribe(blob, mimeType);
    };

    recorder.onerror = (e: any) => {
      setError(`Recording error: ${e?.error?.message ?? "unknown"}`);
      setState("error");
    };

    recorder.start(250); // collect chunks every 250 ms
    setState("recording");
  }, [isSupported, reset]);

  const uploadAndTranscribe = useCallback(
    async (blob: Blob, mimeType: string) => {
      setState("uploading");

      // Choose extension from MIME type
      const ext =
        mimeType.includes("ogg") ? "ogg" :
        mimeType.includes("mp4") ? "mp4" :
        "webm";

      const formData = new FormData();
      formData.append("file", blob, `recording.${ext}`);

      try {
        const base = await getApiBase();
        setState("transcribing");

        const res = await fetch(`${base}/tools/voice/transcribe`, {
          method: "POST",
          body: formData,
        });

        if (res.status === 501) {
          setError(
            "Whisper is not installed on the backend. " +
              "Run: pip install faster-whisper  and restart the backend."
          );
          setState("not-installed");
          return;
        }

        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body?.detail ?? `HTTP ${res.status}`);
        }

        const data = await res.json();
        const text = (data.text ?? "").trim();

        if (!text) {
          setError("No speech detected in the recording. Please try speaking clearly.");
          setState("error");
          return;
        }

        setTranscript(text);
        setState("done");
        if (onTranscript) {
          onTranscript({
            text,
            language: data.language,
            duration_s: data.duration_s,
          });
        }
      } catch (err: any) {
        setError(`Transcription failed: ${err?.message ?? err}`);
        setState("error");
      }
    },
    [onTranscript]
  );

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (
        mediaRecorderRef.current &&
        mediaRecorderRef.current.state !== "inactive"
      ) {
        try {
          mediaRecorderRef.current.stop();
        } catch { /* ignore */ }
      }
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  return {
    state,
    transcript,
    error,
    isRecording: state === "recording",
    isBusy: state === "uploading" || state === "transcribing",
    isSupported,
    startRecording,
    stopRecording,
    reset,
  };
}
