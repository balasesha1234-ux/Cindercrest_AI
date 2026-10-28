/**
 * Typed API client for Cindercrest 2.0 backend running on localhost.
 */

import {
  HealthResponse,
  AuthVerifyResponse,
  VoiceStateResponse,
  VoiceState,
  StandardErrorPayload,
  ChatResponse,
  ConversationTurn,
  ModelStatus,
  Task,
  ToolInfo,
  TaskAuditEvent,
  MemoryItem,
  CreateMemoryRequest,
  CorrectMemoryRequest,
  PersonalityMode,
  ModeResponse,
  ObservationItem,
  InterventionDecision,
} from '../types/api';

export class ApiError extends Error {
  code: string;
  details?: unknown;

  constructor(message: string, code: string = 'CLIENT_ERROR', details?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.details = details;
  }
}

export class CindercrestApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = 'http://127.0.0.1:8000') {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    token?: string,
    timeoutMs: number = 30000
  ): Promise<T> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...((options.headers as Record<string, string>) || {}),
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token.trim()}`;
    }

    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        ...options,
        headers,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      const data = await response.json();

      if (!response.ok) {
        const errorPayload = data as StandardErrorPayload;
        throw new ApiError(
          errorPayload.error?.message || `HTTP error ${response.status}`,
          errorPayload.error?.code || `HTTP_${response.status}`,
          errorPayload.error?.details
        );
      }

      return data as T;
    } catch (err: unknown) {
      clearTimeout(timeoutId);
      if (err instanceof ApiError) {
        throw err;
      }
      if (err instanceof DOMException && err.name === 'AbortError') {
        throw new ApiError('Request timed out connecting to backend', 'TIMEOUT');
      }
      const message = err instanceof Error ? err.message : 'Failed to connect to backend server';
      throw new ApiError(message, 'NETWORK_ERROR');
    }
  }

  /**
   * Public health probe (no token required).
   */
  async getHealth(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/health', {}, undefined, 3000);
  }

  /**
   * Verify session token on protected route.
   */
  async verifyAuth(token: string): Promise<AuthVerifyResponse> {
    return this.request<AuthVerifyResponse>('/api/v1/auth/verify', { method: 'GET' }, token, 3000);
  }

  /**
   * Fetch current voice engine state.
   */
  async getVoiceState(token: string): Promise<VoiceStateResponse> {
    return this.request<VoiceStateResponse>('/api/v1/voice/state', { method: 'GET' }, token, 3000);
  }

  /**
   * Trigger a voice state transition under strict state machine governance.
   */
  async transitionVoiceState(token: string, targetState: VoiceState, reason?: string): Promise<VoiceStateResponse> {
    return this.request<VoiceStateResponse>(
      '/api/v1/voice/transition',
      {
        method: 'POST',
        body: JSON.stringify({ target_state: targetState, reason }),
      },
      token,
      3000
    );
  }

  /**
   * Submit conversational turn (spoken transcript or typed text).
   */
  async submitChat(token: string, text: string, provider?: string): Promise<ChatResponse> {
    return this.request<ChatResponse>(
      '/api/v1/conversation/chat',
      {
        method: 'POST',
        body: JSON.stringify({ text, provider, stream: false }),
      },
      token,
      45000
    );
  }

  /**
   * Fetch session conversation history.
   */
  async getHistory(token: string): Promise<ConversationTurn[]> {
    return this.request<ConversationTurn[]>('/api/v1/conversation/history', { method: 'GET' }, token, 5000);
  }

  /**
   * Reset session turns.
   */
  async resetHistory(token: string): Promise<{ status: string; turns_cleared: number }> {
    return this.request<{ status: string; turns_cleared: number }>(
      '/api/v1/conversation/reset',
      { method: 'POST' },
      token,
      5000
    );
  }

  /**
   * List available conversational models.
   */
  async getModels(token: string): Promise<ModelStatus[]> {
    return this.request<ModelStatus[]>('/api/v1/conversation/models', { method: 'GET' }, token, 5000);
  }

  /**
   * Create a new agent task with intent classification and plan generation.
   */
  async createTask(token: string, goal: string): Promise<Task> {
    return this.request<Task>(
      '/api/v1/tasks',
      {
        method: 'POST',
        body: JSON.stringify({ goal }),
      },
      token,
      10000
    );
  }

  /**
   * Execute a planned task through deterministic policy and verification gates.
   */
  async executeTask(token: string, taskId: string): Promise<Task> {
    return this.request<Task>(
      `/api/v1/tasks/${taskId}/execute`,
      { method: 'POST' },
      token,
      45000
    );
  }

  /**
   * List recent persistent agent tasks.
   */
  async listTasks(token: string, limit: number = 50): Promise<Task[]> {
    return this.request<Task[]>(`/api/v1/tasks?limit=${limit}`, { method: 'GET' }, token, 5000);
  }

  /**
   * Get specific task details.
   */
  async getTask(token: string, taskId: string): Promise<Task> {
    return this.request<Task>(`/api/v1/tasks/${taskId}`, { method: 'GET' }, token, 5000);
  }

  /**
   * Cancel an in-flight or pending agent task.
   */
  async cancelTask(token: string, taskId: string): Promise<Task> {
    return this.request<Task>(
      `/api/v1/tasks/${taskId}/cancel`,
      { method: 'POST' },
      token,
      5000
    );
  }

  /**
   * Retrieve append-only audit event trail for a task.
   */
  async getTaskEvents(token: string, taskId: string): Promise<TaskAuditEvent[]> {
    return this.request<TaskAuditEvent[]>(
      `/api/v1/tasks/${taskId}/events`,
      { method: 'GET' },
      token,
      5000
    );
  }

  /**
   * List registered tools, parameter schemas, and safety tiers.
   */
  async listTools(token: string): Promise<ToolInfo[]> {
    return this.request<ToolInfo[]>('/api/v1/tools', { method: 'GET' }, token, 5000);
  }

  /**
   * List persistent memories filtered by category and status.
   */
  async listMemories(
    token: string,
    category?: string,
    status?: string,
    limit: number = 50
  ): Promise<MemoryItem[]> {
    const params = new URLSearchParams();
    if (category) params.append('category', category);
    if (status) params.append('status_filter', status);
    params.append('limit', limit.toString());
    const query = params.toString() ? `?${params.toString()}` : '';
    return this.request<MemoryItem[]>(`/api/v1/memory${query}`, { method: 'GET' }, token, 5000);
  }

  /**
   * Explicitly create a new memory item (fact, preference, etc.).
   */
  async createMemory(token: string, payload: CreateMemoryRequest): Promise<MemoryItem> {
    return this.request<MemoryItem>(
      '/api/v1/memory',
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
      token,
      5000
    );
  }

  /**
   * Correct an existing memory, creating a superseding chain.
   */
  async correctMemory(
    token: string,
    memoryId: string,
    payload: CorrectMemoryRequest
  ): Promise<MemoryItem> {
    return this.request<MemoryItem>(
      `/api/v1/memory/${memoryId}`,
      {
        method: 'PUT',
        body: JSON.stringify(payload),
      },
      token,
      5000
    );
  }

  /**
   * Delete a memory item so it is excluded from future retrieval.
   */
  async deleteMemory(
    token: string,
    memoryId: string,
    hard: boolean = false
  ): Promise<{ deleted: boolean }> {
    const query = hard ? '?hard=true' : '';
    return this.request<{ deleted: boolean }>(
      `/api/v1/memory/${memoryId}${query}`,
      {
        method: 'DELETE',
      },
      token,
      5000
    );
  }

  /**
   * Search memories by semantic query.
   */
  async searchMemories(token: string, query: string, limit: number = 10): Promise<MemoryItem[]> {
    const params = new URLSearchParams({ query, limit: limit.toString() });
    return this.request<MemoryItem[]>(
      `/api/v1/memory/search?${params.toString()}`,
      { method: 'GET' },
      token,
      5000
    );
  }

  /**
   * Get active personality mode and available modes.
   */
  async getPersonalityMode(token: string): Promise<ModeResponse> {
    return this.request<ModeResponse>('/api/v1/personality/mode', { method: 'GET' }, token, 5000);
  }

  /**
   * Change active personality mode.
   */
  async setPersonalityMode(token: string, mode: PersonalityMode): Promise<ModeResponse> {
    return this.request<ModeResponse>(
      '/api/v1/personality/mode',
      {
        method: 'POST',
        body: JSON.stringify({ mode }),
      },
      token,
      5000
    );
  }

  /**
   * Evaluate a proposed system or sensory observation through proactive intervention policy.
   */
  async evaluateProactive(
    token: string,
    observation: ObservationItem,
    privacyMode: boolean = false,
    userDnd: boolean = false
  ): Promise<InterventionDecision> {
    return this.request<InterventionDecision>(
      '/api/v1/proactive/evaluate',
      {
        method: 'POST',
        body: JSON.stringify({
          observation,
          privacy_mode: privacyMode,
          user_dnd: userDnd,
        }),
      },
      token,
      5000
    );
  }
}

export const apiClient = new CindercrestApiClient();
