import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";
import { Decision, ActionStatus } from "./types.js";
import { ExecutionGuard } from "./guard.js";
import { SqubeBlockedError, SqubeDeniedError, SqubeGuardError } from "./errors.js";

function tmpLedger(): string {
  return path.join(fs.mkdtempSync(path.join(os.tmpdir(), "sqube-")), "ledger.sqlite3");
}

import type { PolicyFn } from "./types.js";

const alwaysAllow: PolicyFn = () => Decision.ALLOW;
const alwaysBlock: PolicyFn = () => Decision.BLOCK;
const requireApproval: PolicyFn = () => Decision.REQUIRE_APPROVAL;

const approveYes = async () => ({
  approved: true,
  approvedBy: "test",
  reason: null,
});
const approveNo = async () => ({
  approved: false,
  approvedBy: null,
  reason: "denied_by_user",
});
const approveTimeout = async () => ({
  approved: false,
  approvedBy: null,
  reason: "timeout",
});

test("ALLOW executes and writes ledger", async () => {
  const guard = new ExecutionGuard({ policy: alwaysAllow, ledgerPath: tmpLedger() });
  const run = guard.wrapAction({ action: "read" }, () => "ok");
  assert.equal(await run(), "ok");
  const row = guard.ledger.getLatest();
  assert.equal(row?.status, ActionStatus.SUCCEEDED);
});

test("BLOCK does not execute", async () => {
  const guard = new ExecutionGuard({ policy: alwaysBlock, ledgerPath: tmpLedger() });
  const run = guard.wrapAction({ action: "x" }, () => {
    throw new Error("should not run");
  });
  await assert.rejects(() => run(), SqubeBlockedError);
  assert.equal(guard.ledger.getLatest()?.status, ActionStatus.BLOCKED);
});

test("REQUIRE_APPROVAL approve", async () => {
  const guard = new ExecutionGuard({
    policy: requireApproval,
    ledgerPath: tmpLedger(),
    approvalFn: approveYes,
  });
  const run = guard.wrapAction({ action: "send_email" }, () => 42);
  assert.equal(await run(), 42);
});

test("REQUIRE_APPROVAL deny", async () => {
  const guard = new ExecutionGuard({
    policy: requireApproval,
    ledgerPath: tmpLedger(),
    approvalFn: approveNo,
  });
  const run = guard.wrapAction({ action: "send_email" }, () => 1);
  await assert.rejects(() => run(), SqubeDeniedError);
});

test("REQUIRE_APPROVAL timeout", async () => {
  const guard = new ExecutionGuard({
    policy: requireApproval,
    ledgerPath: tmpLedger(),
    approvalFn: approveTimeout,
  });
  const run = guard.wrapAction({ action: "send_email" }, () => 1);
  await assert.rejects(() => run(), SqubeDeniedError);
  assert.equal(guard.ledger.getLatest()?.status, ActionStatus.EXPIRED);
});

test("fail_closed on policy error", async () => {
  const badPolicy = () => {
    throw new Error("broken");
  };
  const guard = new ExecutionGuard({
    policy: badPolicy,
    ledgerPath: tmpLedger(),
    onError: "fail_closed",
  });
  const run = guard.wrapAction({ action: "x" }, () => "ok");
  await assert.rejects(() => run(), SqubeGuardError);
});

test("fail_open on policy error", async () => {
  const badPolicy = () => {
    throw new Error("broken");
  };
  const guard = new ExecutionGuard({
    policy: badPolicy,
    ledgerPath: tmpLedger(),
    onError: "fail_open",
  });
  const run = guard.wrapAction({ action: "x" }, () => "ok");
  assert.equal(await run(), "ok");
});
