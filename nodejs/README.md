Policy and audit layer for **AI agent actions** in Node.js.

Intercept tool calls and side effects, decide **allow**, **block**, or **require approval**, then record a **tamper-evident** SQLite ledger. Part of [Sqube Agent Control](https://sqube-groups.github.io/sqube-agent-control/docs/intro) (Python SDK + optional control plane; this package is the Node runtime).

```bash
npm install sqube-agent-guard
```

**Node.js 18+** · [Documentation](https://sqube-groups.github.io/sqube-agent-control/docs/intro) · [Source](https://github.com/Sqube-Groups/sqube-agent-control/tree/main/nodejs)

## Quick start

```typescript
import { Decision, ExecutionGuard } from "sqube-agent-guard";

const guard = new ExecutionGuard({
  ledgerPath: "./sqube_ledger.sqlite3",
  policy: (action) =>
    action === "delete_file" ? Decision.REQUIRE_APPROVAL : Decision.ALLOW,
});

const deleteFile = guard.wrapAction(
  { action: "delete_file", resource: (path: string) => `file:${path}` },
  async (path: string) => {
    /* your logic */
    return { ok: true, path };
  }
);

await deleteFile("/tmp/report.pdf");
```

**Policy outcomes**

- **ALLOW** — handler runs; outcome is logged.
- **BLOCK** — handler does not run (`SqubeBlockedError`).
- **REQUIRE_APPROVAL** — inline `approvalFn` or deferred grant + resume (see below).

> Dashboard, teams/RBAC, and remote event ingest: use Python  
> `pip install "sqube-agent-guard[control-plane]"` — not included in this npm package.

## Examples

### Inline approval

```typescript
import { Decision, ExecutionGuard } from "sqube-agent-guard";

const guard = new ExecutionGuard({
  ledgerPath: "./sqube_ledger.sqlite3",
  policy: (action) =>
    action === "send_email" ? Decision.REQUIRE_APPROVAL : Decision.ALLOW,
  approvalFn: async () => ({
    approved: true,
    approvedBy: "operator@example.com",
    reason: null,
  }),
});

const sendEmail = guard.wrapAction(
  { action: "send_email", resource: "user@example.com" },
  async () => ({ sent: true })
);

await sendEmail();
```

### Deferred approval (pause → grant → resume)

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
  executionId: "sq_exec_001",
  agentId: "bot",
  action: "send_email",
  resource: "a@b.com",
  parameters: { to: "a@b.com" },
};

let approvalId = "";
try {
  await engine.runControlled(ctx, () => "sent");
} catch (err) {
  if (err instanceof SqubeApprovalPendingError) approvalId = err.approvalId;
}

engine.ledger.grantApproval(approvalId, "human", new Date().toISOString());
const result = await engine.resumeAfterApproval(ctx, () => "sent", approvalId);
```

### Simulate policy (no execution)

```typescript
const guard = new ExecutionGuard({
  policy: (action) => (action === "admin_delete" ? Decision.BLOCK : Decision.ALLOW),
});

guard.simulate("admin_delete", "users/1"); // Decision.BLOCK
guard.explain("file.read", "file:/tmp/x");
```

### JSON policy bundle

```typescript
import { ExecutionGuard, loadPolicyBundle } from "sqube-agent-guard";

const policy = loadPolicyBundle("/path/to/org_default.json");
const guard = new ExecutionGuard({
  ledgerPath: "./sqube_ledger.sqlite3",
  policy: (action, resource, agentId) => policy(action, resource, agentId),
});
```

### OpenTelemetry (optional)

```typescript
import { Decision, ExecutionGuard, OtelEventSink } from "sqube-agent-guard";

const guard = new ExecutionGuard({
  policy: () => Decision.ALLOW,
  ledgerPath: "./sqube_ledger.sqlite3",
  eventSinks: [new OtelEventSink()],
});
```

Install `@opentelemetry/api` in your app when wiring a real tracer. OTel does not change authorization decisions.

## More in the repo

| Topic | Link |
|-------|------|
| Guard tests (allow / block / approval) | [`guard.test.ts`](https://github.com/Sqube-Groups/sqube-agent-control/blob/main/nodejs/src/guard.test.ts) |
| Deferred contract | [`deferredContract.test.ts`](https://github.com/Sqube-Groups/sqube-agent-control/blob/main/nodejs/src/deferredContract.test.ts) |
| Cross-language semantics | [`tests/contract/`](https://github.com/Sqube-Groups/sqube-agent-control/tree/main/tests/contract) |
| Python control plane E2E | [`examples/python/`](https://github.com/Sqube-Groups/sqube-agent-control/tree/main/examples/python) |

## License

Apache-2.0 — Copyright © 2026 Sqube Groups
