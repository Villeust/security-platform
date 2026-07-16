export type Uuid = string;

export type WorkflowMetric = {
  key: string;
  label: string;
  value: number | string;
  tone: 'healthy' | 'attention' | 'error' | string;
  target?: string | null;
};

export type WorkflowDashboard = {
  metrics: WorkflowMetric[];
  health_score: number;
  recent_activity: WorkflowActivity[];
};

export type WorkflowActivity = {
  id: Uuid | null;
  action: string;
  workflow_code: string | null;
  workflow_version: number | null;
  actor_id: Uuid | null;
  created_at: string;
};

export type WorkflowDefinition = {
  id: Uuid;
  code: string;
  name: string;
  description: string | null;
  entity_type: string;
  version: number;
  is_published: boolean;
  is_active: boolean;
  states_count: number;
  transitions_count: number;
  instances_count: number;
  created_at: string;
  updated_at: string;
  published_at: string | null;
};

export type WorkflowState = {
  id: Uuid;
  code: string;
  name: string;
  description: string | null;
  state_type: string;
  sort_order: number;
  is_initial: boolean;
  is_terminal: boolean;
  color_token: string | null;
  icon: string | null;
  is_active: boolean;
  incoming_count: number;
  outgoing_count: number;
};

export type WorkflowTransition = {
  id: Uuid;
  code: string;
  name: string;
  description: string | null;
  from_state_id: Uuid;
  to_state_id: Uuid;
  from_state_code: string | null;
  to_state_code: string | null;
  permission_code: string | null;
  requires_comment: boolean;
  requires_reason: boolean;
  requires_attachment: boolean;
  confirmation_required: boolean;
  sort_order: number;
  is_active: boolean;
  configuration_json: Record<string, unknown> | null;
};

export type WorkflowSlaPolicy = {
  id: Uuid;
  code: string;
  name: string;
  state_id: Uuid | null;
  state_code: string | null;
  transition_id: Uuid | null;
  transition_code: string | null;
  duration_minutes: number;
  duration_label: string;
  warning_before_minutes: number | null;
  warning_label: string | null;
  business_calendar_code: string | null;
  severity: string;
  is_active: boolean;
};

export type WorkflowValidationIssue = {
  code: string;
  severity: 'error' | 'warning' | 'info' | string;
  message: string;
  target_type?: string | null;
  target_code?: string | null;
};

export type WorkflowValidation = {
  status: 'ok' | 'warning' | 'error' | string;
  errors: WorkflowValidationIssue[];
  warnings: WorkflowValidationIssue[];
  info: WorkflowValidationIssue[];
};

export type WorkflowDefinitionDetail = WorkflowDefinition & {
  states: WorkflowState[];
  transitions: WorkflowTransition[];
  sla_policies: WorkflowSlaPolicy[];
  validation: WorkflowValidation;
  created_by: Uuid | null;
  published_by: Uuid | null;
};

export type ListResponse<T> = {
  items: T[];
  total: number;
  skip?: number;
  limit?: number;
};

export type WorkflowVersion = {
  id: Uuid;
  code: string;
  version: number;
  status: string;
  created_by: Uuid | null;
  created_at: string;
  published_at: string | null;
  comment: string | null;
  instances_count: number;
  is_active: boolean;
  is_published: boolean;
};

export type WorkflowVersionDiff = {
  source_version: number;
  target_version: number;
  added_states: string[];
  removed_states: string[];
  added_transitions: string[];
  removed_transitions: string[];
  permission_changes: string[];
  sla_changes: string[];
  metadata_changes: string[];
};

export type WorkflowInstance = {
  id: Uuid;
  workflow_definition_id: Uuid;
  workflow_code: string;
  workflow_name: string;
  workflow_version: number;
  entity_type: string;
  entity_id: Uuid;
  business_identifier: string;
  current_state: string;
  current_state_code: string;
  started_at: string;
  updated_at: string;
  completed_at: string | null;
  cancelled_at: string | null;
  lock_version: number;
};

export type WorkflowExecution = {
  id: Uuid;
  transition_code: string | null;
  transition_name: string | null;
  from_state: string | null;
  to_state: string | null;
  actor_type: string;
  actor_id: Uuid | null;
  comment: string | null;
  reason_code: string | null;
  created_at: string;
  correlation_id: string | null;
};

export type WorkflowSlaTimer = {
  id: Uuid;
  policy_code: string | null;
  policy_name: string | null;
  started_at: string;
  due_at: string;
  warning_at: string | null;
  completed_at: string | null;
  breached_at: string | null;
  status: string;
};

export type WorkflowOutboxEvent = {
  id: Uuid;
  event_type: string;
  aggregate_type: string;
  aggregate_id: Uuid;
  business_identifier: string;
  created_at: string;
  processed_at: string | null;
  status: string;
  attempts: number;
  correlation_id: string | null;
  last_error: string | null;
};

export type WorkflowInstanceDetail = WorkflowInstance & {
  executions: WorkflowExecution[];
  sla_timers: WorkflowSlaTimer[];
  outbox_events: WorkflowOutboxEvent[];
  metadata: Record<string, unknown>;
  technical_details: Record<string, unknown> | null;
};

export type SlaCenter = {
  metrics: WorkflowMetric[];
  policies: WorkflowSlaPolicy[];
  timers: WorkflowSlaTimer[];
  business_calendar_note: string;
};

export type OutboxMonitor = {
  metrics: WorkflowMetric[];
  items: WorkflowOutboxEvent[];
  total: number;
};

export type ProcessAuditItem = {
  id: Uuid;
  action: string;
  workflow_code: string | null;
  workflow_version: number | null;
  actor_id: Uuid | null;
  actor_type: string;
  created_at: string;
  safe_details: Record<string, unknown> | null;
};

export type WorkflowStatistics = {
  average_workflow_duration: string;
  median_duration: string;
  fastest_transition: string;
  slowest_transition: string;
  average_completion_time: string;
  completion_percent: number;
  cancellation_percent: number;
  sla_percent: number;
};

export type PlatformHealth = {
  health_score: number;
  backend_status: string;
  database_status: string;
  alembic_revision: string | null;
  workflow_engine: string;
  workflow_definitions: string;
  workflow_instances: string;
  rbac: string;
  authentication: string;
  storage: string;
  smtp: string;
  ldap: string;
  adfs: string;
  warnings: Array<{ name: string; status: string; message: string }>;
  errors: Array<{ name: string; status: string; message: string }>;
};

export type WorkflowSearchResult = {
  type: string;
  label: string;
  description: string | null;
  target: string;
};
