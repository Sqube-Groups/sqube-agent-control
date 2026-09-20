"""Example C — file delete with policy."""

import os
import tempfile

from sqube_guard import Decision, ExecutionGuard

ALLOWLIST = {tempfile.gettempdir()}


def policy(action: str, resource: str | None, agent_id: str, **_) -> Decision:
    if action != "file_delete":
        return Decision.ALLOW
    if resource and not any(resource.startswith(p) for p in ALLOWLIST):
        return Decision.BLOCK
    return Decision.REQUIRE_APPROVAL


def with_sqube(path: str) -> None:
    guard = ExecutionGuard(
        policy=policy,
        ledger_path="examples_ledger.sqlite3",
        approval_fn=lambda **_: (True, "demo", None),
    )

    @guard.wrap_action(action="file_delete", resource=lambda p: p)
    def guarded_remove(p: str) -> None:
        if os.path.exists(p):
            os.remove(p)

    guarded_remove(path)


if __name__ == "__main__":
    fd, path = tempfile.mkstemp()
    os.close(fd)
    with_sqube(path)
    print("deleted", path, "exists:", os.path.exists(path))
