/**
 * TypeScript contract matching FastAPI backend schemas.
 */

export type VoiceState = 'IDLE' | 'LISTENING' | 'PROCESSING' | 'SPEAKING' | 'INTERRUPTED';

export interface ComponentHealth {
  status: 'ok' | 'error' | 'unreachable' | 'ready' | 'active';
  details: Record<string, unknown>;
}

export interface HealthResponse {
  status: 'healthy' | 'degraded';
  version: string;
  timestamp: string;
  checks: {
    database: ComponentHealth;
    ollama: ComponentHealth;
    voice_subsystem: ComponentHealth;
    policy_engine: ComponentHealth;
  };
}

export interface AuthVerifyResponse {
  authenticated: boolean;
  session_active: boolean;
  token_prefix: string;
}

export interface VoiceStateResponse {
  current_state: VoiceState;
  history_count: number;
}

export interface ConversationTurn {
  turn_index: number;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  outcome: string;
  latency_ms?: number;
}

export interface ChatRequest {
  text: string;
  provider?: string;
  stream?: boolean;
}

export interface ChatResponse {
  reply: string;
  turn_index: number;
  latency_ms?: number;
  model_used: string;
}

export interface ModelStatus {
  provider_id: string;
  model_name: string;
  is_available: boolean;
  is_default: boolean;
}

export interface StandardErrorPayload {
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}

export type TaskState =
  | 'CREATED'
  | 'PLANNING'
  | 'AWAITING_APPROVAL'
  | 'RUNNING'
  | 'VERIFYING'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED'
  | 'OUTCOME_UNKNOWN';

export type TaskOutcome = 'success' | 'failure' | 'unknown' | 'cancelled';

export interface ActionStep {
  step_index: number;
  tool_name: string;
  parameters: Record<string, unknown>;
  expected_outcome: string;
  status: string;
  result?: unknown;
  error?: string;
  verified: boolean;
}

export interface TaskPlan {
  goal: string;
  intent: 'CONVERSATION' | 'INFORMATION' | 'TASK_EXECUTION';
  steps: ActionStep[];
  requires_approval: boolean;
  created_at: string;
}

export interface Task {
  task_id: string;
  goal: string;
  intent_type: 'CONVERSATION' | 'INFORMATION' | 'TASK_EXECUTION';
  state: TaskState;
  outcome: TaskOutcome;
  plan?: TaskPlan;
  current_step_index: number;
  error_message?: string;
  result_summary?: string;
  created_at: string;
  updated_at: string;
}

export interface ToolInfo {
  name: string;
  description: string;
  safety_tier: 'READ' | 'WRITE' | 'DESTRUCTIVE';
  parameters_schema: Record<string, unknown>;
}

export interface TaskAuditEvent {
  id: number;
  task_id: string;
  event_type: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export type MemoryCategory =
  | 'conversation_context'
  | 'preference'
  | 'project_state'
  | 'explicit_fact'
  | 'temporary_observation'
  | 'inference';

export type MemoryStatus =
  | 'active'
  | 'superseded'
  | 'corrected'
  | 'deleted'
  | 'expired';

export interface MemoryItem {
  memory_id: string;
  category: MemoryCategory;
  key: string;
  content: string;
  confidence: number;
  provenance: string;
  status: MemoryStatus;
  superseded_by?: string | null;
  expires_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateMemoryRequest {
  category: MemoryCategory;
  key: string;
  content: string;
  confidence?: number;
  provenance?: string;
  expires_at?: string | null;
}

export interface CorrectMemoryRequest {
  content: string;
  provenance?: string;
}

export type PersonalityMode =
  | 'adaptive'
  | 'work'
  | 'focus'
  | 'relax'
  | 'coach'
  | 'quiet'
  | 'serious';

export interface ModeConfig {
  mode: PersonalityMode;
  tone_description: string;
  prompt_modifier: string;
  verbosity: string;
  initiative: number;
  allow_playful_banter: boolean;
  interruption_threshold: string;
}

export interface ModeResponse {
  active_mode: PersonalityMode;
  config: ModeConfig;
  available_modes: string[];
}

export type InterventionOutcome =
  | 'TALK'
  | 'ASK'
  | 'WAIT'
  | 'SUPPRESS'
  | 'PROPOSE_ACTION'
  | 'PRIVACY';

export interface ObservationItem {
  source: string;
  summary: string;
  confidence: number;
  expected_usefulness: number;
  urgency: string;
  proposed_action?: Record<string, unknown>;
  timestamp?: number;
}

export interface InterventionDecision {
  outcome: InterventionOutcome;
  reason: string;
  observation?: ObservationItem;
  proposed_action?: Record<string, unknown>;
  auto_executed: boolean;
}
