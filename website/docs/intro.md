---
sidebar_position: 1
slug: /intro
title: Introduction
---

# Sqube Agent Control

**Open-source execution authorization infrastructure for AI agents.**

> AI proposes. Sqube decides. Sqube records what actually happened.

v1.0 establishes agent identity, composable deterministic policies, approvals, tamper-evident execution events, simulation/explain APIs, and an MCP adapter surface (Python). Simple v0.1-style `ExecutionGuard` wrapping remains supported.

## Status

**v1.0.0** — Shared synchronous execution contract across Python, Node, and Rust; Python is the full reference SDK. Node uses Promises for I/O but not a separate async execution model. SDK-level control is bypassable if application code skips the guard.

## Install

```bash
pip install sqube-agent-guard
npm install sqube-agent-guard
```

Rust: clone the repository and build from `rust/` (crates.io publish pending).

## Quick start (Python)

```python
from sqube_agent_guard import Decision, ExecutionGuard

def policy(action, resource, agent_id, **ctx):
    if action == "email.send":
        return Decision.REQUIRE_APPROVAL
    return Decision.ALLOW

guard = ExecutionGuard(policy=policy)

@guard.wrap_action(action="email.send", resource="customer@example.com")
def send_email():
    ...

send_email()
```

## Documentation

- [Concepts](./concepts) — domain model and security boundaries
- [GitHub README](https://github.com/Sqube-Groups/sqube-agent-control) — development and contributing
