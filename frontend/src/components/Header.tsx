import React from 'react';
import { HealthResponse } from '../types/api';

interface HeaderProps {
  connectionStatus: 'connected' | 'disconnected' | 'probing';
  healthData: HealthResponse | null;
  latencyMs: number | null;
  selectedProvider: string;
  isMicActive: boolean;
  privacyMode: boolean;
  historyCount: number;
  personalityMode: string;
  onCycleMode: () => void;
  onTogglePrivacy: () => void;
  onToggleHistory: () => void;
  onToggleTasks: () => void;
  onToggleMemory: () => void;
  onToggleSettings: () => void;
  isHistoryOpen: boolean;
  isTasksOpen: boolean;
  isMemoryOpen: boolean;
  isSettingsOpen: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  connectionStatus,
  healthData,
  latencyMs,
  selectedProvider,
  isMicActive,
  privacyMode,
  historyCount,
  personalityMode,
  onCycleMode,
  onTogglePrivacy,
  onToggleHistory,
  onToggleTasks,
  onToggleMemory,
  onToggleSettings,
  isHistoryOpen,
  isTasksOpen,
  isMemoryOpen,
  isSettingsOpen,
}) => {
  const isOllamaOnline = healthData?.checks.ollama.status === 'ok';

  return (
    <header className="system-header">
      {/* Brand & Identity */}
      <div className="brand-group">
        <div className="brand-mark">
          <span className="brand-glyph">✦</span>
          <span className="brand-name">CINDERCREST</span>
          <span className="brand-version">2.0</span>
        </div>
        <div className="system-status-indicator">
          <span className={`status-dot ${connectionStatus}`} />
          <span className="status-label">
            {connectionStatus === 'connected' ? 'CORE ONLINE' : connectionStatus === 'probing' ? 'PROBING' : 'OFFLINE'}
          </span>
          {latencyMs !== null && <span className="status-latency">{latencyMs}ms</span>}
        </div>
      </div>

      {/* Center Telemetry Readouts */}
      <div className="telemetry-group">
        {/* Model Indicator */}
        <div className="telemetry-chip" title={`Current LLM Provider: ${selectedProvider}`}>
          <span className="chip-label">MODEL</span>
          <span className={`chip-status-dot ${selectedProvider === 'ollama' ? (isOllamaOnline ? 'active' : 'warn') : 'active'}`} />
          <span className="chip-value">
            {selectedProvider === 'ollama' ? 'QWEN 3 (8B)' : 'GROQ (QWEN 3.8)'}
          </span>
        </div>

        {/* Personality Mode Indicator */}
        <div
          className="telemetry-chip"
          title={`Active Personality Demeanor: ${personalityMode.toUpperCase()} (Click to cycle)`}
          style={{ cursor: 'pointer' }}
          onClick={onCycleMode}
        >
          <span className="chip-label">MODE</span>
          <span className="chip-status-dot active" />
          <span className="chip-value">{personalityMode.toUpperCase()}</span>
        </div>

        {/* Microphone Indicator */}
        <div className="telemetry-chip" title="Hardware Microphone Status">
          <span className="chip-label">AUDIO IN</span>
          <span className={`chip-status-dot ${privacyMode ? 'muted' : isMicActive ? 'live' : 'standby'}`} />
          <span className="chip-value">
            {privacyMode ? 'MUTED' : isMicActive ? 'CAPTURING' : 'STANDBY'}
          </span>
        </div>
      </div>

      {/* Control Actions */}
      <div className="header-actions">
        {/* Privacy Shield Toggle */}
        <button
          onClick={onTogglePrivacy}
          className={`btn-header-action ${privacyMode ? 'active-privacy' : ''}`}
          title={privacyMode ? 'Privacy Mode is Active (Mic disconnected)' : 'Enable Privacy Mode'}
        >
          <span className="action-icon">{privacyMode ? '🛡️' : '🛡️'}</span>
          <span className="action-text">{privacyMode ? 'PRIVACY MUTED' : 'PRIVACY'}</span>
        </button>

        {/* Conversation History Drawer Button */}
        <button
          onClick={onToggleHistory}
          className={`btn-header-action ${isHistoryOpen ? 'active' : ''}`}
          title="Toggle Conversation Transcript History"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
          <span className="action-text">LOG</span>
          {historyCount > 0 && <span className="action-badge">{historyCount}</span>}
        </button>

        {/* Agent Brain Tasks Drawer Button */}
        <button
          onClick={onToggleTasks}
          className={`btn-header-action ${isTasksOpen ? 'active' : ''}`}
          title="Toggle Agent Brain & Tasks"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="9 11 12 14 22 4" />
            <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
          </svg>
          <span className="action-text">TASKS</span>
        </button>

        {/* Controlled Memory Drawer Button */}
        <button
          onClick={onToggleMemory}
          className={`btn-header-action ${isMemoryOpen ? 'active' : ''}`}
          title="Inspect & Manage Controlled Memory"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 2a4 4 0 0 0-4 4v1a4 4 0 0 0-4 4 4 4 0 0 0 4 4v1a4 4 0 0 0 4 4 4 4 0 0 0 4-4v-1a4 4 0 0 0 4-4 4 4 0 0 0-4-4V6a4 4 0 0 0-4-4z" />
          </svg>
          <span className="action-text">MEMORY</span>
        </button>

        {/* Settings Drawer Button */}
        <button
          onClick={onToggleSettings}
          className={`btn-header-action ${isSettingsOpen ? 'active' : ''}`}
          title="Open Settings and Diagnostics"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
        </button>
      </div>
    </header>
  );
};
