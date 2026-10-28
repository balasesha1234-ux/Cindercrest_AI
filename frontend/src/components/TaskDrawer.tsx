import React, { useState, useEffect, useCallback } from 'react';
import { Task, ToolInfo, TaskAuditEvent } from '../types/api';
import { apiClient } from '../api/client';

interface TaskDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  sessionToken: string;
}

export const TaskDrawer: React.FC<TaskDrawerProps> = ({ isOpen, onClose, sessionToken }) => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [auditEvents, setAuditEvents] = useState<TaskAuditEvent[]>([]);
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [newGoal, setNewGoal] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTasks = useCallback(async () => {
    if (!sessionToken) return;
    try {
      const taskList = await apiClient.listTasks(sessionToken);
      setTasks(taskList);
      if (selectedTask) {
        const updated = taskList.find((t) => t.task_id === selectedTask.task_id);
        if (updated) setSelectedTask(updated);
      }
    } catch (err: unknown) {
      console.error('Failed to fetch tasks:', err);
    }
  }, [sessionToken, selectedTask]);

  const fetchTools = useCallback(async () => {
    if (!sessionToken) return;
    try {
      const toolList = await apiClient.listTools(sessionToken);
      setTools(toolList);
    } catch (err: unknown) {
      console.error('Failed to fetch tools:', err);
    }
  }, [sessionToken]);

  const fetchEvents = useCallback(async (taskId: string) => {
    if (!sessionToken) return;
    try {
      const events = await apiClient.getTaskEvents(sessionToken, taskId);
      setAuditEvents(events);
    } catch (err: unknown) {
      console.error('Failed to fetch audit events:', err);
    }
  }, [sessionToken]);

  useEffect(() => {
    if (isOpen && sessionToken) {
      fetchTasks();
      fetchTools();
    }
  }, [isOpen, sessionToken, fetchTasks, fetchTools]);

  useEffect(() => {
    if (selectedTask) {
      fetchEvents(selectedTask.task_id);
    } else {
      setAuditEvents([]);
    }
  }, [selectedTask, fetchEvents]);

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newGoal.trim() || isCreating || !sessionToken) return;

    setIsCreating(true);
    setError(null);
    try {
      const created = await apiClient.createTask(sessionToken, newGoal.trim());
      setNewGoal('');
      await fetchTasks();
      setSelectedTask(created);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create task plan');
    } finally {
      setIsCreating(false);
    }
  };

  const handleExecuteTask = async (taskId: string) => {
    if (isExecuting || !sessionToken) return;

    setIsExecuting(true);
    setError(null);
    try {
      const completed = await apiClient.executeTask(sessionToken, taskId);
      setSelectedTask(completed);
      await fetchTasks();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Execution failed');
    } finally {
      setIsExecuting(false);
    }
  };

  const handleCancelTask = async (taskId: string) => {
    if (!sessionToken) return;
    try {
      const cancelled = await apiClient.cancelTask(sessionToken, taskId);
      setSelectedTask(cancelled);
      await fetchTasks();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Cancellation failed');
    }
  };

  if (!isOpen) return null;

  const getStateBadgeClass = (state: string) => {
    switch (state) {
      case 'COMPLETED':
        return 'badge-success';
      case 'RUNNING':
      case 'VERIFYING':
      case 'PLANNING':
        return 'badge-active';
      case 'FAILED':
      case 'OUTCOME_UNKNOWN':
        return 'badge-error';
      case 'CANCELLED':
        return 'badge-muted';
      default:
        return 'badge-neutral';
    }
  };

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div
        className="drawer-panel agent-brain-drawer"
        onClick={(e) => e.stopPropagation()}
        style={{ width: '640px', maxWidth: '90vw' }}
      >
        <div className="drawer-header">
          <div className="flex-row items-center gap-2">
            <div className="pulse-dot green" />
            <h2 className="drawer-title">Agent Brain &amp; Task Orchestrator</h2>
          </div>
          <button className="btn-icon" onClick={onClose} aria-label="Close tasks panel">
            ✕
          </button>
        </div>

        <div className="drawer-body">
          {error && <div className="alert-banner error mb-4">{error}</div>}

          {/* New Task Planner Input */}
          <div className="task-composer-card mb-6">
            <h3 className="section-label">Create Structured Task</h3>
            <p className="text-xs text-muted mb-2">
              The Agent Brain classifies intent (Conversation, Information, Task Execution), validates schemas, and
              enforces default-DENY policy gates.
            </p>
            <form onSubmit={handleCreateTask} className="flex-row gap-2">
              <input
                type="text"
                className="input-text flex-1"
                placeholder="e.g. Calculate 25 * 4, then check the current time"
                value={newGoal}
                onChange={(e) => setNewGoal(e.target.value)}
                disabled={isCreating}
              />
              <button type="submit" className="btn-primary" disabled={isCreating || !newGoal.trim()}>
                {isCreating ? 'Planning...' : 'Plan Task'}
              </button>
            </form>
          </div>

          {/* Master-Detail Task Layout */}
          <div className="grid grid-cols-2 gap-4" style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr' }}>
            {/* Task List */}
            <div className="task-list-column">
              <div className="flex-row justify-between items-center mb-2">
                <span className="text-xs font-semibold text-muted">TASKS ({tasks.length})</span>
                <button className="btn-link text-xs" onClick={fetchTasks}>
                  Refresh
                </button>
              </div>

              <div className="task-scroll-area flex-col gap-2">
                {tasks.length === 0 ? (
                  <div className="empty-state">No persistent tasks recorded yet.</div>
                ) : (
                  tasks.map((t) => (
                    <div
                      key={t.task_id}
                      className={`task-card-item ${selectedTask?.task_id === t.task_id ? 'selected' : ''}`}
                      onClick={() => setSelectedTask(t)}
                    >
                      <div className="flex-row justify-between items-center mb-1">
                        <span className="task-id-mono">{t.task_id.slice(0, 14)}...</span>
                        <span className={`status-badge ${getStateBadgeClass(t.state)}`}>{t.state}</span>
                      </div>
                      <div className="task-goal-text">{t.goal}</div>
                      <div className="flex-row justify-between items-center mt-2 text-xs text-muted">
                        <span>{t.intent_type}</span>
                        <span>Outcome: {t.outcome}</span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Selected Task Details & Plan View */}
            <div className="task-detail-column">
              {selectedTask ? (
                <div className="task-detail-card flex-col gap-3">
                  <div className="flex-row justify-between items-start">
                    <div>
                      <h4 className="text-sm font-semibold">{selectedTask.goal}</h4>
                      <div className="text-xs text-muted mt-1">ID: {selectedTask.task_id}</div>
                    </div>
                    <span className={`status-badge ${getStateBadgeClass(selectedTask.state)}`}>
                      {selectedTask.state}
                    </span>
                  </div>

                  {/* Actions Bar */}
                  <div className="flex-row gap-2 mt-2">
                    {selectedTask.state !== 'COMPLETED' && selectedTask.state !== 'CANCELLED' && (
                      <button
                        className="btn-primary flex-1"
                        onClick={() => handleExecuteTask(selectedTask.task_id)}
                        disabled={isExecuting}
                      >
                        {isExecuting ? 'Executing...' : 'Execute Plan'}
                      </button>
                    )}
                    {selectedTask.state !== 'CANCELLED' && selectedTask.state !== 'COMPLETED' && (
                      <button
                        className="btn-secondary"
                        onClick={() => handleCancelTask(selectedTask.task_id)}
                        disabled={isExecuting}
                      >
                        Cancel
                      </button>
                    )}
                  </div>

                  {selectedTask.error_message && (
                    <div className="alert-banner error mt-2 text-xs">{selectedTask.error_message}</div>
                  )}

                  {selectedTask.result_summary && (
                    <div className="task-summary-banner mt-2">
                      <div className="text-xs font-semibold text-green mb-1">GROUNDED SUMMARY</div>
                      <div className="text-xs leading-relaxed">{selectedTask.result_summary}</div>
                    </div>
                  )}

                  {/* Plan Steps */}
                  <div className="steps-container mt-2">
                    <span className="text-xs font-semibold text-muted">ACTION STEPS &amp; VERIFICATION</span>
                    {selectedTask.plan?.steps && selectedTask.plan.steps.length > 0 ? (
                      <div className="flex-col gap-2 mt-2">
                        {selectedTask.plan.steps.map((s) => (
                          <div key={s.step_index} className="step-card">
                            <div className="flex-row justify-between items-center mb-1">
                              <span className="font-mono text-xs">
                                #{s.step_index} {s.tool_name}
                              </span>
                              <div className="flex-row gap-1 items-center">
                                {s.verified && <span className="verified-pill">VERIFIED</span>}
                                <span className={`status-pill ${s.status}`}>{s.status}</span>
                              </div>
                            </div>
                            <div className="text-xs text-muted mb-1">Expected: {s.expected_outcome}</div>
                            {s.result !== undefined && (
                              <div className="step-result-box">
                                <pre>{JSON.stringify(s.result, null, 2)}</pre>
                              </div>
                            )}
                            {s.error && <div className="text-xs text-error mt-1">{s.error}</div>}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-xs text-muted mt-2 italic">
                        {selectedTask.intent_type === 'CONVERSATION'
                          ? 'Conversational intent has zero tool steps (direct response).'
                          : 'No steps generated.'}
                      </div>
                    )}
                  </div>

                  {/* Audit Event Trail */}
                  <div className="audit-trail-section mt-4">
                    <span className="text-xs font-semibold text-muted">
                      AUDIT EVENTS ({auditEvents.length})
                    </span>
                    <div className="audit-scroll-area mt-2">
                      {auditEvents.map((ev) => (
                        <div key={ev.id} className="audit-event-row">
                          <span className="event-time">
                            {new Date(ev.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                          </span>
                          <span className="event-type">{ev.event_type}</span>
                          <span className="event-payload">{JSON.stringify(ev.payload)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="empty-state">Select a task on the left or create a new one to inspect its plan.</div>
              )}
            </div>
          </div>

          {/* Registered Tools Overview */}
          <div className="tools-overview-section mt-6">
            <h4 className="text-xs font-semibold text-muted mb-2">REGISTERED SAFE TOOLS ({tools.length})</h4>
            <div className="tools-grid">
              {tools.map((t) => (
                <div key={t.name} className="tool-chip">
                  <div className="font-mono text-xs font-semibold">{t.name}</div>
                  <div className="text-xs text-muted">{t.description}</div>
                  <span className="safety-tier-tag">{t.safety_tier}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
