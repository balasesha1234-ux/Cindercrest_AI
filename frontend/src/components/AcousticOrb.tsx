import React from 'react';
import { VoiceState } from '../types/api';

interface AcousticOrbProps {
  state: VoiceState;
  privacyMode: boolean;
  audioLevel: number; // 0.0 to 1.0 real microphone amplitude
  onClick: () => void;
  isSubmitting: boolean;
}

export const AcousticOrb: React.FC<AcousticOrbProps> = ({
  state,
  privacyMode,
  audioLevel,
  onClick,
  isSubmitting,
}) => {
  // Compute dynamic scale and glow based on real microphone audio amplitude
  const dynamicScale = state === 'LISTENING' && audioLevel > 0.02 ? 1 + audioLevel * 0.45 : 1;
  const dynamicGlow = state === 'LISTENING' && audioLevel > 0.02 ? Math.min(audioLevel * 35, 30) : 10;

  const getTooltip = () => {
    if (privacyMode) return 'Microphone muted in Privacy Mode';
    if (state === 'SPEAKING') return 'Click to interrupt speech (Barge-In)';
    if (state === 'LISTENING') return 'Click to stop listening';
    if (state === 'PROCESSING' || isSubmitting) return 'Processing conversational response...';
    return 'Click to start speaking';
  };

  const getStateAuraClass = () => {
    if (privacyMode) return 'orb-privacy';
    switch (state) {
      case 'LISTENING':
        return 'orb-listening';
      case 'PROCESSING':
        return 'orb-processing';
      case 'SPEAKING':
        return 'orb-speaking';
      case 'INTERRUPTED':
        return 'orb-interrupted';
      default:
        return 'orb-idle';
    }
  };

  return (
    <div className="orb-wrapper" onClick={onClick} title={getTooltip()} role="button" tabIndex={0}>
      {/* Outer ambient atmospheric pulse */}
      <div
        className={`orb-atmosphere ${getStateAuraClass()}`}
        style={{
          transform: `scale(${dynamicScale * 1.15})`,
          opacity: state === 'LISTENING' ? 0.35 + audioLevel * 0.5 : 0.25,
        }}
      />

      {/* Dynamic secondary resonance ring */}
      <div
        className={`orb-ring ${getStateAuraClass()}`}
        style={{
          transform: `scale(${dynamicScale})`,
          boxShadow: `0 0 ${dynamicGlow}px currentColor`,
        }}
      />

      {/* Central crystalline core */}
      <div
        className={`orb-core ${getStateAuraClass()}`}
        style={{
          transform: `scale(${state === 'LISTENING' ? 1 + audioLevel * 0.15 : 1})`,
        }}
      >
        <div className="orb-icon">
          {privacyMode ? (
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="1" y1="1" x2="23" y2="23" />
              <path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6" />
              <path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23" />
              <line x1="12" y1="19" x2="12" y2="23" />
              <line x1="8" y1="23" x2="16" y2="23" />
            </svg>
          ) : state === 'LISTENING' ? (
            <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              <line x1="12" y1="19" x2="12" y2="23" />
              <line x1="8" y1="23" x2="16" y2="23" />
            </svg>
          ) : state === 'SPEAKING' ? (
            <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
              <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
              <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
            </svg>
          ) : state === 'PROCESSING' || isSubmitting ? (
            <svg className="spin-slow" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" strokeDasharray="32" strokeDashoffset="16" />
            </svg>
          ) : state === 'INTERRUPTED' ? (
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="6" y="6" width="12" height="12" rx="2" />
            </svg>
          ) : (
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
              <path d="M12 2a4 4 0 0 0-4 4v6a4 4 0 0 0 8 0V6a4 4 0 0 0-4-4z" />
              <path d="M18 10v2a6 6 0 0 1-12 0v-2" />
              <line x1="12" y1="20" x2="12" y2="22" />
              <circle cx="12" cy="12" r="1.5" fill="currentColor" />
            </svg>
          )}
        </div>
      </div>
    </div>
  );
};
