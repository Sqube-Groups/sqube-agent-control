import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { ExecutionEngine } from "./executionEngine.js";
import { Decision, type PolicyFn } from "./types.js";
import { OtelEventSink } from "./telemetry/otel.js";

const allow: PolicyFn = () => Decision.ALLOW;

test("OtelEventSink does not break execution when OTel is absent", async () => {
  const dir = mkdtempSync(join(tmpdir(), "sqube-otel-"));
  const sink = new OtelEventSink();
  const engine = new ExecutionEngine({
    ledgerPath: join(dir, "l.sqlite3"),
    policy: allow,
    eventSinks: [sink],
  });
  const out = await engine.runControlled(
    {
      executionId: "sq_exec_otel_node",
      agentId: "bot",
      action: "read",
      resource: null,
      parameters: { token: "secret" },
    },
    () => 7
  );
  assert.equal(out, 7);
});
