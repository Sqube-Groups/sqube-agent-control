from __future__ import annotations

from pathlib import Path

import pytest

from sqube_guard import Decision, ExecutionGuard
from sqube_guard.exceptions import SqubeBlockedError, SqubeDeniedError, SqubeGuardError
from sqube_guard.models import ActionStatus
from sqube_guard.policy import default_policy


def _ledger_path(tmp: Path) -> str:
    return str(tmp / "ledger.sqlite3")


def _always_allow(_a, _r, _id, **_) -> Decision:
    return Decision.ALLOW


def _always_block(_a, _r, _id, **_) -> Decision:
    return Decision.BLOCK


def _require_approval(_a, _r, _id, **_) -> Decision:
    return Decision.REQUIRE_APPROVAL


def _approve_yes(**_kwargs):
    return True, "test_user", None


def _approve_no(**_kwargs):
    return False, None, "denied_by_user"


def _approve_timeout(**_kwargs):
    return False, None, "timeout"


def test_allow_executes_and_writes_ledger(tmp_path: Path) -> None:
    guard = ExecutionGuard(policy=_always_allow, ledger_path=_ledger_path(tmp_path))
    ran = {"ok": False}

    @guard.wrap_action(action="read_file")
    def read_file() -> str:
        ran["ok"] = True
        return "data"

    assert read_file() == "data"
    assert ran["ok"]
    row = guard._ledger.get_latest()
    assert row is not None
    assert row["status"] == ActionStatus.SUCCEEDED.value
    assert row["decision"] == Decision.ALLOW.value


def test_block_does_not_execute(tmp_path: Path) -> None:
    guard = ExecutionGuard(policy=_always_block, ledger_path=_ledger_path(tmp_path))
    ran = {"ok": False}

    @guard.wrap_action(action="danger")
    def danger() -> None:
        ran["ok"] = True

    with pytest.raises(SqubeBlockedError):
        danger()
    assert not ran["ok"]
    row = guard._ledger.get_latest()
    assert row["status"] == ActionStatus.BLOCKED.value


def test_require_approval_approve_executes(tmp_path: Path) -> None:
    guard = ExecutionGuard(
        policy=_require_approval,
        ledger_path=_ledger_path(tmp_path),
        approval_fn=_approve_yes,
    )
    ran = {"ok": False}

    @guard.wrap_action(action="send_email", resource="a@b.com")
    def send_email() -> None:
        ran["ok"] = True

    send_email()
    assert ran["ok"]
    row = guard._ledger.get_latest()
    assert row["status"] == ActionStatus.SUCCEEDED.value
    assert row["approved_by"] == "test_user"


def test_require_approval_deny(tmp_path: Path) -> None:
    guard = ExecutionGuard(
        policy=_require_approval,
        ledger_path=_ledger_path(tmp_path),
        approval_fn=_approve_no,
    )

    @guard.wrap_action(action="send_email")
    def send_email() -> None:
        return 1

    with pytest.raises(SqubeDeniedError):
        send_email()
    row = guard._ledger.get_latest()
    assert row["status"] == ActionStatus.DENIED.value


def test_require_approval_timeout(tmp_path: Path) -> None:
    guard = ExecutionGuard(
        policy=_require_approval,
        ledger_path=_ledger_path(tmp_path),
        approval_fn=_approve_timeout,
    )

    @guard.wrap_action(action="send_email")
    def send_email() -> None:
        return 1

    with pytest.raises(SqubeDeniedError):
        send_email()
    row = guard._ledger.get_latest()
    assert row["status"] == ActionStatus.EXPIRED.value


def test_exception_in_wrapped_function(tmp_path: Path) -> None:
    guard = ExecutionGuard(policy=_always_allow, ledger_path=_ledger_path(tmp_path))

    @guard.wrap_action(action="fail")
    def fail() -> None:
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        fail()
    row = guard._ledger.get_latest()
    assert row["status"] == ActionStatus.FAILED.value
    assert row["error_message"] == "boom"


def test_parameters_hashed_not_raw_secrets(tmp_path: Path) -> None:
    guard = ExecutionGuard(policy=_always_allow, ledger_path=_ledger_path(tmp_path))

    @guard.wrap_action(action="x")
    def x(**kwargs) -> None:
        pass

    x(api_key="sk-supersecret12345678901234567890")
    row = guard._ledger.get_latest()
    assert row["parameters_hash"]
    assert "sk-supersecret" not in (row["parameters_summary"] or "")
    assert "[REDACTED]" in (row["parameters_summary"] or "")


def test_fail_closed_on_policy_error(tmp_path: Path) -> None:
    def bad_policy(*_a, **_k):
        raise RuntimeError("policy broke")

    guard = ExecutionGuard(
        policy=bad_policy,
        ledger_path=_ledger_path(tmp_path),
        on_error="fail_closed",
    )
    ran = {"ok": False}

    @guard.wrap_action(action="x")
    def x() -> None:
        ran["ok"] = True

    with pytest.raises(SqubeGuardError):
        x()
    assert not ran["ok"]


def test_fail_open_on_policy_error(tmp_path: Path) -> None:
    def bad_policy(*_a, **_k):
        raise RuntimeError("policy broke")

    guard = ExecutionGuard(
        policy=bad_policy,
        ledger_path=_ledger_path(tmp_path),
        on_error="fail_open",
    )
    ran = {"ok": False}

    @guard.wrap_action(action="x")
    def x() -> None:
        ran["ok"] = True

    x()
    assert ran["ok"]


def test_no_succeeded_without_allow_or_approved(tmp_path: Path) -> None:
    guard = ExecutionGuard(policy=_always_block, ledger_path=_ledger_path(tmp_path))

    @guard.wrap_action(action="x")
    def x() -> None:
        pass

    with pytest.raises(SqubeBlockedError):
        x()
    row = guard._ledger.get_latest()
    assert row["status"] != ActionStatus.SUCCEEDED.value


def test_default_policy_high_risk_requires_approval(tmp_path: Path) -> None:
    guard = ExecutionGuard(
        policy=default_policy,
        ledger_path=_ledger_path(tmp_path),
        approval_fn=_approve_yes,
    )

    @guard.wrap_action(action="db_mutation")
    def mutate() -> str:
        return "ok"

    assert mutate() == "ok"


def test_redaction_email(tmp_path: Path) -> None:
    from sqube_guard.redaction import redact_value

    assert "cu***@example.com" in redact_value({"to": "customer@example.com"})
