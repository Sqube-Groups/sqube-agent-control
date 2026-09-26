"""Load declarative policy bundles (JSON; YAML when PyYAML is installed)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqube_agent_guard.execution.context import ExecutionContext
from sqube_agent_guard.models import Decision
from sqube_agent_guard.policy.engine import (
    ALL,
    ANY,
    Condition,
    PolicyMetadata,
    RulePolicy,
    action_is,
    action_prefix,
    agent_is,
    environment_is,
    resource_matches,
)


def _parse_decision(value: str) -> Decision:
    try:
        return Decision(value)
    except ValueError as exc:
        raise ValueError(f"unknown decision: {value}") from exc


def _condition_from_when(when: dict[str, Any]) -> Condition:
    if not when:
        raise ValueError("rule 'when' must not be empty")
    if "all" in when:
        nested = [_condition_from_when(item) for item in when["all"]]
        return ALL(*nested)
    if "any" in when:
        nested = [_condition_from_when(item) for item in when["any"]]
        return ANY(*nested)

    parts: list[Condition] = []
    if "agent_id" in when:
        parts.append(agent_is(str(when["agent_id"])))
    if "environment" in when:
        parts.append(environment_is(str(when["environment"])))
    if "action" in when:
        parts.append(action_is(str(when["action"])))
    if "action_prefix" in when:
        parts.append(action_prefix(str(when["action_prefix"])))
    if "action_in" in when:
        actions = {str(a) for a in when["action_in"]}
        parts.append(lambda ctx: ctx.action in actions)
    if "resource" in when:
        parts.append(resource_matches(str(when["resource"])))
    if "resource_prefix" in when:
        prefix = str(when["resource_prefix"]).rstrip("/") + "/*"
        parts.append(resource_matches(prefix))

    if not parts:
        raise ValueError(f"unsupported 'when' keys: {sorted(when.keys())}")
    if len(parts) == 1:
        return parts[0]
    return ALL(*parts)


def policy_from_dict(data: dict[str, Any]) -> RulePolicy:
    policy_id = str(data.get("policy_id") or data.get("id") or "bundle_policy")
    name = str(data.get("name") or policy_id)
    version = str(data.get("version", "1"))
    description = data.get("description")
    metadata = PolicyMetadata(
        policy_id=policy_id,
        name=name,
        version=version,
        description=str(description) if description is not None else None,
    )
    raw_rules = data.get("rules")
    if not isinstance(raw_rules, list) or not raw_rules:
        raise ValueError("bundle must include a non-empty 'rules' list")

    rules: list[tuple[str, Condition, Decision]] = []
    for idx, rule in enumerate(raw_rules):
        if not isinstance(rule, dict):
            raise ValueError(f"rule {idx} must be an object")
        rule_name = str(rule.get("name") or f"rule_{idx}")
        when = rule.get("when")
        if not isinstance(when, dict):
            raise ValueError(f"rule '{rule_name}' must include object 'when'")
        decision_raw = rule.get("decision")
        if decision_raw is None:
            raise ValueError(f"rule '{rule_name}' must include 'decision'")
        rules.append(
            (
                rule_name,
                _condition_from_when(when),
                _parse_decision(str(decision_raw)),
            )
        )
    return RulePolicy(metadata=metadata, rules=rules)


def _load_text(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(text)
    elif suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as exc:
            raise ImportError(
                "YAML policy bundles require PyYAML; install with "
                "pip install 'sqube-agent-guard[policy]'"
            ) from exc
        loaded = yaml.safe_load(text)
        if not isinstance(loaded, dict):
            raise ValueError("YAML policy bundle must be a mapping at the top level")
        data = loaded
    else:
        raise ValueError(f"unsupported policy bundle extension: {suffix}")
    if not isinstance(data, dict):
        raise ValueError("policy bundle must be a JSON object")
    return data


def load_policy_bundle(path: str | Path) -> RulePolicy:
    return policy_from_dict(_load_text(Path(path)))


def validate_policy_bundle(path: str | Path) -> list[str]:
    """Return human-readable validation errors (empty if valid)."""
    errors: list[str] = []
    try:
        load_policy_bundle(path)
    except Exception as exc:
        errors.append(str(exc))
    return errors
