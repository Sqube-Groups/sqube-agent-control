import { randomBytes } from "node:crypto";
import { EventType } from "./events.js";
import {
  SqubeApprovalPendingError,
  SqubeBlockedError,
  SqubeDeniedError,
  SqubeGuardError,
} from "./errors.js";
import { hashPayload } from "./hashing.js";
import { Ledger } from "./ledger.js";
import { defaultPolicy } from "./policy.js";
import { redactValue } from "./redaction.js";
import { promptCliApproval } from "./approval.js";
import {
  ActionStatus,
  Decision,
  type ApprovalFn,
  type OnErrorMode,
  type PolicyFn,
} from "./types.js";

export type ApprovalMode = "sync" | "deferred";

export interface ExecutionContext {
  executionId: string;
  agentId: string;
  action: string;
  resource: string | null;
  parameters: Record<string, unknown>;
  timestamp?: string;
  correlationId?: string;
  rootExecutionId?: string;
}

function utcNowIso(): string {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

function newApprovalId(): string {
  return `sq_apr_${randomBytes(6).toString("hex")}`;
}

export class ExecutionEngine {
  readonly ledger: Ledger;
  private policy: PolicyFn;
  private approvalMode: ApprovalMode;
  private approvalTimeoutSeconds: number;
  private approvalFn: ApprovalFn;
  private onError: OnErrorMode;

  constructor(opts: {
    policy?: PolicyFn;
    ledgerPath?: string;
    approvalMode?: ApprovalMode;
    approvalTimeoutSeconds?: number;
    approvalFn?: ApprovalFn;
    onError?: OnErrorMode;
  } = {}) {
    this.ledger = new Ledger(opts.ledgerPath ?? "sqube_ledger.sqlite3");
    this.policy = opts.policy ?? defaultPolicy;
    this.approvalMode = opts.approvalMode ?? "sync";
    this.approvalTimeoutSeconds = opts.approvalTimeoutSeconds ?? 300;
    this.approvalFn = opts.approvalFn ?? promptCliApproval;
    this.onError = opts.onError ?? "fail_closed";
  }

  simulate(ctx: ExecutionContext): Decision {
    return this.policy(ctx.action, ctx.resource, ctx.agentId, {
      parameters: ctx.parameters,
    });
  }

  policyName(): string {
    return this.policy.name || "anonymous_policy";
  }

  async runControlled<T>(ctx: ExecutionContext, fn: () => T | Promise<T>): Promise<T> {
    const ts = ctx.timestamp ?? utcNowIso();
    const rootId = ctx.rootExecutionId ?? ctx.executionId;
    const correlationId = ctx.correlationId ?? rootId;
    const paramsHash = hashPayload(ctx.parameters);
    const summary = redactValue(ctx.parameters);

    this.ledger.insert({
      execution_id: ctx.executionId,
      created_at: ts,
      agent_id: ctx.agentId,
      action: ctx.action,
      resource: ctx.resource,
      parameters_hash: paramsHash,
      parameters_summary: summary,
      decision: Decision.ALLOW,
      policy_id: this.policy.name || "policy",
      status: ActionStatus.REQUESTED,
    });
    this.ledger.appendEvent(
      ctx.executionId,
      EventType.ACTION_REQUESTED,
      ctx.agentId,
      { action: ctx.action, resource: ctx.resource },
      ts
    );

    this.ledger.transitionExecution(
      ctx.executionId,
      ActionStatus.REQUESTED,
      ActionStatus.EVALUATED
    );
    this.ledger.appendEvent(
      ctx.executionId,
      EventType.CONTEXT_RESOLVED,
      ctx.agentId,
      { correlation_id: correlationId, root_execution_id: rootId },
      utcNowIso()
    );

    let decision: Decision;
    try {
      decision = this.simulate(ctx);
    } catch (err) {
      if (this.onError === "fail_open") {
        return this.beginExecute(ctx, fn);
      }
      const message = err instanceof Error ? err.message : String(err);
      this.ledger.transitionExecution(
        ctx.executionId,
        ActionStatus.EVALUATED,
        ActionStatus.FAILED,
        {
          error_message: `policy_error: ${message}`,
          completed_at: utcNowIso(),
        }
      );
      throw new SqubeGuardError(`Policy evaluation failed: ${message}`);
    }
    this.ledger.updateStatus(ctx.executionId, { decision });
    this.ledger.appendEvent(
      ctx.executionId,
      EventType.POLICY_EVALUATED,
      "policy",
      { decision },
      utcNowIso()
    );

    if (decision === Decision.BLOCK) {
      this.ledger.transitionExecution(
        ctx.executionId,
        ActionStatus.EVALUATED,
        ActionStatus.BLOCKED,
        { completed_at: utcNowIso() }
      );
      throw new SqubeBlockedError(ctx.executionId, ctx.action);
    }

    if (decision === Decision.REQUIRE_APPROVAL) {
      if (this.approvalMode === "deferred") {
        const approvalId = newApprovalId();
        const now = utcNowIso();
        const expires = new Date(Date.now() + this.approvalTimeoutSeconds * 1000)
          .toISOString()
          .replace(/\.\d{3}Z$/, "Z");
        this.ledger.transitionExecution(
          ctx.executionId,
          ActionStatus.EVALUATED,
          ActionStatus.WAITING_APPROVAL
        );
        this.ledger.createApprovalRequest(
          approvalId,
          ctx.executionId,
          paramsHash,
          now,
          expires
        );
        this.ledger.appendEvent(
          ctx.executionId,
          EventType.APPROVAL_REQUESTED,
          ctx.agentId,
          { approval_id: approvalId, expires_at: expires },
          now
        );
        throw new SqubeApprovalPendingError(ctx.executionId, approvalId);
      }
      return this.syncApprovalPath(ctx, fn, paramsHash, summary);
    }

    return this.beginExecute(ctx, fn);
  }

  cancelExecution(executionId: string, reason = "cancelled"): void {
    const row = this.ledger.getExecution(executionId);
    if (!row) throw new SqubeGuardError(`unknown execution ${executionId}`);
    const now = utcNowIso();
    if (row.status === ActionStatus.WAITING_APPROVAL) {
      this.ledger.transitionExecution(
        executionId,
        ActionStatus.WAITING_APPROVAL,
        ActionStatus.CANCELLED,
        { completed_at: now, approval_reason: reason }
      );
      return;
    }
    if (row.status === ActionStatus.APPROVED) {
      this.ledger.transitionExecution(
        executionId,
        ActionStatus.APPROVED,
        ActionStatus.CANCELLED,
        { completed_at: now, approval_reason: reason }
      );
      return;
    }
    throw new SqubeGuardError(`cannot cancel execution in status ${row.status}`);
  }

  private async syncApprovalPath<T>(
    ctx: ExecutionContext,
    fn: () => T | Promise<T>,
    paramsHash: string,
    summary: string
  ): Promise<T> {
    this.ledger.transitionExecution(
      ctx.executionId,
      ActionStatus.EVALUATED,
      ActionStatus.WAITING_APPROVAL
    );
    const { approved, approvedBy, reason } = await this.approvalFn({
      executionId: ctx.executionId,
      agentId: ctx.agentId,
      action: ctx.action,
      resource: ctx.resource,
      summary,
      timeoutSeconds: this.approvalTimeoutSeconds,
    });
    const now = utcNowIso();
    if (!approved) {
      const toStatus =
        reason === "timeout" ? ActionStatus.EXPIRED : ActionStatus.DENIED;
      this.ledger.transitionExecution(ctx.executionId, ActionStatus.WAITING_APPROVAL, toStatus, {
        approval_reason: reason,
        completed_at: now,
      });
      throw new SqubeDeniedError(ctx.executionId, reason ?? "denied");
    }
    this.ledger.transitionExecution(ctx.executionId, ActionStatus.WAITING_APPROVAL, ActionStatus.APPROVED, {
      approved_by: approvedBy,
    });
    return this.beginExecute(ctx, fn, ActionStatus.APPROVED);
  }

  async resumeAfterApproval<T>(
    ctx: ExecutionContext,
    fn: () => T | Promise<T>,
    approvalId: string
  ): Promise<T> {
    const row = this.ledger.getExecution(ctx.executionId);
    if (!row) throw new SqubeGuardError(`unknown execution ${ctx.executionId}`);
    if (row.status === ActionStatus.WAITING_APPROVAL) {
      throw new SqubeApprovalPendingError(ctx.executionId, approvalId);
    }
    if (
      row.status === ActionStatus.DENIED ||
      row.status === ActionStatus.EXPIRED ||
      row.status === ActionStatus.BLOCKED
    ) {
      throw new SqubeDeniedError(ctx.executionId, row.status);
    }
    if (hashPayload(ctx.parameters) !== row.parameters_hash) {
      throw new SqubeGuardError("parameters changed after authorization");
    }
    const approval = this.ledger.getApproval(approvalId);
    if (!approval || approval.execution_id !== ctx.executionId) {
      throw new SqubeGuardError(`unknown approval ${approvalId}`);
    }
    const now = utcNowIso();
    if (approval.expires_at && approval.expires_at < now) {
      throw new SqubeDeniedError(ctx.executionId, "approval_expired");
    }
    this.ledger.consumeApproval(approvalId, ctx.executionId, now);
    this.ledger.appendEvent(
      ctx.executionId,
      EventType.ACTION_STARTED,
      ctx.agentId,
      { approval_id: approvalId },
      now
    );
    return this.runFnBody(ctx, fn);
  }

  private async beginExecute<T>(
    ctx: ExecutionContext,
    fn: () => T | Promise<T>,
    fromStatus: ActionStatus = ActionStatus.EVALUATED
  ): Promise<T> {
    this.ledger.transitionExecution(ctx.executionId, fromStatus, ActionStatus.EXECUTING);
    this.ledger.appendEvent(
      ctx.executionId,
      EventType.ACTION_STARTED,
      ctx.agentId,
      {},
      utcNowIso()
    );
    return this.runFnBody(ctx, fn);
  }

  private async runFnBody<T>(ctx: ExecutionContext, fn: () => T | Promise<T>): Promise<T> {
    const start = performance.now();
    try {
      const result = await fn();
      const durationMs = Math.round(performance.now() - start);
      const doneAt = utcNowIso();
      this.ledger.transitionExecution(
        ctx.executionId,
        ActionStatus.EXECUTING,
        ActionStatus.SUCCEEDED,
        {
          result_status: "SUCCESS",
          duration_ms: durationMs,
          completed_at: doneAt,
        }
      );
      this.ledger.appendEvent(
        ctx.executionId,
        EventType.ACTION_SUCCEEDED,
        ctx.agentId,
        {},
        doneAt
      );
      return result;
    } catch (err) {
      const durationMs = Math.round(performance.now() - start);
      const message = err instanceof Error ? err.message : String(err);
      const failedAt = utcNowIso();
      this.ledger.transitionExecution(
        ctx.executionId,
        ActionStatus.EXECUTING,
        ActionStatus.FAILED,
        {
          result_status: "FAILED",
          error_message: message,
          duration_ms: durationMs,
          completed_at: failedAt,
        }
      );
      this.ledger.appendEvent(
        ctx.executionId,
        EventType.ACTION_FAILED,
        ctx.agentId,
        { error: message },
        failedAt
      );
      throw err;
    }
  }
}
