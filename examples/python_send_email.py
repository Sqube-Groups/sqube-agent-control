"""Example B — send email (staged; no real SMTP)."""

from sqube_guard import Decision, ExecutionGuard


def send_email(to: str, subject: str, body: str) -> str:
    return f"sent to {to}: {subject}"


def with_sqube(to: str, subject: str, body: str) -> str:
    guard = ExecutionGuard(
        ledger_path="examples_ledger.sqlite3",
        approval_fn=lambda **_: (True, "demo", None),
    )

    @guard.wrap_action(
        action="send_email",
        resource=lambda t, _s, _b: t,
        agent_id="support-bot",
    )
    def guarded_send(t: str, s: str, b: str) -> str:
        return send_email(t, s, b)

    return guarded_send(to, subject, body)


if __name__ == "__main__":
    print(with_sqube("customer@example.com", "Refund update", "Your refund is processed."))
