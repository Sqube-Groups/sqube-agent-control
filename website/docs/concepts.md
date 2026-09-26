---
sidebar_position: 2
title: Concepts
---

# Concepts (v1.0)

Sqube Agent Control sits between an agent and consequential side effects:

```text
Agent → Action request → Policy → ALLOW / BLOCK / REQUIRE_APPROVAL → Execution → Evidence
```

## Core ideas

- **Agent identity** — Every controlled execution carries an `agent_id` (and optional environment metadata).
- **Principal** — Who the action is performed on behalf of (user or service).
- **Delegated authority** — Optional delegation chain with scopes and expiry (Python v1).
- **Policy** — Deterministic evaluation; LLMs are not the authorization authority.
- **Decisions** — `ALLOW`, `BLOCK`, or `REQUIRE_APPROVAL`.
- **Execution store** — Append-only events with hash chaining for tamper detection (Python and Node; see SDK scope in the repo `tests/contract/V1_SYNC_SEMANTICS.md`).
- **SDK guard** — Application-level control; bypassable if code skips the guard.

## Security boundary

v1.0 distinguishes **SDK guard** (wrapper), **interceptor**, **MCP adapter**, and future **gateway** enforcement. See the repository `docs_internal_never_commit/` security notes for maintainers.

## SDK parity (v1.0)

All three SDKs share **synchronous v1 execution semantics** and the contract in `tests/contract/`. Python is the reference implementation (CLI, idempotency, delegation, MCP adapter). Node and Rust implement `ExecutionEngine` and pass the same policy/state/deferred tests; optional Python-only features are listed in `tests/contract/V1_SYNC_SEMANTICS.md`.
