import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { SqubeApprovalPendingError } from "./errors.js";
import { ExecutionEngine, type ExecutionContext } from "./executionEngine.js";
import { Decision } from "./types.js";
import fs from "node:fs";
import os from "node:os";

const fixture = JSON.parse(
  readFileSync(
    path.join(path.dirname(fileURLToPath(import.meta.url)), "../../tests/contract/deferred_approval.json"),
    "utf8"
  )
) as {
  context: {
    agent_id: string;
    action: string;
    resource: string | null;
    parameters: Record<string, unknown>;
  };
  grant_at: string;
  expected_after_pending_status: string;
  expected_after_grant_status: string;
  expected_final_status: string;
  resume_result: string;
};

test("deferred_approval.json cross-contract scenario", async () => {
  const ledgerPath = path.join(
    fs.mkdtempSync(path.join(os.tmpdir(), "sqube-def-")),
    "ledger.sqlite3"
  );
  const engine = new ExecutionEngine({
    ledgerPath,
    approvalMode: "deferred",
    policy: (action) =>
      action === "send_email" ? Decision.REQUIRE_APPROVAL : Decision.ALLOW,
  });
  const ctx: ExecutionContext = {
    executionId: "sq_exec_contract_def",
    agentId: fixture.context.agent_id,
    action: fixture.context.action,
    resource: fixture.context.resource,
    parameters: fixture.context.parameters,
  };
  let approvalId = "";
  try {
    await engine.runControlled(ctx, () => fixture.resume_result);
  } catch (err) {
    assert.ok(err instanceof SqubeApprovalPendingError);
    approvalId = err.approvalId;
  }
  assert.equal(
    engine.ledger.getExecution(ctx.executionId)?.status,
    fixture.expected_after_pending_status
  );
  engine.ledger.grantApproval(approvalId, "human", fixture.grant_at);
  assert.equal(
    engine.ledger.getExecution(ctx.executionId)?.status,
    fixture.expected_after_grant_status
  );
  const out = await engine.resumeAfterApproval(ctx, () => fixture.resume_result, approvalId);
  assert.equal(out, fixture.resume_result);
  assert.equal(engine.ledger.getExecution(ctx.executionId)?.status, fixture.expected_final_status);
});
