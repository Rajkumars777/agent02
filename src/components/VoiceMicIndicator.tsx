/**
 * Voice Microphone Indicator
 * Visual status indicator for voice interface
 */

import React from 'react';
import { Mic, MicOff, Loader2 } from 'lucide-react';
import { VoiceStatus, getVoiceState, getVoiceStateColor, getVoiceStateLabel } from '../types/voice';

interface VoiceMicIndicatorProps {
    status: VoiceStatus;
    onToggle: () => void;
    size?: 'sm' | 'md' | 'lg';
}

export const VoiceMicIndicator: React.FC<VoiceMicIndicatorProps> = ({
    status,
    onToggle,
    size = 'md',
}) => {
    const state = getVoiceState(status);
    const color = getVoiceStateColor(state);
    const label = getVoiceStateLabel(state);

    const sizeClasses = {
        sm: 'w-8 h-8',
        md: 'w-12 h-12',
        lg: 'w-16 h-16',
    };

    const iconSizes = {
        sm: 16,
        md: 20,
        lg: 24,
    };

    const isActive = status.isEnabled;

    return (
        <div className="flex items-center gap-3">
            {/* Microphone Button */}
            <button
                onClick={onToggle}
                className={`
          ${sizeClasses[size]}
          rounded-full
          flex items-center justify-center
          transition-all duration-200
          shadow-lg
          hover:shadow-xl
          relative
          ${isActive ? 'cursor-pointer' : 'cursor-pointer opacity-60'}
        `}
                style={{
                    backgroundColor: isActive ? color : '#6B7280',
                }}
                title={isActive ? label : 'Click to enable voice mode'}
            >
                {/* Ripple animation when listening */}
                {status.isListening && (
                    <div
                        className="absolute inset-0 rounded-full animate-ping opacity-75"
                        style={{ backgroundColor: color }}
                    />
                )}

                {/* Icon */}
                {status.isProcessing ? (
                    <Loader2 size={iconSizes[size]} className="text-white animate-spin" />
                ) : isActive ? (
                    <Mic size={iconSizes[size]} className="text-white" />
                ) : (
                    <MicOff size={iconSizes[size]} className="text-white" />
                )}

                {/* Recording pulse */}
                {status.isRecording && (
                    <div
                        className="absolute inset-0 rounded-full animate-pulse"
                        style={{ backgroundColor: color, opacity: 0.5 }}
                    />
                )}
            </button>

            {/* Status Label */}
            {isActive && (
                <div className="flex flex-col">
                    <span
                        className="text-sm font-medium"
                        style={{ color }}
                    >
                        {label}
                    </span>
                    {status.currentCommand && (
                        <span className="text-xs text-gray-500">
                            "{status.currentCommand}"
                        </span>
                    )}
                    {status.error && (
                        <span className="text-xs text-red-500">
                            {status.error}
                        </span>
                    )}
                </div>
            )}
        </div>
    );
};
