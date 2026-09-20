---
sidebar_position: 1
slug: /intro
title: Introduction
---

# Sqube Agent Control

**Sqube Execution Guard (v0.1)** wraps consequential actions, deterministically decides `ALLOW` / `BLOCK` / `REQUIRE_APPROVAL`, optionally pauses for a human (CLI in Python v0.1), and writes an append-only SQLite execution record.

## Status

**Experimental — API may change.** SDK wrapping is bypassable. This is not a replacement for IAM, gateways, or production security controls.

## What it does

- **Policy hook** — Your code supplies a deterministic policy; no LLM in the decision path for v0.1.
- **Decisions** — `ALLOW`, `BLOCK`, or `REQUIRE_APPROVAL` before the wrapped action runs.
- **Ledger** — Append-only SQLite record of decisions for audit and experiments.
- **SDKs** — Python (PyPI), Node.js (npm), and Rust (build from the repo).

## SDKs

| Language | Package | Source |
|----------|---------|--------|
| Python | `sqube-agent-guard` (PyPI) | [`src/sqube_agent_guard/`](https://github.com/Sqube-Groups/sqube-agent-control/tree/main/src/sqube_agent_guard) |
| Node.js | `sqube-agent-guard` (npm) | [`nodejs/`](https://github.com/Sqube-Groups/sqube-agent-control/tree/main/nodejs) |
| Rust | `sqube-agent-guard` (build from repo) | [`rust/`](https://github.com/Sqube-Groups/sqube-agent-control/tree/main/rust) |

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

- [GitHub repository](https://github.com/Sqube-Groups/sqube-agent-control) — source, examples, and issue tracker.
- [README on GitHub](https://github.com/Sqube-Groups/sqube-agent-control/blob/main/README.md) — quick starts, development, tests, and optional LLM probe examples.
