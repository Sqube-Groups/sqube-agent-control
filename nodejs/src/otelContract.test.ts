import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { EventType } from "./events.js";

const contractDir = join(dirname(fileURLToPath(import.meta.url)), "../../tests/contract");

test("otel_semantics.json matches ledger EventType enum", () => {
  const data = JSON.parse(readFileSync(join(contractDir, "otel_semantics.json"), "utf8")) as {
    span_events: Record<string, string>;
    metrics: string[];
  };
  for (const value of Object.values(EventType)) {
    assert.ok(data.span_events[value], `missing span event mapping for ${value}`);
  }
  assert.ok(data.metrics.includes("sqube.executions.total"));
});
