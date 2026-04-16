// Backend port discovery for Tauri sidecar architecture
let resolvedApiBase: string | null = null;
let portResolve: ((url: string) => void) | null = null;
const portPromise = new Promise<string>((resolve) => { portResolve = resolve; });

// Called by TauriProvider once the backend is confirmed ready
export function setBackendPort(port: number) {
    resolvedApiBase = `http://127.0.0.1:${port}`;
    if (portResolve) portResolve(resolvedApiBase);
}

export async function getApiBase(): Promise<string> {
    if (resolvedApiBase) return resolvedApiBase;

    // Fallback for web-only development
    if (typeof window !== "undefined") {
        resolvedApiBase = "http://127.0.0.1:8000";
        return resolvedApiBase;
    }

    return portPromise;
}

/**
 * Throws a descriptive error if the HTTP response is not OK.
 * Tries to extract JSON { detail } message from FastAPI error bodies.
 */
async function checkResponse(res: Response): Promise<Response> {
    if (!res.ok) {
        let detail = `HTTP ${res.status} ${res.statusText}`;
        try {
            const body = await res.json();
            if (body?.detail) detail = String(body.detail);
            else if (body?.message) detail = String(body.message);
            else if (typeof body === "string") detail = body;
        } catch {
            // Body is not JSON — use status text
        }
        throw new Error(detail);
    }
    return res;
}

// Store active abort controllers for cancellation
let currentAbortController: AbortController | null = null;
let currentTaskId: string | null = null;

export function generateTaskId(): string {
    return `task_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

export function getCurrentTaskId(): string | null {
    return currentTaskId;
}

export async function fetchHealth() {
    const base = await getApiBase();
    const res = await fetch(`${base}/`);
    await checkResponse(res);
    return res.json();
}

export async function chatWithAgent(message: string, taskId?: string, files?: any[], useWeb?: boolean) {
    // Cancel any previous request
    if (currentAbortController) {
        currentAbortController.abort();
    }

    currentAbortController = new AbortController();
    currentTaskId = taskId || generateTaskId();

    try {
        const base = await getApiBase();
        const payload = { 
            input: message, 
            task_id: currentTaskId,
            files: files,
            use_web: useWeb
        };
        const res = await fetch(`${base}/agent/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
            signal: currentAbortController.signal
        });
        await checkResponse(res);
        return res.json();
    } catch (error: unknown) {
        if (error instanceof Error && error.name === 'AbortError') {
            return { cancelled: true, task_id: currentTaskId, steps: [] };
        }
        throw error;
    } finally {
        currentAbortController = null;
    }
}

export async function cancelOperation(): Promise<boolean> {
    // First, abort the fetch request
    if (currentAbortController) {
        currentAbortController.abort();
        currentAbortController = null;
    }

    // Then notify the backend
    if (currentTaskId) {
        try {
            const base = await getApiBase();
            const res = await fetch(`${base}/agent/cancel`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ task_id: currentTaskId })
            });
            currentTaskId = null;
            return res.ok;
        } catch {
            return false;
        }
    }
    return true;
}

export async function listFiles(directory: string = ".") {
    const base = await getApiBase();
    const res = await fetch(`${base}/tools/files?directory=${encodeURIComponent(directory)}`);
    await checkResponse(res);
    return res.json();
}

export async function resumeTask(taskId: string, data: unknown) {
    const base = await getApiBase();
    const res = await fetch(`${base}/agent/resume`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_id: taskId, data }),
    });
    await checkResponse(res);
    return res.json();
}

export async function browseUrl(url: string) {
    const base = await getApiBase();
    const res = await fetch(`${base}/tools/browser/browse`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
    });
    await checkResponse(res);
    return res.json();
}

// ── Settings API ──────────────────────────────────────────────────────────

export async function getSettings() {
    const base = await getApiBase();
    const res = await fetch(`${base}/agent/settings`);
    await checkResponse(res);
    return res.json();
}

export async function saveSettings(settings: Record<string, string>) {
    const base = await getApiBase();
    const res = await fetch(`${base}/agent/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
    });
    await checkResponse(res);
    return res.json();
}

// ── OpenClaw Gateway API ──────────────────────────────────────────────────

export async function startOpenClawGateway(port?: number) {
    const base = await getApiBase();
    const res = await fetch(`${base}/openclaw/gateway/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(port ? { port } : {}),
    });
    await checkResponse(res);
    return res.json();
}

export async function stopOpenClawGateway() {
    const base = await getApiBase();
    const res = await fetch(`${base}/openclaw/gateway/stop`, { method: "POST" });
    await checkResponse(res);
    return res.json();
}

export async function getOpenClawStatus() {
    const base = await getApiBase();
    const res = await fetch(`${base}/openclaw/status`);
    await checkResponse(res);
    return res.json();
}

export async function pairOpenClawChannel(channel: string) {
    const base = await getApiBase();
    const res = await fetch(`${base}/openclaw/channel/pair`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ channel }),
    });
    await checkResponse(res);
    return res.json();
}

export async function logoutOpenClawChannel(channel: string) {
    const base = await getApiBase();
    const res = await fetch(`${base}/openclaw/channel/logout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ channel }),
    });
    await checkResponse(res);
    return res.json();
}

export async function getOpenClawConfig() {
    const base = await getApiBase();
    const res = await fetch(`${base}/openclaw/config`);
    await checkResponse(res);
    return res.json();
}

export async function saveOpenClawConfig(config: unknown) {
    const base = await getApiBase();
    const res = await fetch(`${base}/openclaw/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
    });
    await checkResponse(res);
    return res.json();
}
export async function getHistory() {
    try {
        const base = await getApiBase();
        const res = await fetch(`${base}/agent/history`);
        if (!res.ok) return { history: [] };
        await checkResponse(res);
        return res.json();
    } catch {
        return { history: [] };
    }
}

export async function saveHistory(history: string[]) {
    const base = await getApiBase();
    const res = await fetch(`${base}/agent/history`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ history }),
    });
    await checkResponse(res);
    return res.json();
}

export async function getFolders() {
    try {
        const base = await getApiBase();
        const res = await fetch(`${base}/agent/folders`);
        if (!res.ok) return { folders: [] };
        await checkResponse(res);
        return res.json();
    } catch {
        return { folders: [] };
    }
}

export async function saveFolders(folders: any[]) {
    const base = await getApiBase();
    const res = await fetch(`${base}/agent/folders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folders }),
    });
    await checkResponse(res);
    return res.json();
}

export async function openPath(path: string) {
    const base = await getApiBase();
    const res = await fetch(`${base}/tools/desktop/open-path`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path }),
    });
    await checkResponse(res);
    return res.json();
}

export async function getSystemInfo() {
    const base = await getApiBase();
    const res = await fetch(`${base}/system/info`);
    await checkResponse(res);
    return res.json();
}

export async function getBrowsers() {
    const base = await getApiBase();
    const res = await fetch(`${base}/agent/browsers`);
    await checkResponse(res);
    return res.json();
}
