import assert from "node:assert/strict";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { Decision } from "./types.js";
import { loadPolicyBundle } from "./policyBundle.js";

const bundlePath = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../tests/fixtures/policies/org_default.json"
);

test("org_default bundle matches contract decisions", () => {
  const policy = loadPolicyBundle(bundlePath);
  assert.equal(policy("file.read", "file:/tmp/x", "bot"), Decision.ALLOW);
  assert.equal(policy("admin_delete", null, "bot"), Decision.BLOCK);
  assert.equal(policy("send_email", "user@example.com", "bot"), Decision.REQUIRE_APPROVAL);
});
