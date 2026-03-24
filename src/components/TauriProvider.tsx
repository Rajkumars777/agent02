"use client";

import { useEffect, useState, useRef } from "react";
import { setBackendPort } from "@/lib/api";

export default function TauriProvider({
    children,
}: {
    children: React.ReactNode;
}) {
    const [isReady, setIsReady] = useState(false);
    const addLog = (msg: string) => {
        console.log(`[${new Date().toLocaleTimeString()}] ${msg}`);
    };

    useEffect(() => {
        // Check if running in Tauri
        if (typeof window !== "undefined" && (window as any).__TAURI__) {
            const initTauri = async () => {
                addLog("Initializing Tauri...");
                try {
                    // Dynamically import to avoid SSR issues
                    const { Command } = await import("@tauri-apps/plugin-shell");

                    // Start the sidecar
                    addLog("Attempting to spawn sidecar: ai-engine");
                    const command = Command.sidecar("ai-engine");

                    // Listen for stdout/stderr for debugging
                    command.on("close", (data) => {
                        addLog(`❌ Sidecar exited with code ${data.code} signal ${data.signal}`);
                    });
                    command.on("error", (error) => {
                        addLog(`❌ Sidecar error event: ${JSON.stringify(error)}`);
                    });
                    command.stdout.on("data", (line) => {
                        addLog(`[STDOUT] ${line}`);
                    });
                    command.stderr.on("data", (line) => {
                        addLog(`[STDERR] ${line}`);
                    });

                    const child = await command.spawn();
                    addLog(`✅ Sidecar spawned with PID: ${child.pid}`);

                    // Wait for the backend to be ready before resolving
                    addLog("Waiting for backend health check...");
                    // Try root endpoint or health endpoint
                    await waitForBackend(8000, 30, addLog);
                    setBackendPort(8000);
                    setIsReady(true);
                    addLog("Backend ready & port set to 8000");

                } catch (e: any) {
                    addLog(`❌ CRITICAL FAILURE: ${e.toString()}`);
                    console.error("Tauri init failed:", e);
                    // Still set port so API calls don't hang forever
                    setBackendPort(8000);
                    setIsReady(true);
                }
            };

            initTauri();
        } else {
            // Dev/Web mode — backend is already running externally
            setBackendPort(8000);
            setIsReady(true);
        }
    }, []);

    // Always render children
    return <>{children}</>;
}

/**
 * Poll the backend health endpoint until it responds or we time out.
 */
async function waitForBackend(port: number, maxRetries: number, logFn: (msg: string) => void): Promise<void> {
    for (let i = 0; i < maxRetries; i++) {
        try {
            logFn(`Health check attempt ${i + 1}/${maxRetries}...`);
            const res = await fetch(`http://127.0.0.1:${port}/health`, {
                signal: AbortSignal.timeout(1000),
            });
            if (res.ok) {
                logFn("✅ Health check passed!");
                return;
            } else {
                logFn(`⚠️ Health check failed with status: ${res.status}`);
            }
        } catch (e: any) {
            logFn(`⚠️ Health check connection error: ${e.message}`);
        }
        await new Promise((r) => setTimeout(r, 1000));
    }
    logFn("❌ Backend did not respond in time!");
}
