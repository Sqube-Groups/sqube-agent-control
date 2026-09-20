---
sidebar_position: 1
slug: /intro
title: Introduction
---

# Sqube Agent Control

**Sqube Execution Guard (v0.1)** wraps consequential actions, deterministically decides `ALLOW` / `BLOCK` / `REQUIRE_APPROVAL`, optionally pauses for a human (CLI in Python v0.1), and writes an append-only SQLite execution record.

## Status

**Experimental — API may change.** SDK wrapping is bypassable. This is not a replacement for IAM, gateways, or production security controls.

## SDKs

| Language | Package | Source |
|----------|---------|--------|
| Python | `sqube-guard` | `src/sqube_guard/` |
| Node.js | `@sqube/guard` | `nodejs/` |
| Rust | `sqube-guard` | `rust/` |

All three implement the same v0.1 contract documented in the [v0.1 specification](./v0.1-spec).

## Where to go next

- Read the full **[v0.1 spec](./v0.1-spec)** — product promise, non-goals, ledger schema, tests required, and validation metrics.
- **[Optional LLM probes](./optional-llm-probes)** — external API test scripts only; not used for guard decisions.
- Clone the [GitHub repository](https://github.com/Sqube-Groups/sqube-agent-control) for SDK source and examples.
