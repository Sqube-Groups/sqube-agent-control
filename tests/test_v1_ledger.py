from pathlib import Path

from sqube_agent_guard.ledger.events import EventType
from sqube_agent_guard.ledger.store import SQLiteExecutionStore
from sqube_agent_guard.models import ActionRecord, ActionStatus, Decision


def test_event_chain_verifies(tmp_path: Path) -> None:
    store = SQLiteExecutionStore(str(tmp_path / "x.sqlite3"))
    store.append_event("e1", EventType.ACTION_REQUESTED, "agent", {"a": 1}, "t1")
    store.append_event("e1", EventType.POLICY_EVALUATED, "policy", {"d": "ALLOW"}, "t2")
    assert store.verify_chain("e1")


def test_list_executions_by_status(tmp_path: Path) -> None:
    store = SQLiteExecutionStore(str(tmp_path / "y.sqlite3"))
    store.upsert_execution_record(
        ActionRecord(
            execution_id="pending-1",
            created_at="t",
            agent_id="bot",
            action="send_email",
            resource=None,
            parameters_hash="h",
            parameters_summary=None,
            decision=Decision.REQUIRE_APPROVAL.value,
            policy_id="default",
            status=ActionStatus.WAITING_APPROVAL.value,
        )
    )
    store.upsert_execution_record(
        ActionRecord(
            execution_id="done-1",
            created_at="t",
            agent_id="bot",
            action="read",
            resource=None,
            parameters_hash="h",
            parameters_summary=None,
            decision=Decision.ALLOW.value,
            policy_id="default",
            status=ActionStatus.SUCCEEDED.value,
        )
    )
    pending = store.list_executions(status=ActionStatus.WAITING_APPROVAL.value)
    assert len(pending) == 1
    assert pending[0]["execution_id"] == "pending-1"
