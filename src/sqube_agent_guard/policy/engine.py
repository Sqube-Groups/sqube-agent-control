from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from sqube_agent_guard.core.hashing import stable_json_dumps
from sqube_agent_guard.execution.context import ExecutionContext
from sqube_agent_guard.models import Decision

Condition = Callable[[ExecutionContext], bool]


@dataclass(frozen=True)
class PolicyMetadata:
    policy_id: str
    name: str
    version: str = "1"
    description: str | None = None
    owner: str | None = None
    status: str = "ACTIVE"


@dataclass
class PolicyEvaluation:
    decision: Decision
    policy_id: str
    policy_version: str
    policy_hash: str
    reason: str
    matched_rules: list[str] = field(default_factory=list)
    failed_rules: list[str] = field(default_factory=list)
    evaluated_at: str | None = None


class Policy(Protocol):
    metadata: PolicyMetadata

    def evaluate(self, ctx: ExecutionContext) -> PolicyEvaluation: ...

    def explain(self, ctx: ExecutionContext) -> PolicyEvaluation: ...


def _policy_hash(metadata: PolicyMetadata, body: str) -> str:
    payload = f"{metadata.policy_id}:{metadata.version}:{body}"
    return hashlib.sha256(payload.encode()).hexdigest()


def _merge_decisions(decisions: list[Decision]) -> Decision:
    if Decision.BLOCK in decisions:
        return Decision.BLOCK
    if Decision.REQUIRE_APPROVAL in decisions:
        return Decision.REQUIRE_APPROVAL
    return Decision.ALLOW


@dataclass
class RulePolicy:
    metadata: PolicyMetadata
    rules: list[tuple[str, Condition, Decision]]

    def evaluate(self, ctx: ExecutionContext) -> PolicyEvaluation:
        matched: list[str] = []
        failed: list[str] = []
        decisions: list[Decision] = []
        for name, cond, decision in self.rules:
            if cond(ctx):
                matched.append(name)
                decisions.append(decision)
            else:
                failed.append(name)
        final = _merge_decisions(decisions) if decisions else Decision.ALLOW
        reason = f"{len(matched)} matched, {len(failed)} not matched"
        return PolicyEvaluation(
            decision=final,
            policy_id=self.metadata.policy_id,
            policy_version=self.metadata.version,
            policy_hash=_policy_hash(
                self.metadata, "|".join(name for name, _, _ in self.rules)
            ),
            reason=reason,
            matched_rules=matched,
            failed_rules=failed,
        )

    def explain(self, ctx: ExecutionContext) -> PolicyEvaluation:
        return self.evaluate(ctx)


def ALL(*conditions: Condition) -> Condition:
    def _all(ctx: ExecutionContext) -> bool:
        return all(c(ctx) for c in conditions)

    return _all


def ANY(*conditions: Condition) -> Condition:
    def _any(ctx: ExecutionContext) -> bool:
        return any(c(ctx) for c in conditions)

    return _any


def NOT(condition: Condition) -> Condition:
    def _not(ctx: ExecutionContext) -> bool:
        return not condition(ctx)

    return _not


def agent_is(agent_id: str) -> Condition:
    return lambda ctx: ctx.agent.agent_id == agent_id


def environment_is(env: str) -> Condition:
    return lambda ctx: (ctx.environment or ctx.agent.environment) == env


def action_is(action: str) -> Condition:
    return lambda ctx: ctx.action == action


def action_prefix(prefix: str) -> Condition:
    return lambda ctx: ctx.action.startswith(prefix)


def resource_matches(pattern: str) -> Condition:
    if pattern.endswith("/*"):
        prefix = pattern[:-1]
        return lambda ctx: (ctx.resource or "").startswith(prefix)
    return lambda ctx: ctx.resource == pattern


class CallablePolicy:
    """Wrap v0.1-style callables into v1 Policy."""

    def __init__(
        self,
        fn: Callable[..., Decision],
        metadata: PolicyMetadata | None = None,
    ) -> None:
        self._fn = fn
        self.metadata = metadata or PolicyMetadata(
            policy_id=getattr(fn, "__name__", "callable_policy"),
            name=getattr(fn, "__name__", "callable_policy"),
        )

    def evaluate(self, ctx: ExecutionContext) -> PolicyEvaluation:
        raw = self._fn(
            ctx.action,
            ctx.resource,
            ctx.agent.agent_id,
            parameters=ctx.parameters,
            context=ctx,
        )
        decision = raw if isinstance(raw, Decision) else Decision(str(raw))
        return PolicyEvaluation(
            decision=decision,
            policy_id=self.metadata.policy_id,
            policy_version=self.metadata.version,
            policy_hash=_policy_hash(self.metadata, self.metadata.policy_id),
            reason="callable policy",
            matched_rules=[self.metadata.policy_id],
        )

    def explain(self, ctx: ExecutionContext) -> PolicyEvaluation:
        return self.evaluate(ctx)
