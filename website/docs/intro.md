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
| Python | `sqube-agent-guard` (PyPI) | `src/sqube_agent_guard/` |
| Node.js | `sqube-agent-guard` (npm) | `nodejs/` |
| Rust | `sqube-agent-guard` (build from repo) | `rust/` |

All three implement the same v0.1 contract documented in the [v0.1 specification](./v0.1-spec).

## Installation

```bash
pip install sqube-agent-guard
npm install sqube-agent-guard
```

Rust is **not on crates.io yet**. Clone the repository and build from `rust/`:

```bash
git clone https://github.com/Sqube-Groups/sqube-agent-control.git
cd sqube-agent-control/rust
cargo build
cargo test
```

After a future crates.io publish, `cargo add sqube-agent-guard` will apply; until then use a path or git dependency (see [`rust/README.md`](https://github.com/Sqube-Groups/sqube-agent-control/blob/main/rust/README.md) in the repo).

## Where to go next

- Read the full **[v0.1 spec](./v0.1-spec)** — product promise, non-goals, ledger schema, tests required, and validation metrics.
- **[Optional LLM probes](./optional-llm-probes)** — external API test scripts only; not used for guard decisions.
- Clone the [GitHub repository](https://github.com/Sqube-Groups/sqube-agent-control) for SDK source and examples.
