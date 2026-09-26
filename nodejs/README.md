# sqube-agent-guard

**Sqube Agent Control (Node.js)** — wrap agent actions, run policy, optionally require human approval, and append hash-chained events to a SQLite ledger.

| Decision | What happens |
|----------|----------------|
| `ALLOW` | Your function runs; success is recorded. |
| `BLOCK` | Your function does **not** run (`SqubeBlockedError`). |
| `REQUIRE_APPROVAL` | Waits for approval (inline callback or deferred grant in the ledger). |

**Control plane** (dashboard, RBAC, remote ingest) is **Python only**: `pip install "sqube-agent-guard[control-plane]"`. This package is the Node **execution kernel**.

Requires **Node.js 18+**.

```bash
npm install sqube-agent-guard
```

---

## Example 1 — Wrap one action (allow vs block)

```typescript
import { Decision, ExecutionGuard, SqubeBlockedError } from "sqube-agent-guard";

const guard = new ExecutionGuard({
  ledgerPath: "./sqube_ledger.sqlite3",
  policy: (action) =>
    action === "delete_file" ? Decision.REQUIRE_APPROVAL : Decision.ALLOW,
});

const deleteFile = guard.wrapAction(
  {
    action: "delete_file",
    resource: (path: string) => `file:${path}`,
    agentId: "my-agent",
  },
  async (path: string) => {
    // your real delete logic
    return { deleted: path };
  }
);

// Allowed read-style actions would use Decision.ALLOW in policy.
try {
  await deleteFile("/tmp/report.pdf");
} catch (err) {
  if (err instanceof SqubeBlockedError) {
    console.log("blocked by policy");
  }
}
```

---

## Example 2 — Inline approval (human-in-the-loop)

Use when something like `send_email` must be approved before the handler runs:

```typescript
import { Decision, ExecutionGuard } from "sqube-agent-guard";

const guard = new ExecutionGuard({
  ledgerPath: "./sqube_ledger.sqlite3",
  policy: (action) =>
    action === "send_email" ? Decision.REQUIRE_APPROVAL : Decision.ALLOW,
  approvalFn: async () => ({
    approved: true, // set false to deny
    approvedBy: "operator@example.com",
    reason: null,
  }),
});

const sendEmail = guard.wrapAction(
  { action: "send_email", resource: "user@example.com" },
  async () => ({ sent: true })
);

await sendEmail(); // runs only after approvalFn returns approved: true
```

---

## Example 3 — Deferred approval (pause, grant, resume)

Use `ExecutionEngine` with `approvalMode: "deferred"`. The run stops with `SqubeApprovalPendingError`; grant on the ledger, then `resumeAfterApproval` with the **same** `executionId`.

```typescript
import {
  Decision,
  ExecutionEngine,
  SqubeApprovalPendingError,
} from "sqube-agent-guard";

const engine = new ExecutionEngine({
  ledgerPath: "./sqube_ledger.sqlite3",
  approvalMode: "deferred",
  policy: (action) =>
    action === "send_email" ? Decision.REQUIRE_APPROVAL : Decision.ALLOW,
});

const ctx = {
  executionId: "sq_exec_my_run_001",
  agentId: "bot",
  action: "send_email",
  resource: "a@b.com",
  parameters: { to: "a@b.com" },
};

let approvalId = "";
try {
  await engine.runControlled(ctx, () => "sent");
} catch (err) {
  if (err instanceof SqubeApprovalPendingError) {
    approvalId = err.approvalId;
  }
}

engine.ledger.grantApproval(approvalId, "human", new Date().toISOString());

const result = await engine.resumeAfterApproval(ctx, () => "sent", approvalId);
console.log(result); // "sent"
```

---

## Example 4 — Simulate before you execute

Dry-run policy without running the handler:

```typescript
import { Decision, ExecutionGuard } from "sqube-agent-guard";

const guard = new ExecutionGuard({
  policy: (action) =>
    action === "admin_delete" ? Decision.BLOCK : Decision.ALLOW,
});

console.log(guard.simulate("admin_delete", "users/1")); // Decision.BLOCK
console.log(guard.explain("file.read", "file:/tmp/x"));
// { decision: Decision.ALLOW, policyId: "..." }
```

---

## Example 5 — JSON policy bundle

Load the same style of rules as Python (path to a bundle file in your app):

```typescript
import { ExecutionGuard, loadPolicyBundle } from "sqube-agent-guard";

const policy = loadPolicyBundle("/path/to/org_default.json");

const guard = new ExecutionGuard({
  ledgerPath: "./sqube_ledger.sqlite3",
  policy: (action, resource, agentId) => policy(action, resource, agentId),
});
```

Fixture used in tests: [`tests/fixtures/policies/org_default.json`](https://github.com/Sqube-Groups/sqube-agent-control/blob/main/tests/fixtures/policies/org_default.json).

---

## Example 6 — OpenTelemetry (optional)

Observability only; does not change allow/block decisions.

```typescript
import { Decision, ExecutionGuard, OtelEventSink } from "sqube-agent-guard";

const guard = new ExecutionGuard({
  policy: () => Decision.ALLOW,
  ledgerPath: "./sqube_ledger.sqlite3",
  eventSinks: [new OtelEventSink()],
});
```

Install `@opentelemetry/api` in your application if you attach a real tracer.

---

## More examples in the repo

| What | Where |
|------|--------|
| Guard allow / block / approval | [`nodejs/src/guard.test.ts`](https://github.com/Sqube-Groups/sqube-agent-control/blob/main/nodejs/src/guard.test.ts) |
| Deferred approval contract | [`nodejs/src/deferredContract.test.ts`](https://github.com/Sqube-Groups/sqube-agent-control/blob/main/nodejs/src/deferredContract.test.ts) |
| Cross-language semantics | [`tests/contract/`](https://github.com/Sqube-Groups/sqube-agent-control/tree/main/tests/contract) |
| Python agent + control plane E2E | [`examples/python/`](https://github.com/Sqube-Groups/sqube-agent-control/tree/main/examples/python) |

## Documentation

- **Docs:** https://sqube-groups.github.io/sqube-agent-control/docs/intro  
- **Source:** https://github.com/Sqube-Groups/sqube-agent-control/tree/main/nodejs  

## License

Apache-2.0 — Copyright © 2026 Sqube Groups
