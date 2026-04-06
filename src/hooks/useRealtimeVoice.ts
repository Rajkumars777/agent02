"use client";

import { useState, useEffect, useCallback, useRef } from "react";

export type VoiceState = "idle" | "listening" | "thinking" | "speaking" | "error";

interface VoiceHookResult {
  state: VoiceState;
  volume: number; // 0 to 1
  transcription: string;
  response: string;
  error: string | null;
  start: () => Promise<void>;
  stop: () => void;
  isActive: boolean;
}

export function useRealtimeVoice(): VoiceHookResult {
  const [state, setState] = useState<VoiceState>("idle");
  const [volume, setVolume] = useState(0);
  const [transcription, setTranscription] = useState("");
  const [response, setResponse] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isActive, setIsActive] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const analyzerRef = useRef<AnalyserNode | null>(null);
  const currentTaskId = useRef<string | null>(null);

  // ── Silence Detection Parameters ──
  const SILENCE_THRESHOLD = 0.05; 
  const SILENCE_DURATION = 1500; 
  const lastSpeakTime = useRef<number>(Date.now());
  const isCurrentlySpeaking = useRef<boolean>(false);

  const processSpeech = useCallback((taskId: string) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: "process", task_id: taskId }));
    }
  }, []);

  const stop = useCallback(() => {
    setIsActive(false);
    setState("idle");
    setVolume(0);
    
    if (wsRef.current) wsRef.current.close();
    if (processorRef.current) processorRef.current.disconnect();
    if (analyzerRef.current) analyzerRef.current.disconnect();
    if (mediaStreamRef.current) mediaStreamRef.current.getTracks().forEach(t => t.stop());
    if (audioContextRef.current) audioContextRef.current.close();

    wsRef.current = null;
    processorRef.current = null;
    analyzerRef.current = null;
    audioContextRef.current = null;
    mediaStreamRef.current = null;
    currentTaskId.current = null;
  }, []);

  const start = useCallback(async () => {
    try {
      setIsActive(true);
      setError(null);
      setState("listening");
      setResponse("");
      setTranscription("");
      
      const sessionTaskId = "voice_" + Date.now();
      currentTaskId.current = sessionTaskId;

      // ── 1. Setup Microphone ──
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;

      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      const audioCtx = new AudioContextClass({ sampleRate: 16000 });
      audioContextRef.current = audioCtx;

      const source = audioCtx.createMediaStreamSource(stream);
      const analyzer = audioCtx.createAnalyser();
      analyzer.fftSize = 256;
      analyzerRef.current = analyzer;
      source.connect(analyzer);

      const dataArray = new Uint8Array(analyzer.frequencyBinCount);
      
      // Volume/VAD loop
      const updateVolume = () => {
        if (!audioContextRef.current) return;
        
        analyzer.getByteFrequencyData(dataArray);
        const avg = dataArray.reduce((p, c) => p + c, 0) / dataArray.length;
        const vol = avg / 128;
        setVolume(vol);

        if (vol > SILENCE_THRESHOLD) {
          lastSpeakTime.current = Date.now();
          isCurrentlySpeaking.current = true;
        } else if (isCurrentlySpeaking.current && (Date.now() - lastSpeakTime.current > SILENCE_DURATION)) {
            isCurrentlySpeaking.current = false;
            processSpeech(currentTaskId.current || sessionTaskId);
        }
        
        requestAnimationFrame(updateVolume);
      };
      requestAnimationFrame(updateVolume);

      // ── 2. Audio Processor ──
      const processor = audioCtx.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;
      source.connect(processor);
      processor.connect(audioCtx.destination);

      // ── 3. WebSocket ──
      const ws = new WebSocket("ws://127.0.0.1:8000/voice/ws/voice");
      wsRef.current = ws;

      processor.onaudioprocess = (e) => {
        if (ws.readyState !== WebSocket.OPEN || !isCurrentlySpeaking.current) return;
        
        const inputData = e.inputBuffer.getChannelData(0);
        const pcmData = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {
          pcmData[i] = Math.max(-1, Math.min(1, inputData[i])) * 0x7FFF;
        }
        ws.send(pcmData.buffer);
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === "status") setState(data.state as VoiceState);
        if (data.type === "transcription") setTranscription(data.text);
        if (data.type === "response") setResponse(data.text);
        if (data.type === "error") {
            setError(data.message);
            setState("error");
        }
      };

      ws.onclose = () => stop();

    } catch (err: any) {
      setError(err.message || "Could not access microphone");
      setState("error");
      setIsActive(false);
    }
  }, [processSpeech, stop]);

  return { state, volume, transcription, response, error, isActive, start, stop };
}
