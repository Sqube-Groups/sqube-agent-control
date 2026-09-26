from __future__ import annotations

import hashlib
import json
from typing import Any


def stable_json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def sha256_hex(value: str | bytes) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def hash_payload(payload: Any) -> str:
    return sha256_hex(stable_json_dumps(payload))
