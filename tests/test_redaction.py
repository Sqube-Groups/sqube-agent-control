from sqube_guard.redaction import redact_value


def test_long_string_truncated() -> None:
    assert len(redact_value("x" * 300)) == 200
