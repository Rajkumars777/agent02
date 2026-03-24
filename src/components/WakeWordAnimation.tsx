/**
 * Wake Word Animation
 * Visual feedback when wake word is detected
 */

import React, { useEffect, useState } from 'react';
import { Volume2 } from 'lucide-react';

interface WakeWordAnimationProps {
    isDetected: boolean;
    wakeWord: string;
}

export const WakeWordAnimation: React.FC<WakeWordAnimationProps> = ({
    isDetected,
    wakeWord,
}) => {
    const [show, setShow] = useState(false);

    useEffect(() => {
        if (isDetected) {
            setShow(true);
            // Auto-hide after 2 seconds
            const timer = setTimeout(() => setShow(false), 2000);
            return () => clearTimeout(timer);
        }
    }, [isDetected]);

    if (!show) return null;

    return (
        <div className="fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 z-50">
            <div className="bg-blue-500 text-white px-8 py-4 rounded-lg shadow-2xl animate-bounce">
                <div className="flex items-center gap-3">
                    <Volume2 size={32} className="animate-pulse" />
                    <div>
                        <div className="text-xl font-bold">Wake Word Detected!</div>
                        <div className="text-sm opacity-90">&quot;{wakeWord}&quot;</div>
                    </div>
                </div>
            </div>
        </div>
    );
};
