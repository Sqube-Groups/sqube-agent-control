export class SqubeBlockedError extends Error {
  constructor(
    readonly executionId: string,
    readonly action: string
  ) {
    super(`Action '${action}' blocked (execution_id=${executionId})`);
    this.name = "SqubeBlockedError";
  }
}

export class SqubeDeniedError extends Error {
  constructor(
    readonly executionId: string,
    readonly reason: string
  ) {
    super(`Action denied: ${reason} (execution_id=${executionId})`);
    this.name = "SqubeDeniedError";
  }
}

export class SqubeGuardError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SqubeGuardError";
  }
}

export class SqubeApprovalPendingError extends SqubeGuardError {
  constructor(
    readonly executionId: string,
    readonly approvalId: string
  ) {
    super(`Approval pending (approval_id=${approvalId}, execution_id=${executionId})`);
    this.name = "SqubeApprovalPendingError";
  }
}

export class SqubeApprovalError extends SqubeGuardError {
  constructor(
    readonly approvalId: string,
    readonly reason: string
  ) {
    super(`Approval ${approvalId}: ${reason}`);
    this.name = "SqubeApprovalError";
  }
}
