import React, { useState, useEffect, useCallback } from 'react';
import { MemoryItem, MemoryCategory, CreateMemoryRequest } from '../types/api';
import { apiClient } from '../api/client';

interface MemoryDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  token: string;
  privacyMode: boolean;
}

export const MemoryDrawer: React.FC<MemoryDrawerProps> = ({
  isOpen,
  onClose,
  token,
  privacyMode,
}) => {
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Form states for adding new memory
  const [isAdding, setIsAdding] = useState<boolean>(false);
  const [newCategory, setNewCategory] = useState<MemoryCategory>('explicit_fact');
  const [newKey, setNewKey] = useState<string>('');
  const [newContent, setNewContent] = useState<string>('');

  // Editing / correcting state
  const [correctingId, setCorrectingId] = useState<string | null>(null);
  const [correctedContent, setCorrectedContent] = useState<string>('');

  const fetchMemories = useCallback(async () => {
    if (!token || !isOpen) return;
    setIsLoading(true);
    setError(null);
    try {
      if (searchQuery.trim()) {
        const results = await apiClient.searchMemories(token, searchQuery.trim());
        setMemories(results);
      } else {
        const cat = selectedCategory === 'all' ? undefined : selectedCategory;
        const results = await apiClient.listMemories(token, cat, 'active');
        setMemories(results);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load memories');
    } finally {
      setIsLoading(false);
    }
  }, [token, isOpen, selectedCategory, searchQuery]);

  useEffect(() => {
    fetchMemories();
  }, [fetchMemories]);

  const handleCreateMemory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKey.trim() || !newContent.trim()) return;
    try {
      const payload: CreateMemoryRequest = {
        category: newCategory,
        key: newKey.trim(),
        content: newContent.trim(),
        confidence: newCategory === 'inference' ? 0.8 : 1.0,
        provenance: 'user_explicit',
      };
      await apiClient.createMemory(token, payload);
      setNewKey('');
      setNewContent('');
      setIsAdding(false);
      await fetchMemories();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create memory');
    }
  };

  const handleCorrectMemory = async (memoryId: string) => {
    if (!correctedContent.trim()) return;
    try {
      await apiClient.correctMemory(token, memoryId, {
        content: correctedContent.trim(),
        provenance: 'user_correction',
      });
      setCorrectingId(null);
      setCorrectedContent('');
      await fetchMemories();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to correct memory');
    }
  };

  const handleDeleteMemory = async (memoryId: string) => {
    try {
      await apiClient.deleteMemory(token, memoryId);
      await fetchMemories();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to delete memory');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer-panel memory-drawer" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="drawer-header">
          <div className="drawer-title">
            <span className="drawer-icon">🧠</span>
            <span>CONTROLLED MEMORY & CONTEXT</span>
          </div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <button
              onClick={() => setIsAdding(!isAdding)}
              className="btn-drawer-action"
              title="Add explicit fact or preference"
            >
              {isAdding ? 'Cancel' : '+ Add Fact'}
            </button>
            <button
              onClick={fetchMemories}
              className="btn-drawer-action"
              title="Refresh memories from SQLite"
            >
              ↻ Refresh
            </button>
            <button onClick={onClose} className="btn-drawer-close" title="Close Drawer">
              ✕
            </button>
          </div>
        </div>

        {/* Privacy Notice Banner if active */}
        {privacyMode && (
          <div
            style={{
              padding: '10px 16px',
              backgroundColor: 'rgba(239, 68, 68, 0.15)',
              borderBottom: '1px solid rgba(239, 68, 68, 0.3)',
              color: '#fca5a5',
              fontSize: '0.82rem',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <span>🛡️</span>
            <span>Privacy Mode is active. Memory writes and retrievals are suspended.</span>
          </div>
        )}

        {/* Filter & Search Bar */}
        <div
          style={{
            padding: '12px 16px',
            display: 'flex',
            gap: '10px',
            borderBottom: '1px solid var(--border-subtle, rgba(255,255,255,0.08))',
            background: 'rgba(0,0,0,0.2)',
          }}
        >
          <input
            type="text"
            placeholder="Search remembered facts, keys, or preferences..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              flex: 1,
              background: 'rgba(255,255,255,0.05)',
              border: '1px solid rgba(255,255,255,0.15)',
              borderRadius: '6px',
              color: '#fff',
              padding: '6px 10px',
              fontSize: '0.85rem',
            }}
          />
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            style={{
              background: 'rgba(255,255,255,0.05)',
              border: '1px solid rgba(255,255,255,0.15)',
              borderRadius: '6px',
              color: '#fff',
              padding: '6px 10px',
              fontSize: '0.85rem',
            }}
          >
            <option value="all">All Categories</option>
            <option value="explicit_fact">Explicit Facts</option>
            <option value="preference">Preferences</option>
            <option value="project_state">Project State</option>
            <option value="inference">Inferences</option>
            <option value="temporary_observation">Observations</option>
          </select>
        </div>

        {/* Add Memory Form */}
        {isAdding && (
          <form
            onSubmit={handleCreateMemory}
            style={{
              padding: '14px 16px',
              borderBottom: '1px solid rgba(255,255,255,0.1)',
              background: 'rgba(16, 185, 129, 0.05)',
              display: 'flex',
              flexDirection: 'column',
              gap: '10px',
            }}
          >
            <div style={{ display: 'flex', gap: '8px' }}>
              <select
                value={newCategory}
                onChange={(e) => setNewCategory(e.target.value as MemoryCategory)}
                style={{
                  background: '#1a1f2c',
                  border: '1px solid rgba(255,255,255,0.2)',
                  borderRadius: '4px',
                  color: '#fff',
                  padding: '6px',
                  fontSize: '0.85rem',
                }}
              >
                <option value="explicit_fact">Explicit Fact</option>
                <option value="preference">User Preference</option>
                <option value="project_state">Project State</option>
                <option value="inference">Inference</option>
                <option value="temporary_observation">Observation</option>
              </select>
              <input
                type="text"
                placeholder="Key (e.g. project_codename)"
                value={newKey}
                onChange={(e) => setNewKey(e.target.value)}
                required
                style={{
                  flex: 1,
                  background: '#1a1f2c',
                  border: '1px solid rgba(255,255,255,0.2)',
                  borderRadius: '4px',
                  color: '#fff',
                  padding: '6px 10px',
                  fontSize: '0.85rem',
                }}
              />
            </div>
            <textarea
              placeholder="Memory content (e.g. Cindercrest 2.0 uses SQLite in WAL mode)"
              value={newContent}
              onChange={(e) => setNewContent(e.target.value)}
              required
              rows={2}
              style={{
                width: '100%',
                background: '#1a1f2c',
                border: '1px solid rgba(255,255,255,0.2)',
                borderRadius: '4px',
                color: '#fff',
                padding: '6px 10px',
                fontSize: '0.85rem',
                resize: 'none',
              }}
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button
                type="button"
                onClick={() => setIsAdding(false)}
                className="btn-drawer-action"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="btn-drawer-action"
                style={{ backgroundColor: 'rgba(16, 185, 129, 0.3)', borderColor: '#10b981' }}
              >
                Save to SQLite
              </button>
            </div>
          </form>
        )}

        {/* Content list */}
        <div className="drawer-content" style={{ padding: '16px' }}>
          {error && (
            <div
              style={{
                padding: '10px',
                marginBottom: '12px',
                backgroundColor: 'rgba(239, 68, 68, 0.2)',
                border: '1px solid #ef4444',
                borderRadius: '6px',
                color: '#fca5a5',
                fontSize: '0.85rem',
              }}
            >
              {error}
            </div>
          )}

          {isLoading ? (
            <div className="drawer-empty">
              <span>Loading memories...</span>
            </div>
          ) : memories.length === 0 ? (
            <div className="drawer-empty">
              <span>No memories stored under this category.</span>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Tell Cindercrest "Remember that..." or use "+ Add Fact" above.
              </span>
            </div>
          ) : (
            memories.map((item) => (
              <div
                key={item.memory_id}
                style={{
                  padding: '12px 14px',
                  marginBottom: '12px',
                  backgroundColor: 'rgba(255, 255, 255, 0.03)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: '8px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                }}
              >
                {/* Top badges */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                    <span
                      style={{
                        fontSize: '0.72rem',
                        fontWeight: 600,
                        padding: '2px 6px',
                        borderRadius: '4px',
                        textTransform: 'uppercase',
                        backgroundColor:
                          item.category === 'explicit_fact'
                            ? 'rgba(59, 130, 246, 0.2)'
                            : item.category === 'preference'
                            ? 'rgba(168, 85, 247, 0.2)'
                            : item.category === 'inference'
                            ? 'rgba(234, 179, 8, 0.2)'
                            : 'rgba(16, 185, 129, 0.2)',
                        color:
                          item.category === 'explicit_fact'
                            ? '#93c5fd'
                            : item.category === 'preference'
                            ? '#d8b4fe'
                            : item.category === 'inference'
                            ? '#fde047'
                            : '#6ee7b7',
                      }}
                    >
                      {item.category.replace('_', ' ')}
                      {item.category === 'inference' && ` (${Math.round(item.confidence * 100)}%)`}
                    </span>
                    <span
                      style={{
                        fontSize: '0.75rem',
                        fontFamily: 'monospace',
                        color: 'var(--text-muted, #9ca3af)',
                      }}
                    >
                      {item.key}
                    </span>
                  </div>
                  <span
                    style={{
                      fontSize: '0.7rem',
                      color: item.status === 'active' ? '#10b981' : '#9ca3af',
                      textTransform: 'uppercase',
                    }}
                  >
                    {item.status}
                  </span>
                </div>

                {/* Content / Edit Mode */}
                {correctingId === item.memory_id ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <textarea
                      value={correctedContent}
                      onChange={(e) => setCorrectedContent(e.target.value)}
                      rows={2}
                      style={{
                        background: '#1a1f2c',
                        border: '1px solid #3b82f6',
                        borderRadius: '4px',
                        color: '#fff',
                        padding: '6px',
                        fontSize: '0.85rem',
                      }}
                    />
                    <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end' }}>
                      <button
                        onClick={() => setCorrectingId(null)}
                        className="btn-drawer-action"
                        style={{ fontSize: '0.75rem' }}
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => handleCorrectMemory(item.memory_id)}
                        className="btn-drawer-action"
                        style={{
                          fontSize: '0.75rem',
                          backgroundColor: 'rgba(59, 130, 246, 0.3)',
                          borderColor: '#3b82f6',
                        }}
                      >
                        Save Correction
                      </button>
                    </div>
                  </div>
                ) : (
                  <div style={{ fontSize: '0.88rem', color: '#e5e7eb', lineHeight: 1.4 }}>
                    {item.content}
                  </div>
                )}

                {/* Footer Provenance & Actions */}
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    fontSize: '0.72rem',
                    color: 'var(--text-muted, #9ca3af)',
                    borderTop: '1px solid rgba(255, 255, 255, 0.05)',
                    paddingTop: '6px',
                  }}
                >
                  <div>
                    <span>Source: {item.provenance}</span>
                    <span style={{ margin: '0 6px' }}>•</span>
                    <span>{new Date(item.created_at).toLocaleDateString()}</span>
                  </div>

                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      onClick={() => {
                        setCorrectingId(item.memory_id);
                        setCorrectedContent(item.content);
                      }}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: '#60a5fa',
                        cursor: 'pointer',
                        fontSize: '0.75rem',
                      }}
                    >
                      Correct
                    </button>
                    <button
                      onClick={() => handleDeleteMemory(item.memory_id)}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: '#f87171',
                        cursor: 'pointer',
                        fontSize: '0.75rem',
                      }}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
