# CLI reference

```bash
sqube-agent-guard --ledger ./sqube_ledger.sqlite3 <command>
```

## Executions

- `executions --limit 20` — list recent runs
- `execution <execution_id>` — record + event timeline
- `ledger verify` — verify tamper-evident event hash chains

## Policy

- `simulate --action file.read --agent bot`
- `explain --action admin_delete`
- `policy validate policies/org_default.json`
- `policy simulate policies/org_default.json --action send_email`

## Approvals

Deferred mode (`ExecutionGuard(approval_mode="deferred")`):

- `approvals pending` — durable approval requests (`sq_apr_*`)
- `approvals grant <approval_id> [--by name]`
- `approvals deny <approval_id> [--reason text]`

After grant, resume in Python via `guard.resume_after_approval(ctx, fn, approval_id=...)`.

Sync mode (default) keeps the interactive CLI prompt inside the process.

## Authorize (stateless)

Pipe JSON to evaluate policy without touching the ledger:

```bash
echo '{"agent_id":"bot","action":"send_email","resource":"a@b.com"}' | \
  sqube-agent-guard authorize
```

Optional bundle:

```bash
echo '{"action":"admin_delete"}' | \
  sqube-agent-guard authorize --policy-bundle policies/org_default.json
```
