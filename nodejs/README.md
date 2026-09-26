# sqube-agent-guard

**Sqube Agent Control (Node.js)** — v1 execution authorization for AI agents.

Wrap consequential actions, evaluate deterministic policy (`ALLOW` / `BLOCK` / `REQUIRE_APPROVAL`), optional deferred human approval, and record tamper-evident execution events in a SQLite ledger (hash-chained). Optional OpenTelemetry hooks align with the shared v1 contract in [`tests/contract/`](https://github.com/Sqube-Groups/sqube-agent-control/tree/main/tests/contract/).

The **control plane** (dashboard, teams/RBAC, remote event ingest) ships with the **Python** package: `pip install "sqube-agent-guard[control-plane]"` then `sqube-agent-guard serve` (first run: `/setup`). This npm package is the **runtime execution kernel** for Node.

SDK wrapping is bypassable if application code skips the guard. This is **not** IAM, a network security boundary, or host-level enforcement.

## Install

```bash
npm install sqube-agent-guard
```

Requires **Node.js 18+**.

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

## Related packages

| Runtime | Package |
|--------|---------|
| Node.js (this) | [npm `sqube-agent-guard`](https://www.npmjs.com/package/sqube-agent-guard) |
| Python (reference SDK + control plane) | [PyPI `sqube-agent-guard`](https://pypi.org/project/sqube-agent-guard/) |
| Rust | Build from [`rust/`](https://github.com/Sqube-Groups/sqube-agent-control/tree/main/rust) (not on crates.io yet) |

## Documentation

- **Docs:** https://sqube-groups.github.io/sqube-agent-control/docs/intro
- **Source:** https://github.com/Sqube-Groups/sqube-agent-control/tree/main/nodejs
- **Issues:** https://github.com/Sqube-Groups/sqube-agent-control/issues

## License

Apache-2.0 — Copyright © 2026 Sqube Groups
