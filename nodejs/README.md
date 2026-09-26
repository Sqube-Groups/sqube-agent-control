# sqube-agent-guard

**Sqube Agent Control (Node.js)** — execution authorization for AI agents with v1 synchronous semantics.

Wrap actions, evaluate policy (`ALLOW` / `BLOCK` / `REQUIRE_APPROVAL`), deferred approval, and hash-chained ledger events. Shared behavior is covered by `tests/contract/` in the monorepo. SDK wrapping is bypassable; this is not a replacement for IAM or network controls.

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

- Docs: https://sqube-groups.github.io/sqube-agent-control/docs/intro
- Repository: https://github.com/Sqube-Groups/sqube-agent-control

## License

Apache-2.0 — Copyright © 2026 Sqube Groups
