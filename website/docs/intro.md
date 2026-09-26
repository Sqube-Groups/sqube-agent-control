---
sidebar_position: 1
slug: /intro
title: Introduction
---

# Sqube Agent Control

**Open-source execution authorization infrastructure for AI agents.**

> AI proposes. Sqube decides. Sqube records what actually happened.

v1.0 covers deterministic policy, approvals, tamper-evident ledgers, optional OpenTelemetry, a **local control plane** (dashboard + APIs), and **remote event ingestion** (agents export ledger events; the plane does not authorize runtime execution).

## Status

**v1.0** — Python is the reference SDK; Node and Rust share the synchronous execution contract (`tests/contract/`). SDK-level control is bypassable if application code skips the guard.

## Install

```bash
pip install sqube-agent-guard
npm install sqube-agent-guard
```

Rust: build from the repository `rust/` directory (crates.io pending).

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

## Platform operator path

```bash
pip install "sqube-agent-guard[control-plane]"
sqube-agent-guard serve --data-dir .sqube
```

First visit: **http://127.0.0.1:8080/setup** — create the administrator account in the browser (no terminal password required).

## Documentation map

| Topic | Page |
|-------|------|
| Concepts | [Concepts](./concepts) |
| Architecture | [Architecture](./architecture) |
| Control plane | [Control plane](./control-plane) |
| Event ingestion & SSE | [Event ingestion](./event-ingestion) |
| Sign-in, roles, SSO | [Control plane authentication](./control-plane-auth) |
| Policies | [Policies](./policies) |
| CLI | [CLI](./cli) |
| Observability | [Observability](./observability) |

Source: [GitHub](https://github.com/Sqube-Groups/sqube-agent-control)
