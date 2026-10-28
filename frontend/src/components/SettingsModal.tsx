import React, { useState } from 'react';
import { HealthResponse, ModelStatus } from '../types/api';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  healthData: HealthResponse | null;
  models: ModelStatus[];
  selectedProvider: string;
  onSelectProvider: (providerId: string) => void;
  personalityMode: string;
  onSelectPersonalityMode: (mode: string) => void;
  availableVoices: SpeechSynthesisVoice[];
  selectedVoiceUri: string;
  onSelectVoice: (uri: string) => void;
  speechRate: number;
  onChangeSpeechRate: (rate: number) => void;
  speechPitch: number;
  onChangeSpeechPitch: (pitch: number) => void;
  sessionToken: string;
  onUpdateSessionToken: (token: string) => void;
  isAuthenticated: boolean;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  healthData,
  models,
  selectedProvider,
  onSelectProvider,
  personalityMode,
  onSelectPersonalityMode,
  availableVoices,
  selectedVoiceUri,
  onSelectVoice,
  speechRate,
  onChangeSpeechRate,
  speechPitch,
  onChangeSpeechPitch,
  sessionToken,
  onUpdateSessionToken,
  isAuthenticated,
}) => {
  const [tokenInput, setTokenInput] = useState(sessionToken);

  if (!isOpen) return null;

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="settings-modal" onClick={(e) => e.stopPropagation()}>
        <div className="settings-modal-header">
          <div className="drawer-title">
            <span>⚙️ SYSTEM SETTINGS & TELEMETRY</span>
          </div>
          <button onClick={onClose} className="btn-drawer-close">
            ✕
          </button>
        </div>

        <div className="settings-modal-body">
          {/* Section: Model Configuration */}
          <div className="settings-section">
            <h3 className="section-title">CONVERSATIONAL REASONING MODEL</h3>
            <div className="setting-field">
              <label>Active Provider</label>
              <select
                value={selectedProvider}
                onChange={(e) => onSelectProvider(e.target.value)}
                className="input-select"
              >
                {models.length > 0 ? (
                  models.map((m) => (
                    <option key={m.provider_id} value={m.provider_id}>
                      {m.provider_id.toUpperCase()} ({m.model_name}) {m.is_available ? '✓ Available' : '⚠️ Offline'}
                    </option>
                  ))
                ) : (
                  <>
                    <option value="ollama">Ollama Local (Qwen 3 8B)</option>
                    <option value="groq">Groq Cloud (Qwen 3.8 27B)</option>
                  </>
                )}
              </select>
            </div>
            <p className="setting-hint">
              Local Ollama Qwen3:8b runs with CUDA acceleration on your NVIDIA RTX 5050. No audio or text leaves your machine when using local models.
            </p>
          </div>

          {/* Section: Personality & Proactive Demeanor Mode */}
          <div className="settings-section">
            <h3 className="section-title">PERSONALITY & DEMEANOR MODE</h3>
            <div className="setting-field">
              <label>Active Mode</label>
              <select
                value={personalityMode}
                onChange={(e) => onSelectPersonalityMode(e.target.value)}
                className="input-select"
              >
                <option value="adaptive">Adaptive (Context-responsive, balanced)</option>
                <option value="work">Work (Structured, technical, minimal pleasantries)</option>
                <option value="focus">Focus (Deep concentration, low verbosity, non-critical alerts suppressed)</option>
                <option value="relax">Relax (Friendly banter, warmth, witty companion)</option>
                <option value="coach">Coach (Disciplined, motivational, goal-driven)</option>
                <option value="quiet">Quiet (Minimal spoken words, text-preferred)</option>
                <option value="serious">Serious (Grave, deeply respectful, objective)</option>
              </select>
            </div>
            <p className="setting-hint">
              {personalityMode === 'relax'
                ? 'Relax mode permits friendly banter and light humor. Sensitive distress or medical concerns automatically trigger serious, supportive demeanor.'
                : personalityMode === 'focus'
                ? 'Focus mode defers all low/medium notifications to preserve flow state. Only critical hardware/system alerts can interrupt.'
                : personalityMode === 'quiet'
                ? 'Quiet mode suppresses spoken output and routes alerts to visual queues.'
                : 'Modes calibrate conversational warmth, verbosity, and proactivity without altering core safety boundaries.'}
            </p>
          </div>

          {/* Section: Speech Synthesis */}
          <div className="settings-section">
            <h3 className="section-title">WINDOWS ONECORE SPEECH SYNTHESIZER</h3>
            <div className="setting-field">
              <label>Spoken Voice</label>
              <select
                value={selectedVoiceUri}
                onChange={(e) => onSelectVoice(e.target.value)}
                className="input-select"
              >
                {availableVoices.map((v) => (
                  <option key={v.voiceURI} value={v.voiceURI}>
                    {v.name} ({v.lang})
                  </option>
                ))}
              </select>
            </div>

            <div className="slider-row">
              <div className="slider-item">
                <div className="slider-label">
                  <span>Playback Rate</span>
                  <span className="slider-val">{speechRate.toFixed(1)}x</span>
                </div>
                <input
                  type="range"
                  min="0.8"
                  max="1.4"
                  step="0.05"
                  value={speechRate}
                  onChange={(e) => onChangeSpeechRate(parseFloat(e.target.value))}
                  className="input-range"
                />
              </div>

              <div className="slider-item">
                <div className="slider-label">
                  <span>Pitch</span>
                  <span className="slider-val">{speechPitch.toFixed(1)}</span>
                </div>
                <input
                  type="range"
                  min="0.8"
                  max="1.2"
                  step="0.05"
                  value={speechPitch}
                  onChange={(e) => onChangeSpeechPitch(parseFloat(e.target.value))}
                  className="input-range"
                />
              </div>
            </div>
          </div>

          {/* Section: Session Authentication */}
          <div className="settings-section">
            <h3 className="section-title">SESSION SECURITY & TOKEN</h3>
            <div className="setting-field">
              <label>Per-Launch Bearer Token</label>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="text"
                  placeholder="Paste session token from backend startup..."
                  value={tokenInput}
                  onChange={(e) => setTokenInput(e.target.value)}
                  className="input-text"
                />
                <button
                  onClick={() => onUpdateSessionToken(tokenInput)}
                  className="btn-primary"
                  style={{ whiteSpace: 'nowrap' }}
                >
                  Apply
                </button>
              </div>
            </div>
            <div className="token-status">
              Status:{' '}
              <span className={isAuthenticated ? 'text-green' : 'text-red'}>
                {isAuthenticated ? 'Authenticated & Bound' : 'Unauthenticated (Paste token from startup)'}
              </span>
            </div>
          </div>

          {/* Section: Subsystem Diagnostics */}
          <div className="settings-section">
            <h3 className="section-title">SUBSYSTEM STATUS TELEMETRY</h3>
            <div className="diagnostic-grid">
              <div className="diag-item">
                <span className="diag-key">FastAPI Spine:</span>
                <span className={`diag-val ${healthData?.status === 'healthy' ? 'text-green' : 'text-red'}`}>
                  {healthData?.status || 'Unknown'}
                </span>
              </div>
              <div className="diag-item">
                <span className="diag-key">SQLite (WAL):</span>
                <span className={`diag-val ${healthData?.checks.database.status === 'ok' ? 'text-green' : 'text-red'}`}>
                  {healthData?.checks.database.status || 'Checking...'}
                </span>
              </div>
              <div className="diag-item">
                <span className="diag-key">Ollama Service:</span>
                <span className={`diag-val ${healthData?.checks.ollama.status === 'ok' ? 'text-green' : 'text-amber'}`}>
                  {healthData?.checks.ollama.status || 'Unreachable'}
                </span>
              </div>
              <div className="diag-item">
                <span className="diag-key">Policy Engine:</span>
                <span className="diag-val text-cyan">DEFAULT-DENY</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
