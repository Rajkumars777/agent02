import { useEffect, useRef } from 'react';
import { getApiBase } from '@/lib/api';

export type WebSocketEvent = {
    task_id: string;
    type: string;
    data: Record<string, unknown>;
    timestamp: number;
};

/**
 * Connects a WebSocket for the given taskId and calls onEvent for each message.
 *
 * Root cause fix: onEvent is stored in a ref so that changing the callback
 * (which happens on every render in the parent) does NOT cause the WebSocket
 * to disconnect and reconnect. The connection only changes when taskId changes.
 */
export function useWebsocket(
    taskId: string | null,
    onEvent?: (event: WebSocketEvent) => void
) {
    const wsRef = useRef<WebSocket | null>(null);
    // Stable ref for the callback — updated every render without triggering reconnects
    const onEventRef = useRef(onEvent);
    useEffect(() => {
        onEventRef.current = onEvent;
    });

    useEffect(() => {
        if (!taskId) return;

        let cancelled = false;

        async function connect() {
            try {
                const base = await getApiBase();
                if (cancelled) return;

                const wsUrl = base.replace(/^http/, 'ws') + `/ws/${taskId}`;
                const ws = new WebSocket(wsUrl);
                wsRef.current = ws;

                ws.onopen = () => {
                    if (!cancelled) console.log(`WS: Connected to ${taskId}`);
                };

                ws.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data) as WebSocketEvent;
                        onEventRef.current?.(data);
                    } catch (e) {
                        console.error('WS: Parse error', e);
                    }
                };

                ws.onerror = (e) => {
                    console.error(`WS: Error for task ${taskId}`, e);
                };

                ws.onclose = () => {
                    if (!cancelled) console.log(`WS: Disconnected from ${taskId}`);
                    wsRef.current = null;
                };
            } catch (e) {
                console.error('WS: Connection error', e);
            }
        }

        connect();

        return () => {
            cancelled = true;
            if (wsRef.current) {
                wsRef.current.close();
                wsRef.current = null;
            }
        };
    }, [taskId]); // ← only reconnect when taskId changes, NOT on every callback change
}
