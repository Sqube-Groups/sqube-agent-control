# Policy bundles

Sqube supports declarative **policy bundles** (JSON; YAML with optional `PyYAML`) that compile to the same rule engine used in code.

## Example (`org_default.json`)

```json
{
  "policy_id": "org-default",
  "name": "Organization default",
  "version": "1",
  "rules": [
    {
      "name": "block admin prefix",
      "when": { "action_prefix": "admin_" },
      "decision": "BLOCK"
    },
    {
      "name": "high risk actions",
      "when": { "action_in": ["send_email", "db_mutation", "file_delete"] },
      "decision": "REQUIRE_APPROVAL"
    }
  ]
}
```

## CLI

```bash
sqube-agent-guard policy validate path/to/bundle.json
sqube-agent-guard policy simulate path/to/bundle.json --action send_email
```

## Python

```python
from sqube_agent_guard import load_policy_bundle, ExecutionEngine

policy = load_policy_bundle("policies/org_default.json")
engine = ExecutionEngine(policy=policy)
```

Node.js can load the same JSON via `loadPolicyBundle` from the `sqube-agent-guard` package.
