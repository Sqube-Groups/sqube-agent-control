import { randomBytes } from "node:crypto";
import {
  ExecutionEngine,
  type ApprovalMode,
  type ExecutionContext,
} from "./executionEngine.js";
import {
  Decision,
  type ApprovalFn,
  type OnErrorMode,
  type PolicyFn,
} from "./types.js";
import type { EventSink } from "./eventSink.js";
import { Ledger } from "./ledger.js";

function newExecutionId(): string {
  return `sq_exec_${randomBytes(8).toString("hex")}`;
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
  approvalMode?: ApprovalMode;
  eventSinks?: EventSink[];
}

export interface WrapActionOptions {
  action: string;
  resource?: string | ((...args: unknown[]) => string);
  agentId?: string;
}

/** v1 guard — delegates to `ExecutionEngine` for shared semantics. */
export class ExecutionGuard {
  private readonly engine: ExecutionEngine;

  constructor(opts: ExecutionGuardOptions = {}) {
    this.engine = new ExecutionEngine(opts);
  }

  get ledger(): Ledger {
    return this.engine.ledger;
  }

  simulate(action: string, resource: string | null = null, agentId = "default"): Decision {
    return this.engine.simulate({
      executionId: "sq_exec_sim",
      agentId,
      action,
      resource,
      parameters: {},
    });
  }

  explain(action: string, resource: string | null = null, agentId = "default") {
    const decision = this.simulate(action, resource, agentId);
    return { decision, policyId: this.engine.policyName() };
  }

  resumeAfterApproval<T>(
    ctx: ExecutionContext,
    fn: () => T | Promise<T>,
    approvalId: string
  ): Promise<T> {
    return this.engine.resumeAfterApproval(ctx, fn, approvalId);
  }

  cancelExecution(executionId: string, reason?: string): void {
    this.engine.cancelExecution(executionId, reason);
  }

  wrapAction<T extends (...fnArgs: unknown[]) => unknown>(
    opts: WrapActionOptions,
    fn: T
  ): (...args: Parameters<T>) => Promise<Awaited<ReturnType<T>>> {
    const { action, resource, agentId = "default" } = opts;
    return async (...args: Parameters<T>): Promise<Awaited<ReturnType<T>>> => {
      const parameters =
        args.length === 1 && typeof args[0] === "object" && args[0] !== null && !Array.isArray(args[0])
          ? (args[0] as Record<string, unknown>)
          : { args };
      const ctx: ExecutionContext = {
        executionId: newExecutionId(),
        agentId,
        action,
        resource: resolveResource(resource, args as unknown[]),
        parameters,
      };
      const result = await this.engine.runControlled(ctx, () => fn(...args));
      return result as Awaited<ReturnType<T>>;
    };
  }
}
