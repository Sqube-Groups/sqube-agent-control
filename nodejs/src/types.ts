export enum Decision {
  ALLOW = "ALLOW",
  BLOCK = "BLOCK",
  REQUIRE_APPROVAL = "REQUIRE_APPROVAL",
}

export enum ActionStatus {
  REQUESTED = "REQUESTED",
  EVALUATED = "EVALUATED",
  BLOCKED = "BLOCKED",
  WAITING_APPROVAL = "WAITING_APPROVAL",
  APPROVED = "APPROVED",
  DENIED = "DENIED",
  EXPIRED = "EXPIRED",
  EXECUTING = "EXECUTING",
  SUCCEEDED = "SUCCEEDED",
  FAILED = "FAILED",
  CANCELLED = "CANCELLED",
}

export type PolicyFn = (
  action: string,
  resource: string | null,
  agentId: string,
  ctx?: Record<string, unknown>
) => Decision;

export type ApprovalFn = (opts: {
  executionId: string;
  agentId: string;
  action: string;
  resource: string | null;
  summary: string;
  timeoutSeconds: number;
}) => Promise<{ approved: boolean; approvedBy: string | null; reason: string | null }>;

export type OnErrorMode = "fail_open" | "fail_closed";

export interface ActionRecord {
  execution_id: string;
  created_at: string;
  agent_id: string;
  action: string;
  resource: string | null;
  parameters_hash: string;
  parameters_summary: string | null;
  decision: string;
  policy_id: string;
  status: string;
  approved_by?: string | null;
  approval_reason?: string | null;
  result_status?: string | null;
  error_message?: string | null;
  duration_ms?: number | null;
  completed_at?: string | null;
}
