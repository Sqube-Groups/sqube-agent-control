from __future__ import annotations

import sys
import threading
from typing import Callable

ApprovalResult = tuple[bool, str | None, str | None]


def prompt_cli_approval(
    *,
    execution_id: str,
    agent_id: str,
    action: str,
    resource: str | None,
    summary: str,
    timeout_seconds: int,
    input_fn: Callable[[str], str] | None = None,
) -> ApprovalResult:
    """Returns (approved, approved_by, denial_reason)."""
    lines = [
        "[sqube] Approval required",
        f"  execution_id: {execution_id}",
        f"  agent_id:     {agent_id}",
        f"  action:       {action}",
        f"  resource:     {resource or ''}",
        f"  summary:      {summary}",
        "",
        "Approve? [y/N]",
    ]
    message = "\n".join(lines)

    if input_fn is not None:
        answer = input_fn(message + "\n").strip().lower()
        if answer in ("y", "yes"):
            return True, "cli_user", None
        return False, None, "denied_by_user"

    result: list[ApprovalResult] = []

    def _read() -> None:
        try:
            print(message, file=sys.stderr)
            answer = sys.stdin.readline().strip().lower()
            if answer in ("y", "yes"):
                result.append((True, "cli_user", None))
            else:
                result.append((False, None, "denied_by_user"))
        except Exception:
            result.append((False, None, "input_error"))

    thread = threading.Thread(target=_read, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)
    if not result:
        return False, None, "timeout"
    return result[0]
