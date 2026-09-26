import { ActionStatus } from "./types.js";

const TERMINAL = new Set<string>([
  ActionStatus.BLOCKED,
  ActionStatus.DENIED,
  ActionStatus.EXPIRED,
  ActionStatus.SUCCEEDED,
  ActionStatus.FAILED,
  ActionStatus.CANCELLED,
]);

const ALLOWED = new Set<string>(
  [
    [ActionStatus.REQUESTED, ActionStatus.EVALUATED],
    [ActionStatus.REQUESTED, ActionStatus.BLOCKED],
    [ActionStatus.REQUESTED, ActionStatus.FAILED],
    [ActionStatus.EVALUATED, ActionStatus.BLOCKED],
    [ActionStatus.EVALUATED, ActionStatus.WAITING_APPROVAL],
    [ActionStatus.EVALUATED, ActionStatus.EXECUTING],
    [ActionStatus.EVALUATED, ActionStatus.FAILED],
    [ActionStatus.WAITING_APPROVAL, ActionStatus.APPROVED],
    [ActionStatus.WAITING_APPROVAL, ActionStatus.DENIED],
    [ActionStatus.WAITING_APPROVAL, ActionStatus.EXPIRED],
    [ActionStatus.WAITING_APPROVAL, ActionStatus.CANCELLED],
    [ActionStatus.APPROVED, ActionStatus.EXECUTING],
    [ActionStatus.APPROVED, ActionStatus.CANCELLED],
    [ActionStatus.EXECUTING, ActionStatus.SUCCEEDED],
    [ActionStatus.EXECUTING, ActionStatus.FAILED],
    [ActionStatus.EXECUTING, ActionStatus.CANCELLED],
  ].map(([a, b]) => `${a}->${b}`)
);

export class SqubeInvalidStateTransitionError extends Error {
  constructor(
    readonly fromStatus: string,
    readonly toStatus: string,
    readonly executionId?: string
  ) {
    super(
      `Invalid execution transition ${fromStatus} -> ${toStatus}` +
        (executionId ? ` (execution_id=${executionId})` : "")
    );
    this.name = "SqubeInvalidStateTransitionError";
  }
}

export function assertTransition(
  fromStatus: string,
  toStatus: string,
  executionId?: string
): void {
  if (fromStatus === toStatus) {
    throw new SqubeInvalidStateTransitionError(fromStatus, toStatus, executionId);
  }
  if (TERMINAL.has(fromStatus)) {
    throw new SqubeInvalidStateTransitionError(fromStatus, toStatus, executionId);
  }
  const key = `${fromStatus}->${toStatus}`;
  if (!ALLOWED.has(key)) {
    throw new SqubeInvalidStateTransitionError(fromStatus, toStatus, executionId);
  }
}
