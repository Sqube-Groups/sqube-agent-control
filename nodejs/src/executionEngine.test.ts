import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";
import { SqubeApprovalPendingError } from "./errors.js";
import { ExecutionEngine, type ExecutionContext } from "./executionEngine.js";
import { ActionStatus, Decision } from "./types.js";

function tmpLedger(): string {
  return path.join(fs.mkdtempSync(path.join(os.tmpdir(), "sqube-engine-")), "ledger.sqlite3");
}

const requireEmail = (action: string): Decision =>
  action === "send_email" ? Decision.REQUIRE_APPROVAL : Decision.ALLOW;

test("deferred approval grant and resume", async () => {
  const ledgerPath = tmpLedger();
  const engine = new ExecutionEngine({
    policy: requireEmail,
    ledgerPath,
    approvalMode: "deferred",
  });
  const ctx: ExecutionContext = {
    executionId: "sq_exec_node_def",
    agentId: "bot",
    action: "send_email",
    resource: "a@b.com",
    parameters: { to: "a@b.com" },
  };
  let approvalId = "";
  try {
    await engine.runControlled(ctx, () => "sent");
  } catch (err) {
    assert.ok(err instanceof SqubeApprovalPendingError);
    approvalId = err.approvalId;
  }
  assert.ok(approvalId.startsWith("sq_apr_"));
  engine.ledger.grantApproval(approvalId, "human", "2026-01-02T00:00:00Z");
  const result = await engine.resumeAfterApproval(ctx, () => "sent", approvalId);
  assert.equal(result, "sent");
  assert.equal(
    engine.ledger.getExecution(ctx.executionId)?.status,
    ActionStatus.SUCCEEDED
  );
});

test("allow path succeeds with event chain", async () => {
  const ledgerPath = tmpLedger();
  const engine = new ExecutionEngine({ ledgerPath, approvalMode: "deferred" });
  const ctx: ExecutionContext = {
    executionId: "sq_exec_node_allow",
    agentId: "bot",
    action: "file.read",
    resource: "file:/tmp/x",
    parameters: {},
  };
  assert.equal(await engine.runControlled(ctx, () => 1), 1);
  assert.equal(engine.ledger.verifyChain(ctx.executionId), true);
});
