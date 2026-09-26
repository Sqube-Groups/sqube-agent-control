# sqube-agent-guard

**Sqube Execution Guard** is a developer-side helper for v0.1 experiments: it wraps consequential actions, evaluates a deterministic policy (`ALLOW` / `BLOCK` / `REQUIRE_APPROVAL`), can pause for human approval via CLI, and appends decisions to a SQLite ledger. SDK wrapping is bypassable—this is **not** a security boundary and does not replace IAM, gateways, or other controls.

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

## Documentation

- **Docs site (intro):** [https://sqube-groups.github.io/sqube-agent-control/docs/intro](https://sqube-groups.github.io/sqube-agent-control/docs/intro)
- **Source & examples:** [https://github.com/Sqube-Groups/sqube-agent-control](https://github.com/Sqube-Groups/sqube-agent-control) (optional LLM probe scripts live under `examples/` in the repo)

## License

Apache-2.0 — Copyright © 2026 Sqube Groups
