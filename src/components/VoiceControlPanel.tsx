/**
 * Voice Control Panel
 * Complete voice interface controls and settings
 */

import React, { useState } from 'react';
import { Settings, X } from 'lucide-react';
import { VoiceConfig, defaultVoiceConfig } from '../types/voice';

interface VoiceControlPanelProps {
    config: VoiceConfig;
    onConfigChange: (config: VoiceConfig) => void;
}

export const VoiceControlPanel: React.FC<VoiceControlPanelProps> = ({
    config,
    onConfigChange,
}) => {
    const [isOpen, setIsOpen] = useState(false);

    const wakeWords = ['jarvis', 'computer', 'alexa', 'hey google', 'picovoice'];
    const voices = [
        { id: 'af_sarah', name: 'Sarah (Female, Professional)' },
        { id: 'af_bella', name: 'Bella (Female, Warm)' },
        { id: 'am_adam', name: 'Adam (Male, Clear)' },
        { id: 'am_michael', name: 'Michael (Male, Deep)' },
    ];

    return (
        <div className="relative">
            {/* Settings Button */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
                title="Voice Settings"
            >
                <Settings size={20} className="text-gray-600 dark:text-gray-400" />
            </button>

            {/* Settings Panel */}
            {isOpen && (
                <div className="absolute right-0 top-12 w-80 bg-white dark:bg-gray-800 rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 p-4 z-50">
                    {/* Header */}
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-lg font-semibold">Voice Settings</h3>
                        <button
                            onClick={() => setIsOpen(false)}
                            className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                        >
                            <X size={18} />
                        </button>
                    </div>

                    {/* Wake Word */}
                    <div className="mb-4">
                        <label className="block text-sm font-medium mb-2">Wake Word</label>
                        <select
                            value={config.wakeWord}
                            onChange={(e) => onConfigChange({ ...config, wakeWord: e.target.value })}
                            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700"
                        >
                            {wakeWords.map((word) => (
                                <option key={word} value={word}>
                                    {word}
                                </option>
                            ))}
                        </select>
                    </div>

                    {/* Voice */}
                    <div className="mb-4">
                        <label className="block text-sm font-medium mb-2">Voice</label>
                        <select
                            value={config.voice}
                            onChange={(e) => onConfigChange({ ...config, voice: e.target.value })}
                            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700"
                        >
                            {voices.map((voice) => (
                                <option key={voice.id} value={voice.id}>
                                    {voice.name}
                                </option>
                            ))}
                        </select>
                    </div>

                    {/* TTS Mode */}
                    <div className="mb-4">
                        <label className="block text-sm font-medium mb-2">TTS Engine</label>
                        <div className="flex gap-2">
                            <button
                                onClick={() => onConfigChange({ ...config, useLocalTTS: true })}
                                className={`flex-1 px-3 py-2 rounded-lg ${config.useLocalTTS
                                        ? 'bg-blue-500 text-white'
                                        : 'bg-gray-100 dark:bg-gray-700'
                                    }`}
                            >
                                Local (Free)
                            </button>
                            <button
                                onClick={() => onConfigChange({ ...config, useLocalTTS: false })}
                                className={`flex-1 px-3 py-2 rounded-lg ${!config.useLocalTTS
                                        ? 'bg-blue-500 text-white'
                                        : 'bg-gray-100 dark:bg-gray-700'
                                    }`}
                            >
                                Cloud (Premium)
                            </button>
                        </div>
                    </div>

                    {/* Sensitivity */}
                    <div className="mb-4">
                        <label className="block text-sm font-medium mb-2">
                            Sensitivity: {config.sensitivity.toFixed(1)}
                        </label>
                        <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.1"
                            value={config.sensitivity}
                            onChange={(e) =>
                                onConfigChange({ ...config, sensitivity: parseFloat(e.target.value) })
                            }
                            className="w-full"
                        />
                        <div className="flex justify-between text-xs text-gray-500 mt-1">
                            <span>Strict</span>
                            <span>Balanced</span>
                            <span>Sensitive</span>
                        </div>
                    </div>

                    {/* Info */}
                    <div className="mt-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg text-sm">
                        <p className="text-blue-700 dark:text-blue-300">
                            💡 Local TTS uses Kokoro-82M (free, offline). Cloud uses ElevenLabs (premium quality).
                        </p>
                    </div>
                </div>
            )}
        </div>
    );
};
