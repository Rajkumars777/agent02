"use client";

import React, { useEffect, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

interface VoiceAuraProps {
  volume: number; // 0 to 1
  state: "idle" | "listening" | "thinking" | "speaking" | "error";
  size?: number;
}

export function VoiceAura({ volume, state, size = 300 }: VoiceAuraProps) {
  // Map state to colors
  const colors = useMemo(() => {
    switch (state) {
      case "listening": return ["#6366f1", "#a855f7", "#ec4899"]; // Indigo -> Purple -> Pink
      case "thinking": return ["#f59e0b", "#ef4444", "#f59e0b"]; // Amber -> Red -> Amber
      case "speaking": return ["#10b981", "#3b82f6", "#10b981"]; // Emerald -> Blue -> Emerald
      case "error": return ["#ef4444", "#7f1d1d", "#ef4444"]; // Red -> Dark Red
      default: return ["#94a3b8", "#475569", "#94a3b8"]; // Slate
    }
  }, [state]);

  // Derived intensity based on volume (for listening)
  const pulseScale = state === "listening" ? 1 + volume * 0.4 : 1;
  const glowIntensity = state === "listening" ? 0.3 + volume * 0.6 : 0.3;

  return (
    <div 
      className="relative flex items-center justify-center pointer-events-none"
      style={{ width: size, height: size }}
    >
      {/* ── Ambient Glow Background ── */}
      <motion.div
        animate={{
          scale: [1, 1.1, 1],
          opacity: [0.1, 0.2, 0.1],
        }}
        transition={{
          duration: 4,
          repeat: Infinity,
          ease: "easeInOut"
        }}
        className="absolute inset-0 rounded-full blur-3xl"
        style={{ background: colors[0] }}
      />

      {/* ── Outer Ring (Pulsing) ── */}
      <AnimatePresence>
        <motion.div
          key={state + "-outer"}
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{
            opacity: glowIntensity * 0.4,
            scale: pulseScale * 1.2,
            rotate: state === "thinking" ? 360 : 0
          }}
          transition={{
            type: "spring",
            stiffness: 100,
            damping: 15,
            rotate: state === "thinking" ? { duration: 3, repeat: Infinity, ease: "linear" } : {}
          }}
          className="absolute inset-0 border-2 rounded-full opacity-20"
          style={{ 
            borderColor: colors[1],
            boxShadow: `0 0 40px ${colors[1]}80`
          }}
        />
      </AnimatePresence>

      {/* ── Core Aura (Fluid Shape) ── */}
      <motion.div
        animate={{
          borderRadius: ["40% 60% 70% 30% / 40% 50% 60% 50%", "60% 40% 30% 70% / 60% 40% 60% 40%", "40% 60% 70% 30% / 40% 50% 60% 50%"],
          scale: pulseScale,
        }}
        transition={{
          duration: 6,
          repeat: Infinity,
          ease: "easeInOut"
        }}
        className="relative w-1/2 h-1/2 flex items-center justify-center backdrop-blur-xl border border-white/20 shadow-2xl overflow-hidden"
        style={{
          background: `radial-gradient(circle at center, ${colors[0]}, ${colors[1]})`,
        }}
      >
        {/* Animated Internal Mesh */}
        <div className="absolute inset-0 opacity-40">
           <motion.div 
             animate={{ x: [-20, 20, -20], y: [-20, 20, -20] }}
             transition={{ duration: 10, repeat: Infinity }}
             className="absolute inset-[-100%] bg-gradient-to-br from-white/20 via-transparent to-black/20" 
           />
        </div>

        {/* Center Indicator */}
        <div className="z-10 w-4 h-4 rounded-full bg-white/90 shadow-[0_0_15px_white]" />
      </motion.div>

      {/* ── Particle Rings (Reactive) ── */}
      {state === "listening" && volume > 0.1 && (
        <motion.div
           initial={{ scale: 0.5, opacity: 0 }}
           animate={{ scale: pulseScale * 1.5, opacity: 0 }}
           transition={{ duration: 0.8, repeat: Infinity, ease: "easeOut" }}
           className="absolute w-2/3 h-2/3 border border-white/40 rounded-full"
        />
      )}
    </div>
  );
}
