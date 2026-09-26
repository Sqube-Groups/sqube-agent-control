from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqube_agent_guard.control_plane.rbac import Role, parse_role, role_name


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return f"pbkdf2_sha256${salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        algo, salt_hex, digest_hex = stored.split("$", 2)
        if algo != "pbkdf2_sha256":
            return False
        salt = bytes.fromhex(salt_hex)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
        return digest.hex() == digest_hex
    except (ValueError, TypeError):
        return False


_IDENTITY_SCHEMA = """
CREATE TABLE IF NOT EXISTS teams (
  team_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
  user_id TEXT PRIMARY KEY,
  username TEXT NOT NULL UNIQUE,
  email TEXT,
  display_name TEXT,
  password_hash TEXT,
  is_platform_admin INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS team_members (
  team_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  role TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (team_id, user_id)
);

CREATE TABLE IF NOT EXISTS sessions (
  session_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  team_id TEXT NOT NULL,
  csrf_token TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sso_providers (
  provider_id TEXT PRIMARY KEY,
  team_id TEXT,
  protocol TEXT NOT NULL,
  display_name TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 0,
  config_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
  audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
  team_id TEXT,
  actor_user_id TEXT,
  actor_username TEXT,
  action TEXT NOT NULL,
  resource_type TEXT,
  resource_id TEXT,
  details_json TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS policy_active (
  policy_id TEXT PRIMARY KEY,
  active_version TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT
);

CREATE TABLE IF NOT EXISTS policy_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  policy_id TEXT NOT NULL,
  version TEXT NOT NULL,
  bundle_hash TEXT NOT NULL,
  name TEXT,
  created_at TEXT NOT NULL,
  created_by TEXT,
  UNIQUE(policy_id, version)
);
"""


class IdentityStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.executescript(_IDENTITY_SCHEMA)
        self._migrate_agents_policy_version()

    def _migrate_agents_policy_version(self) -> None:
        cols = {
            row[1]
            for row in self._conn.execute("PRAGMA table_info(agents)").fetchall()
        }
        if "policy_version" not in cols:
            self._conn.execute("ALTER TABLE agents ADD COLUMN policy_version TEXT")
            self._conn.commit()

    def setup_required(self) -> bool:
        row = self._conn.execute("SELECT COUNT(*) FROM users").fetchone()
        return not row or int(row[0]) == 0

    def setup_initial_admin(
        self,
        username: str,
        password: str,
        *,
        email: str | None = None,
        team_name: str = "Default team",
    ) -> dict[str, Any]:
        if not self.setup_required():
            raise ValueError("control plane already configured")
        username = username.strip()
        if len(username) < 2:
            raise ValueError("username too short")
        if len(password) < 8:
            raise ValueError("password must be at least 8 characters")
        now = _utc_now()
        team_id = "sq_team_default"
        user_id = f"sq_user_{uuid.uuid4().hex[:12]}"
        self._conn.execute(
            "INSERT INTO teams (team_id, name, created_at) VALUES (?,?,?)",
            (team_id, team_name, now),
        )
        self._conn.execute(
            "INSERT INTO users (user_id, username, email, display_name, password_hash, "
            "is_platform_admin, created_at) VALUES (?,?,?,?,?,?,?)",
            (
                user_id,
                username,
                email,
                username,
                _hash_password(password),
                1,
                now,
            ),
        )
        self._conn.execute(
            "INSERT INTO team_members (team_id, user_id, role, created_at) VALUES (?,?,?,?)",
            (team_id, user_id, role_name(Role.ADMINISTRATOR), now),
        )
        self._conn.commit()
        self.audit(
            team_id,
            user_id,
            username,
            "setup.initial_admin",
            "user",
            user_id,
            {"team_name": team_name},
        )
        return {"user_id": user_id, "username": username, "team_id": team_id}

    def ensure_bootstrap(self) -> None:
        if not self.setup_required():
            return
        admin_password = os.environ.get("SQUBE_ADMIN_PASSWORD")
        if not admin_password:
            return
        self.setup_initial_admin(
            "admin",
            admin_password,
            email=os.environ.get("SQUBE_ADMIN_EMAIL", "admin@local"),
        )

    def auth_required(self) -> bool:
        """True when at least one user exists (anonymous access disabled)."""
        return not self.setup_required()

    def create_team(self, name: str, actor: dict[str, Any]) -> dict[str, Any]:
        team_id = f"sq_team_{uuid.uuid4().hex[:12]}"
        now = _utc_now()
        self._conn.execute(
            "INSERT INTO teams (team_id, name, created_at) VALUES (?,?,?)",
            (team_id, name, now),
        )
        self._conn.commit()
        self.audit(
            actor.get("team_id"),
            actor.get("user_id"),
            actor.get("username"),
            "team.created",
            "team",
            team_id,
            {"name": name},
        )
        return {"team_id": team_id, "name": name, "created_at": now}

    def list_teams(self) -> list[dict[str, Any]]:
        rows = self._conn.execute("SELECT * FROM teams ORDER BY created_at").fetchall()
        return [dict(r) for r in rows]

    def provision_sso_user(
        self, username: str, email: str | None, team_id: str, role: str
    ) -> str:
        now = _utc_now()
        row = self._conn.execute(
            "SELECT user_id FROM users WHERE username=?", (username,)
        ).fetchone()
        if row:
            user_id = row[0]
        else:
            user_id = f"sq_user_{uuid.uuid4().hex[:12]}"
            self._conn.execute(
                "INSERT INTO users (user_id, username, email, display_name, password_hash, "
                "is_platform_admin, created_at) VALUES (?,?,?,?,?,?,?)",
                (user_id, username, email, username, None, 0, now),
            )
        self._conn.execute(
            "INSERT OR REPLACE INTO team_members (team_id, user_id, role, created_at) "
            "VALUES (?,?,?,?)",
            (team_id, user_id, role, now),
        )
        self._conn.commit()
        return user_id

    def add_team_member(
        self, team_id: str, username: str, role: str, password: str | None, actor: dict[str, Any]
    ) -> dict[str, Any]:
        role_enum = parse_role(role)
        now = _utc_now()
        existing = self._conn.execute(
            "SELECT user_id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            user_id = existing[0]
        else:
            if not password:
                raise ValueError("password required for new user")
            user_id = f"sq_user_{uuid.uuid4().hex[:12]}"
            self._conn.execute(
                "INSERT INTO users (user_id, username, email, display_name, password_hash, "
                "is_platform_admin, created_at) VALUES (?,?,?,?,?,?,?)",
                (user_id, username, None, username, _hash_password(password), 0, now),
            )
        self._conn.execute(
            "INSERT OR REPLACE INTO team_members (team_id, user_id, role, created_at) "
            "VALUES (?,?,?,?)",
            (team_id, user_id, role_name(role_enum), now),
        )
        self._conn.commit()
        self.audit(
            team_id,
            actor.get("user_id"),
            actor.get("username"),
            "team.member_added",
            "user",
            user_id,
            {"username": username, "role": role_name(role_enum)},
        )
        return {"team_id": team_id, "user_id": user_id, "username": username, "role": role}

    def list_team_members(self, team_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT u.user_id, u.username, u.display_name, u.email, tm.role, tm.created_at "
            "FROM team_members tm JOIN users u ON u.user_id = tm.user_id "
            "WHERE tm.team_id = ? ORDER BY tm.created_at",
            (team_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def authenticate_local(self, username: str, password: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT user_id, username, password_hash, is_platform_admin FROM users WHERE username=?",
            (username,),
        ).fetchone()
        if not row or not row[2]:
            return None
        if not _verify_password(password, row[2]):
            return None
        return {
            "user_id": row[0],
            "username": row[1],
            "is_platform_admin": bool(row[3]),
        }

    def user_teams(self, user_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT t.team_id, t.name, tm.role FROM team_members tm "
            "JOIN teams t ON t.team_id = tm.team_id WHERE tm.user_id = ?",
            (user_id,),
        ).fetchall()
        return [{"team_id": r[0], "name": r[1], "role": r[2]} for r in rows]

    def create_session(self, user_id: str, team_id: str, hours: int = 24) -> dict[str, str]:
        session_id = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(24)
        now = datetime.now(timezone.utc)
        expires = (now + timedelta(hours=hours)).replace(microsecond=0).isoformat()
        self._conn.execute(
            "INSERT INTO sessions (session_id, user_id, team_id, csrf_token, expires_at, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (session_id, user_id, team_id, csrf, expires, _utc_now()),
        )
        self._conn.commit()
        return {"session_id": session_id, "csrf_token": csrf, "expires_at": expires}

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT s.session_id, s.user_id, s.team_id, s.csrf_token, s.expires_at, "
            "u.username, u.is_platform_admin, tm.role "
            "FROM sessions s "
            "JOIN users u ON u.user_id = s.user_id "
            "LEFT JOIN team_members tm ON tm.team_id = s.team_id AND tm.user_id = s.user_id "
            "WHERE s.session_id = ?",
            (session_id,),
        ).fetchone()
        if not row:
            return None
        if row[4] < _utc_now():
            self.delete_session(session_id)
            return None
        role = row[7] or ("administrator" if row[6] else "viewer")
        return {
            "session_id": row[0],
            "user_id": row[1],
            "team_id": row[2],
            "csrf_token": row[3],
            "username": row[5],
            "role": role,
            "is_platform_admin": bool(row[6]),
        }

    def delete_session(self, session_id: str) -> None:
        self._conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        self._conn.commit()

    def effective_role(self, session: dict[str, Any]) -> Role:
        if session.get("is_platform_admin"):
            return Role.ADMINISTRATOR
        return parse_role(session.get("role", "viewer"))

    def audit(
        self,
        team_id: str | None,
        user_id: str | None,
        username: str | None,
        action: str,
        resource_type: str | None,
        resource_id: str | None,
        details: dict[str, Any] | None,
    ) -> None:
        self._conn.execute(
            "INSERT INTO audit_log (team_id, actor_user_id, actor_username, action, "
            "resource_type, resource_id, details_json, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (
                team_id,
                user_id,
                username,
                action,
                resource_type,
                resource_id,
                json.dumps(details or {}, sort_keys=True),
                _utc_now(),
            ),
        )
        self._conn.commit()

    def list_audit(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM audit_log ORDER BY audit_id DESC LIMIT ?", (limit,)
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["details"] = json.loads(d.pop("details_json") or "{}")
            out.append(d)
        return out

    def upsert_sso_provider(
        self, data: dict[str, Any], actor: dict[str, Any]
    ) -> dict[str, Any]:
        provider_id = data.get("provider_id") or f"sq_sso_{uuid.uuid4().hex[:12]}"
        now = _utc_now()
        config = dict(data.get("config") or {})
        secret = config.pop("client_secret", None)
        if secret:
            config["client_secret_set"] = True
            config["_client_secret"] = secret
        safe_config = {k: v for k, v in config.items() if not k.startswith("_")}
        row = self._conn.execute(
            "SELECT config_json FROM sso_providers WHERE provider_id=?", (provider_id,)
        ).fetchone()
        if row:
            old = json.loads(row[0])
            if not secret and old.get("_client_secret"):
                config["_client_secret"] = old["_client_secret"]
                safe_config["client_secret_set"] = True
        existing_created = self._conn.execute(
            "SELECT created_at FROM sso_providers WHERE provider_id=?", (provider_id,)
        ).fetchone()
        created_at = existing_created[0] if existing_created else now
        stored_config = {**safe_config, **{k: v for k, v in config.items() if k.startswith("_")}}
        self._conn.execute(
            "INSERT OR REPLACE INTO sso_providers "
            "(provider_id, team_id, protocol, display_name, enabled, config_json, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                provider_id,
                data.get("team_id"),
                data["protocol"],
                data["display_name"],
                1 if data.get("enabled") else 0,
                json.dumps(stored_config, sort_keys=True),
                created_at,
                now,
            ),
        )
        self._conn.commit()
        self.audit(
            actor.get("team_id"),
            actor.get("user_id"),
            actor.get("username"),
            "sso.provider_updated",
            "sso_provider",
            provider_id,
            {"protocol": data["protocol"], "display_name": data["display_name"]},
        )
        return self.get_sso_provider_public(provider_id)

    def get_sso_provider(self, provider_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM sso_providers WHERE provider_id=?", (provider_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["config"] = json.loads(d.pop("config_json"))
        d["enabled"] = bool(d["enabled"])
        return d

    def get_sso_provider_public(self, provider_id: str) -> dict[str, Any]:
        p = self.get_sso_provider(provider_id) or {}
        cfg = dict(p.get("config") or {})
        cfg.pop("_client_secret", None)
        return {
            "provider_id": p.get("provider_id"),
            "team_id": p.get("team_id"),
            "protocol": p.get("protocol"),
            "display_name": p.get("display_name"),
            "enabled": p.get("enabled"),
            "config": cfg,
        }

    def list_sso_providers(self, public: bool = False) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT provider_id FROM sso_providers ORDER BY display_name"
        ).fetchall()
        if public:
            return [
                self.get_sso_provider_public(r[0])
                for r in rows
                if (self.get_sso_provider(r[0]) or {}).get("enabled")
            ]
        return [self.get_sso_provider_public(r[0]) for r in rows]

    def policy_bundle_hash(self, bundle: dict[str, Any]) -> str:
        raw = json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(raw).hexdigest()

    def record_policy_version(
        self, policy_id: str, version: str, name: str | None, bundle_hash: str, actor: str | None
    ) -> None:
        now = _utc_now()
        self._conn.execute(
            "INSERT OR REPLACE INTO policy_history "
            "(policy_id, version, bundle_hash, name, created_at, created_by) VALUES (?,?,?,?,?,?)",
            (policy_id, version, bundle_hash, name, now, actor),
        )
        self._conn.commit()

    def set_active_policy(self, policy_id: str, version: str, actor: str | None) -> None:
        now = _utc_now()
        self._conn.execute(
            "INSERT OR REPLACE INTO policy_active (policy_id, active_version, updated_at, updated_by) "
            "VALUES (?,?,?,?)",
            (policy_id, version, now, actor),
        )
        self._conn.commit()

    def get_active_policy_version(self, policy_id: str) -> str | None:
        row = self._conn.execute(
            "SELECT active_version FROM policy_active WHERE policy_id=?", (policy_id,)
        ).fetchone()
        return row[0] if row else None

    def list_policy_history(self, policy_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT policy_id, version, bundle_hash, name, created_at, created_by "
            "FROM policy_history WHERE policy_id=? ORDER BY created_at DESC",
            (policy_id,),
        ).fetchall()
        return [dict(r) for r in rows]
