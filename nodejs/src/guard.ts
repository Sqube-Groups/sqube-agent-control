import crypto from "node:crypto";
import { randomBytes } from "node:crypto";
import { SqubeBlockedError, SqubeDeniedError, SqubeGuardError } from "./errors.js";
import { Ledger } from "./ledger.js";
import { promptCliApproval } from "./approval.js";
import { defaultPolicy } from "./policy.js";
import { redactValue } from "./redaction.js";
import {
  ActionStatus,
  Decision,
  type ApprovalFn,
  type OnErrorMode,
  type PolicyFn,
} from "./types.js";

function utcNowIso(): string {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

function newExecutionId(): string {
  return `sq_exec_${randomBytes(8).toString("hex")}`;
}

function hashParameters(args: unknown[], kwargs: Record<string, unknown>): string {
  const payload = JSON.stringify({ args, kwargs });
  return crypto.createHash("sha256").update(payload).digest("hex");
}

function policyId(policy: PolicyFn): string {
  return policy.name || "anonymous_policy";
}

function resolveResource(
  resourceResolver: string | ((...args: unknown[]) => string) | undefined,
  args: unknown[]
): string | null {
  if (resourceResolver == null) return null;
  if (typeof resourceResolver === "string") return resourceResolver;
  return resourceResolver(...args);
}

export interface ExecutionGuardOptions {
  policy?: PolicyFn;
  ledgerPath?: string;
  approvalTimeoutSeconds?: number;
  onError?: OnErrorMode;
  approvalFn?: ApprovalFn;
}

export interface WrapActionOptions {
  action: string;
  resource?: string | ((...args: unknown[]) => string);
  agentId?: string;
}

export class ExecutionGuard {
  private policy: PolicyFn;
  readonly ledger: Ledger;
  private approvalTimeout: number;
  private onError: OnErrorMode;
  private approvalFn: ApprovalFn;

  constructor(opts: ExecutionGuardOptions = {}) {
    this.policy = opts.policy ?? defaultPolicy;
    this.ledger = new Ledger(opts.ledgerPath ?? "sqube_ledger.sqlite3");
    this.approvalTimeout = opts.approvalTimeoutSeconds ?? 300;
    this.onError = opts.onError ?? "fail_closed";
    this.approvalFn = opts.approvalFn ?? promptCliApproval;
  }

  wrapAction<T extends (...fnArgs: unknown[]) => unknown>(
    opts: WrapActionOptions,
    fn: T
  ): (...args: Parameters<T>) => Promise<Awaited<ReturnType<T>>> {
    const { action, resource, agentId = "default" } = opts;
    const wrapped = async (
      ...args: Parameters<T>
    ): Promise<Awaited<ReturnType<T>>> => {
      const result = await this.executeWrapped({
        fn,
        action,
        resourceResolver: resource,
        agentId,
        args: args as unknown[],
        kwargs: {},
      });
      return result as Awaited<ReturnType<T>>;
    };
    return wrapped;
  }

  private async executeWrapped<T extends (...fnArgs: unknown[]) => unknown>(params: {
    fn: T;
    action: string;
    resourceResolver?: string | ((...args: unknown[]) => string);
    agentId: string;
    args: unknown[];
    kwargs: Record<string, unknown>;
  }): Promise<unknown> {
    const { fn, action, resourceResolver, agentId, args, kwargs } = params;
    const executionId = newExecutionId();
    const createdAt = utcNowIso();
    const parametersHash = hashParameters(args, kwargs);
    const parametersSummary = redactValue(
      Object.keys(kwargs).length ? kwargs : args
    );
    const resource = resolveResource(resourceResolver, args);

    this.ledger.insert({
      execution_id: executionId,
      created_at: createdAt,
      agent_id: agentId,
      action,
      resource,
      parameters_hash: parametersHash,
      parameters_summary: parametersSummary,
      decision: Decision.ALLOW,
      policy_id: policyId(this.policy),
      status: ActionStatus.REQUESTED,
    });

    let decision: Decision;
    try {
      decision = this.policy(action, resource, agentId, { args, kwargs });
    } catch (err) {
      return this.handlePolicyError(executionId, fn, args, err as Error);
    }

    this.ledger.updateStatus(executionId, {
      decision,
      status: ActionStatus.EVALUATED,
    });

    if (decision === Decision.BLOCK) {
      this.ledger.updateStatus(executionId, {
        status: ActionStatus.BLOCKED,
        completed_at: utcNowIso(),
      });
      throw new SqubeBlockedError(executionId, action);
    }

    if (decision === Decision.REQUIRE_APPROVAL) {
      this.ledger.updateStatus(executionId, {
        status: ActionStatus.WAITING_APPROVAL,
      });
      const { approved, approvedBy, reason } = await this.approvalFn({
        executionId,
        agentId,
        action,
        resource,
        summary: parametersSummary,
        timeoutSeconds: this.approvalTimeout,
      });
      if (!approved) {
        const status =
          reason === "timeout" ? ActionStatus.EXPIRED : ActionStatus.DENIED;
        this.ledger.updateStatus(executionId, {
          status,
          approval_reason: reason,
          completed_at: utcNowIso(),
        });
        throw new SqubeDeniedError(executionId, reason ?? "denied");
      }
      this.ledger.updateStatus(executionId, {
        status: ActionStatus.APPROVED,
        approved_by: approvedBy,
      });
    }

    return this.runFn(executionId, fn, args);
  }

  private handlePolicyError<T extends (...fnArgs: unknown[]) => unknown>(
    executionId: string,
    fn: T,
    args: unknown[],
    error: Error
  ): unknown {
    this.ledger.updateStatus(executionId, {
      status: ActionStatus.FAILED,
      error_message: `policy_error: ${error.message}`,
      completed_at: utcNowIso(),
    });
    if (this.onError === "fail_open") {
      return this.runFn(executionId, fn, args);
    }
    throw new SqubeGuardError(`Policy evaluation failed: ${error.message}`);
  }

  private runFn<T extends (...fnArgs: unknown[]) => unknown>(
    executionId: string,
    fn: T,
    args: unknown[]
  ): ReturnType<T> {
    this.ledger.updateStatus(executionId, { status: ActionStatus.EXECUTING });
    const start = performance.now();
    try {
      const result = fn(...args) as ReturnType<T>;
      const durationMs = Math.round(performance.now() - start);
      this.ledger.updateStatus(executionId, {
        status: ActionStatus.SUCCEEDED,
        result_status: "SUCCESS",
        duration_ms: durationMs,
        completed_at: utcNowIso(),
      });
      return result;
    } catch (err) {
      const durationMs = Math.round(performance.now() - start);
      const message = err instanceof Error ? err.message : String(err);
      this.ledger.updateStatus(executionId, {
        status: ActionStatus.FAILED,
        result_status: "FAILED",
        error_message: message,
        duration_ms: durationMs,
        completed_at: utcNowIso(),
      });
      throw err;
    }
  }
}
