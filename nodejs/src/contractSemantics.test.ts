import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { assertTransition, SqubeInvalidStateTransitionError } from "./stateMachine.js";

const fixture = JSON.parse(
  readFileSync(
    path.join(path.dirname(fileURLToPath(import.meta.url)), "../../tests/contract/v1_semantics.json"),
    "utf8"
  )
) as {
  illegal_transitions: [string, string][];
  deferred_approval_flow: string[];
};

for (const [fromStatus, toStatus] of fixture.illegal_transitions) {
  test(`illegal transition ${fromStatus} -> ${toStatus}`, () => {
    assert.throws(
      () => assertTransition(fromStatus, toStatus),
      SqubeInvalidStateTransitionError
    );
  });
}

test("deferred flow steps are legal transitions", () => {
  const flow = fixture.deferred_approval_flow as string[];
  for (let i = 0; i < flow.length - 1; i++) {
    assertTransition(flow[i], flow[i + 1]);
  }
});
