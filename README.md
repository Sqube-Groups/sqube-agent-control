# Sqube Agent Control

> Open-source infrastructure for controlling AI agent actions.

Sqube Agent Control provides developers with primitives for evaluating and controlling actions performed by AI agents.

The project is currently in early experimental development.

## Status

**Experimental — API may change.**

The current release focuses on a small Python-first execution-control layer.

## Core concepts

Sqube Agent Control currently works around a few simple concepts:

* **Actions** — operations an agent wants to perform
* **Policies** — application-defined rules for evaluating actions
* **Decisions** — whether an action can proceed
* **Approvals** — optional human decisions for selected actions
* **Execution records** — structured information about action execution

## Quick start

```python
from sqube_guard import ExecutionGuard, Decision


def policy(action, resource, context):
    if action == "delete_file":
        return Decision.REQUIRE_APPROVAL

    return Decision.ALLOW


guard = ExecutionGuard(policy=policy)


@guard.wrap_action(
    action="delete_file",
    resource=lambda path: f"file:{path}",
)
def delete_file(path):
    # Your action
    ...


delete_file("/tmp/example.txt")
```

The policy determines how the action should proceed before the wrapped function executes.

## Decisions

The current API supports:

```text
ALLOW
BLOCK
REQUIRE_APPROVAL
```

Policies are application-defined and do not require an LLM.

## Installation

```bash
pip install sqube-guard
```

> Packaging and release status are experimental during early development.

## Development

Clone the repository:

```bash
git clone https://github.com/Sqube-Groups/sqube-agent-control.git
cd sqube-agent-control
```

Install the development dependencies and run the tests:

```bash
pytest
```

## Project structure

The project is organized around the core execution-control primitives:

```text
src/
└── sqube_guard/
    ├── guard.py
    ├── policy.py
    ├── models.py
    ├── ledger.py
    ├── approval.py
    └── redaction.py

tests/
examples/
```

The structure may evolve as the project develops.

## Contributing

Contributions and feedback are welcome.

For larger changes, please open an
