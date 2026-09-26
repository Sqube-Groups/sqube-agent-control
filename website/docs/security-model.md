---
sidebar_position: 3
title: Security model
---

# Security model (v1.0)

Sqube Agent Control is **execution authorization infrastructure**, not a guarantee that every side effect in a process is impossible without Sqube.

## Enforcement boundaries

| Layer | What it controls | Bypass risk |
|-------|------------------|-------------|
| **SDK guard** | Calls wrapped with `ExecutionGuard` / engine | High — any unwrapped call skips Sqube |
| **Interceptor** | Central hook around a code path | Medium — depends on integration |
| **MCP adapter** | Tool calls routed through the adapter | Medium — direct MCP bypass possible |
| **Future gateway** | Network-level enforcement | Lower — outside agent process |

Document and design for the boundary you actually deploy.

## Defaults

- **Fail closed** on policy, identity, and storage errors unless `on_error="fail_open"` is explicitly set.
- **No secrets in evidence** — parameters are hashed; summaries are redacted.
- **Deterministic policy** — no LLM as the authorization authority.

## Identity

`agent_id` and `principal` are **application-supplied** unless you integrate a real identity provider. Sqube does not cryptographically prove agent identity in the local SDK alone.

## Ledger integrity

Event hash chains detect tampering of stored events. This supports audit and debugging; it is not a legal-grade proof without broader controls.

See [Threat model](./threat-model) for structured risks and mitigations.
