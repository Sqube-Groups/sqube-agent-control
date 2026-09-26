# sqube-agent-guard

**Sqube Agent Control (Node.js)** — v1 execution authorization for AI agents.

Deterministic policy (`ALLOW` / `BLOCK` / `REQUIRE_APPROVAL`), deferred human approval, SQLite execution ledger with hash-chained events, and optional OpenTelemetry. Behavior aligns with the shared v1 contract in the [Sqube monorepo](https://github.com/Sqube-Groups/sqube-agent-control) (`tests/contract/`).

The control plane (dashboard, remote event ingest) is operated via the **Python** package today (`pip install "sqube-agent-guard[control-plane]"`). Node focuses on the runtime execution kernel.

SDK wrapping is bypassable; this is not IAM or a network security boundary.

## Install

```bash
npm install sqube-agent-guard
```

Requires Node.js 18+.

## Quick start

```typescript
import { Decision, ExecutionGuard } from "sqube-agent-guard";

const guard = new ExecutionGuard({
  policy: (action) =>
    action === "delete_file" ? Decision.REQUIRE_APPROVAL : Decision.ALLOW,
});

const deleteFile = guard.wrapAction(
  { action: "delete_file", resource: (path: string) => `file:${path}` },
  (path: string) => {
    /* your implementation */
  }
);

await deleteFile("/tmp/example.txt");
```

## Optional OpenTelemetry

Install `@opentelemetry/api` in your app and use `OtelEventSink` (observability only; does not affect authorization).

## Documentation

- **Docs:** https://sqube-groups.github.io/sqube-agent-control/docs/intro
- **Repository:** https://github.com/Sqube-Groups/sqube-agent-control/tree/main/nodejs

## License

Apache-2.0 — Copyright © 2026 Sqube Groups
