from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib import request as urlrequest
from urllib.error import URLError


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sign_webhook_payload(secret: str, timestamp: str, body: bytes) -> str:
    msg = f"{timestamp}.".encode() + body
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


class WebhookStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS webhook_destinations (
              destination_id TEXT PRIMARY KEY,
              url TEXT NOT NULL,
              secret TEXT NOT NULL,
              event_types TEXT NOT NULL,
              enabled INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS webhook_deliveries (
              delivery_id TEXT PRIMARY KEY,
              destination_id TEXT NOT NULL,
              event_key TEXT NOT NULL,
              status TEXT NOT NULL,
              attempts INTEGER NOT NULL,
              last_error TEXT,
              created_at TEXT NOT NULL,
              UNIQUE(destination_id, event_key)
            );
            """
        )

    def add_destination(
        self, url: str, secret: str, event_types: list[str]
    ) -> dict[str, Any]:
        dest_id = f"sq_wh_{uuid.uuid4().hex[:12]}"
        now = _utc_now()
        self._conn.execute(
            "INSERT INTO webhook_destinations (destination_id, url, secret, event_types, created_at) "
            "VALUES (?,?,?,?,?)",
            (dest_id, url, secret, json.dumps(event_types), now),
        )
        self._conn.commit()
        return {
            "destination_id": dest_id,
            "url": url,
            "event_types": event_types,
            "created_at": now,
        }

    def list_destinations(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT destination_id, url, event_types, enabled, created_at FROM webhook_destinations"
        ).fetchall()
        out = []
        for r in rows:
            out.append(
                {
                    "destination_id": r[0],
                    "url": r[1],
                    "event_types": json.loads(r[2]),
                    "enabled": bool(r[3]),
                    "created_at": r[4],
                }
            )
        return out

    def deliver(self, event_type: str, payload: dict[str, Any]) -> None:
        rows = self._conn.execute(
            "SELECT destination_id, url, secret, event_types FROM webhook_destinations WHERE enabled=1"
        ).fetchall()
        event_key = f"{payload.get('event_id') or payload.get('id')}:{event_type}"
        body = json.dumps(
            {
                "id": payload.get("delivery_id") or f"sq_del_{uuid.uuid4().hex[:12]}",
                "type": event_type,
                "timestamp": _utc_now(),
                "data": payload,
            },
            sort_keys=True,
        ).encode()
        ts = str(int(datetime.now(timezone.utc).timestamp()))
        for dest_id, url, secret, types_json in rows:
            types = json.loads(types_json)
            if event_type not in types:
                continue
            signature = sign_webhook_payload(secret, ts, body)
            delivery_id = f"sq_del_{uuid.uuid4().hex[:12]}"
            if self._already_delivered(dest_id, event_key):
                continue
            ok, err = self._post(url, body, ts, signature)
            self._record_delivery(
                delivery_id, dest_id, event_key, "delivered" if ok else "failed", err
            )

    def _already_delivered(self, destination_id: str, event_key: str) -> bool:
        row = self._conn.execute(
            "SELECT status FROM webhook_deliveries WHERE destination_id=? AND event_key=?",
            (destination_id, event_key),
        ).fetchone()
        return row is not None and row[0] == "delivered"

    def _record_delivery(
        self,
        delivery_id: str,
        destination_id: str,
        event_key: str,
        status: str,
        error: str | None,
    ) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO webhook_deliveries "
            "(delivery_id, destination_id, event_key, status, attempts, last_error, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (delivery_id, destination_id, event_key, status, 1, error, _utc_now()),
        )
        self._conn.commit()

    def _post(self, url: str, body: bytes, ts: str, signature: str) -> tuple[bool, str | None]:
        req = urlrequest.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Sqube-Signature": f"t={ts},v1={signature}",
            },
            method="POST",
        )
        try:
            with urlrequest.urlopen(req, timeout=5) as resp:
                return 200 <= resp.status < 300, None
        except URLError as exc:
            return False, str(exc)
