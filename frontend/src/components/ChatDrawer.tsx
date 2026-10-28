import React from 'react';
import { ConversationTurn } from '../types/api';

interface ChatDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  turns: ConversationTurn[];
  onResetHistory: () => void;
}

export const ChatDrawer: React.FC<ChatDrawerProps> = ({
  isOpen,
  onClose,
  turns,
  onResetHistory,
}) => {
  if (!isOpen) return null;

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer-panel" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-header">
          <div className="drawer-title">
            <span className="drawer-icon">📜</span>
            <span>SESSION TRANSCRIPT LOG</span>
          </div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            {turns.length > 0 && (
              <button
                onClick={onResetHistory}
                className="btn-drawer-action"
                title="Clear current session turns from memory"
              >
                Clear History
              </button>
            )}
            <button onClick={onClose} className="btn-drawer-close" title="Close Transcript Drawer">
              ✕
            </button>
          </div>
        </div>

        <div className="drawer-content">
          {turns.length === 0 ? (
            <div className="drawer-empty">
              <span>No conversational turns recorded in this session.</span>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Speak into the microphone or type below to begin.
              </span>
            </div>
          ) : (
            turns.map((turn, idx) => (
              <div key={idx} className={`transcript-row ${turn.role}`}>
                <div className="transcript-meta">
                  <span className="transcript-speaker">
                    {turn.role === 'user' ? 'YOU' : 'CINDERCREST'}
                  </span>
                  <span className="transcript-time">
                    {new Date(turn.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </span>
                  {turn.latency_ms && (
                    <span className="transcript-latency">{Math.round(turn.latency_ms)}ms</span>
                  )}
                </div>
                <div className="transcript-body">{turn.content}</div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
