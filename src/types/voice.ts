/**
 * Voice Status Types
 * Manages voice interface state across the application
 */

export interface VoiceStatus {
    isListening: boolean;      // Listening for wake word
    isRecording: boolean;      // Recording voice command
    isProcessing: boolean;     // Processing command
    isSpeaking: boolean;       // Speaking response
    wakeWordDetected: boolean; // Wake word just detected
    isEnabled: boolean;        // Voice mode enabled
    currentCommand?: string;   // Current/last command
    error?: string;            // Error message if any
}

export type VoiceState = 'idle' | 'listening' | 'recording' | 'processing' | 'speaking' | 'error';

export interface VoiceConfig {
    wakeWord: string;          // e.g., "jarvis"
    voice: string;             // TTS voice ID
    useLocalTTS: boolean;      // Local vs cloud TTS
    sensitivity: number;       // Wake word sensitivity
}

export const defaultVoiceStatus: VoiceStatus = {
    isListening: false,
    isRecording: false,
    isProcessing: false,
    isSpeaking: false,
    wakeWordDetected: false,
    isEnabled: false,
};

export const defaultVoiceConfig: VoiceConfig = {
    wakeWord: 'jarvis',
    voice: 'af_sarah',
    useLocalTTS: true,
    sensitivity: 0.5,
};

/**
 * Get current voice state from status
 */
export function getVoiceState(status: VoiceStatus): VoiceState {
    if (status.error) return 'error';
    if (status.isSpeaking) return 'speaking';
    if (status.isProcessing) return 'processing';
    if (status.isRecording) return 'recording';
    if (status.isListening) return 'listening';
    return 'idle';
}

/**
 * Get color for current voice state
 */
export function getVoiceStateColor(state: VoiceState): string {
    switch (state) {
        case 'listening': return '#3B82F6'; // Blue
        case 'recording': return '#EF4444'; // Red
        case 'processing': return '#F59E0B'; // Yellow
        case 'speaking': return '#10B981'; // Green
        case 'error': return '#DC2626'; // Dark red
        default: return '#6B7280'; // Gray
    }
}

/**
 * Get label for current voice state
 */
export function getVoiceStateLabel(state: VoiceState): string {
    switch (state) {
        case 'listening': return 'Listening for wake word...';
        case 'recording': return 'Recording command...';
        case 'processing': return 'Processing...';
        case 'speaking': return 'Speaking response...';
        case 'error': return 'Error';
        default: return 'Voice inactive';
    }
}
