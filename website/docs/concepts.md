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
- **Execution store** — Append-only events with hash chaining for tamper detection (Python v1).
- **SDK guard** — Application-level control; bypassable if code skips the guard.

## Security boundary

v1.0 distinguishes **SDK guard** (wrapper), **interceptor**, **MCP adapter**, and future **gateway** enforcement. See the repository `docs_internal_never_commit/` security notes for maintainers.

## SDK parity

Python ships the v1.0 core first. Node.js and Rust retain v0.1-compatible APIs while catching up to the shared contract tests in `tests/contract/`.
