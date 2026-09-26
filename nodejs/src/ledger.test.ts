import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";
import { EventType } from "./events.js";
import { Ledger } from "./ledger.js";
import { ActionStatus, Decision } from "./types.js";

function tmpLedger(): string {
  return path.join(fs.mkdtempSync(path.join(os.tmpdir(), "sqube-ledger-")), "ledger.sqlite3");
}

test("appendEvent builds verifiable hash chain", () => {
  const ledger = new Ledger(tmpLedger());
  ledger.appendEvent("e1", EventType.ACTION_REQUESTED, "agent", { a: 1 }, "t1");
  ledger.appendEvent("e1", EventType.POLICY_EVALUATED, "policy", { d: "ALLOW" }, "t2");
  assert.equal(ledger.verifyChain("e1"), true);
  assert.equal(ledger.getEvents("e1").length, 2);
});

test("listExecutions filters by status", () => {
  const ledger = new Ledger(tmpLedger());
  ledger.insert({
    execution_id: "a",
    created_at: "t",
    agent_id: "bot",
    action: "x",
    resource: null,
    parameters_hash: "h",
    parameters_summary: null,
    decision: Decision.REQUIRE_APPROVAL,
    policy_id: "p",
    status: ActionStatus.WAITING_APPROVAL,
  });
  ledger.insert({
    execution_id: "b",
    created_at: "t",
    agent_id: "bot",
    action: "y",
    resource: null,
    parameters_hash: "h",
    parameters_summary: null,
    decision: Decision.ALLOW,
    policy_id: "p",
    status: ActionStatus.SUCCEEDED,
  });
  const pending = ledger.listExecutions(10, ActionStatus.WAITING_APPROVAL);
  assert.equal(pending.length, 1);
  assert.equal(pending[0].execution_id, "a");
});
