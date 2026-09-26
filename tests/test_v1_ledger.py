from pathlib import Path

from sqube_agent_guard.ledger.events import EventType
from sqube_agent_guard.ledger.store import SQLiteExecutionStore


def test_event_chain_verifies(tmp_path: Path) -> None:
    store = SQLiteExecutionStore(str(tmp_path / "x.sqlite3"))
    store.append_event("e1", EventType.ACTION_REQUESTED, "agent", {"a": 1}, "t1")
    store.append_event("e1", EventType.POLICY_EVALUATED, "policy", {"d": "ALLOW"}, "t2")
    assert store.verify_chain("e1")
