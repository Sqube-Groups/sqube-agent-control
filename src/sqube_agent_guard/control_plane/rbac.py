from __future__ import annotations

from enum import IntEnum


class Role(IntEnum):
    VIEWER = 1
    OPERATOR = 2
    ADMINISTRATOR = 3


ROLE_NAMES = {
    "viewer": Role.VIEWER,
    "operator": Role.OPERATOR,
    "administrator": Role.ADMINISTRATOR,
}


def parse_role(name: str) -> Role:
    key = name.strip().lower()
    if key not in ROLE_NAMES:
        raise ValueError(f"unknown role: {name}")
    return ROLE_NAMES[key]


def role_name(role: Role) -> str:
    return {Role.VIEWER: "viewer", Role.OPERATOR: "operator", Role.ADMINISTRATOR: "administrator"}[
        role
    ]


# Permission gates (minimum role).
PERM_READ_FLEET = Role.VIEWER
PERM_APPROVE = Role.OPERATOR
PERM_ADMIN = Role.ADMINISTRATOR
PERM_INGEST_EVENTS = None  # machine API key only
