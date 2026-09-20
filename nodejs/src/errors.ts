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
