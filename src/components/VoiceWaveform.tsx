/**
 * Voice Waveform
 * Animated waveform for speaking state
 */

import React from 'react';

interface VoiceWaveformProps {
    isActive: boolean;
    color?: string;
}

export const VoiceWaveform: React.FC<VoiceWaveformProps> = ({
    isActive,
    color = '#10B981',
}) => {
    const bars = 5;

    return (
        <div className="flex items-center gap-1 h-8">
            {Array.from({ length: bars }).map((_, i) => (
                <div
                    key={i}
                    className={`w-1 rounded-full transition-all ${isActive ? 'animate-wave' : ''
                        }`}
                    style={{
                        backgroundColor: color,
                        height: isActive ? '100%' : '20%',
                        animationDelay: `${i * 0.1}s`,
                    }}
                />
            ))}
        </div>
    );
};
