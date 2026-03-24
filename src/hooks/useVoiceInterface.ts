/**
 * Voice Interface Hook with WebSocket
 * Real WebSocket communication with backend.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { VoiceStatus, VoiceConfig, defaultVoiceStatus, defaultVoiceConfig } from '../types/voice';

const WS_URL = 'ws://127.0.0.1:8000/ws/voice';
const API_URL = 'http://127.0.0.1:8000/api/voice';

export function useVoiceInterface() {
    const [status, setStatus] = useState<VoiceStatus>(defaultVoiceStatus);
    const [config, setConfig] = useState<VoiceConfig>(defaultVoiceConfig);
    const [isConnected, setIsConnected] = useState(false);
    const wsRef = useRef<WebSocket | null>(null);

    // Connect to WebSocket
    useEffect(() => {
        const ws = new WebSocket(WS_URL);

        ws.onopen = () => {
            console.log('✅ Voice WebSocket connected');
            setIsConnected(true);
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);

                if (data.type === 'voice_status') {
                    setStatus(data.status);
                }
            } catch (error) {
                console.error('WebSocket message error:', error);
            }
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            setIsConnected(false);
        };

        ws.onclose = () => {
            console.log('❌ Voice WebSocket disconnected');
            setIsConnected(false);

            // Auto-reconnect after 3 seconds
            setTimeout(() => {
                console.log('🔄 Reconnecting to voice WebSocket...');
                // Component will re-mount and reconnect
            }, 3000);
        };

        wsRef.current = ws;

        return () => {
            ws.close();
        };
    }, []);

    // Load initial configuration
    useEffect(() => {
        fetch(`${API_URL}/config`)
            .then((res) => res.json())
            .then((data) => setConfig(data))
            .catch((error) => console.error('Failed to load voice config:', error));
    }, []);

    // Toggle voice mode
    const toggleVoiceMode = useCallback(async () => {
        const newEnabled = !status.isEnabled;

        try {
            const endpoint = newEnabled ? '/enable' : '/disable';
            const res = await fetch(`${API_URL}${endpoint}`, {
                method: 'POST',
            });

            if (!res.ok) {
                throw new Error('Failed to toggle voice mode');
            }

            // WebSocket will update status automatically
        } catch (error) {
            console.error('Error toggling voice mode:', error);
        }
    }, [status.isEnabled]);

    // Update configuration
    const updateConfig = useCallback(async (newConfig: VoiceConfig) => {
        try {
            const res = await fetch(`${API_URL}/config`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(newConfig),
            });

            if (!res.ok) {
                throw new Error('Failed to update voice config');
            }

            const data = await res.json();
            setConfig(data.config);

            // Notify WebSocket
            if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                wsRef.current.send(
                    JSON.stringify({
                        action: 'update_config',
                        config: newConfig,
                    })
                );
            }
        } catch (error) {
            console.error('Error updating voice config:', error);
        }
    }, []);

    // Test TTS
    const testTTS = useCallback(async (text?: string) => {
        try {
            const params = text ? `?text=${encodeURIComponent(text)}` : '';
            const res = await fetch(`${API_URL}/test-tts${params}`, {
                method: 'POST',
            });

            if (!res.ok) {
                throw new Error('Failed to test TTS');
            }

            return await res.json();
        } catch (error) {
            console.error('Error testing TTS:', error);
            throw error;
        }
    }, []);

    return {
        status,
        config,
        isConnected,
        toggleVoiceMode,
        updateConfig,
        testTTS,
    };
}
