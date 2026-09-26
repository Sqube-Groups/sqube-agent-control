export enum EventType {
  ACTION_REQUESTED = "ACTION_REQUESTED",
  CONTEXT_RESOLVED = "CONTEXT_RESOLVED",
  POLICY_EVALUATED = "POLICY_EVALUATED",
  ACTION_BLOCKED = "ACTION_BLOCKED",
  APPROVAL_REQUESTED = "APPROVAL_REQUESTED",
  APPROVAL_GRANTED = "APPROVAL_GRANTED",
  APPROVAL_DENIED = "APPROVAL_DENIED",
  APPROVAL_EXPIRED = "APPROVAL_EXPIRED",
  ACTION_STARTED = "ACTION_STARTED",
  ACTION_SUCCEEDED = "ACTION_SUCCEEDED",
  ACTION_FAILED = "ACTION_FAILED",
  ACTION_CANCELLED = "ACTION_CANCELLED",
}

export interface ExecutionEvent {
  event_id: string;
  execution_id: string;
  event_type: EventType;
  timestamp: string;
  actor: string;
  payload: Record<string, unknown>;
  previous_event_hash: string | null;
  event_hash: string;
}
