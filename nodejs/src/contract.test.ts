import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { defaultPolicy } from "./policy.js";
import { Decision } from "./types.js";

const fixturesDir = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../tests/contract/fixtures"
);

for (const file of readdirSync(fixturesDir).filter((f) => f.endsWith(".json"))) {
  test(`contract fixture ${file}`, () => {
    const data = JSON.parse(readFileSync(path.join(fixturesDir, file), "utf8")) as {
      name: string;
      context: { agent_id: string; action: string; resource?: string | null };
      expected_decision: string;
    };
    assert.equal(data.name.length > 0, true);
    const decision = defaultPolicy(
      data.context.action,
      data.context.resource ?? null,
      data.context.agent_id
    );
    assert.equal(decision, data.expected_decision as Decision);
  });
}
