---
sidebar_position: 6
title: Control plane authentication
---

# Control plane authentication

The Sqube control plane separates **human operators** (browser session) from **machine agents** (API key for event ingest only).

## First-time setup (recommended)

1. Start the control plane: `sqube-agent-guard serve --data-dir /path/to/data`
2. Open **http://127.0.0.1:8080/setup** (or `/` — you are redirected automatically).
3. Choose a **username** (default suggestion: `admin`) and password (minimum 8 characters).
4. You are signed in and land on the dashboard.

**Username is whatever you enter on setup** — it is not fixed unless you use automation below.

Until setup completes, the dashboard and fleet APIs are **not** open anonymously.

### Optional automation (CI / scripts)

```bash
export SQUBE_ADMIN_PASSWORD='choose-a-strong-password'  # creates username admin on first start
export SQUBE_API_KEY='agent-ingest-key'
sqube-agent-guard serve --data-dir /path/to/data
```

Then sign in at `/login` with username **`admin`** and that password.

When any user exists, **anonymous API access is disabled**.

## Roles

| Role | Capabilities |
|------|----------------|
| **viewer** | Read agents, executions, policies, overview, approvals list, SSE |
| **operator** | viewer + grant/deny approvals |
| **administrator** | operator + register agents/policies, webhooks, teams, SSO config |

Approvals still flow through the **local ledger** APIs; the dashboard cannot bypass execution invariants.

## Browser sessions

- HttpOnly session cookie (`sqube_session`, path `/`, SameSite=Lax)
- Set `SQUBE_COOKIE_SECURE=true` behind HTTPS in production
- **Sign out** deletes the session in SQLite and clears the cookie; you must sign in again (that is expected)
- A stolen session id does not work after logout (server-side invalidation)
- CSRF token required on mutating requests (`X-Sqube-CSRF-Token`)
- API keys are **not** stored in `localStorage`

## Machine ingest

`POST /api/v1/events/batch` accepts `X-Sqube-Api-Key` when human auth is enabled. Session cookies are **not** accepted for ingest (prevents browser token leakage patterns).

## Enterprise SSO

Administrators configure providers under **Administration → SSO**:

- **OIDC (supported):** Azure Entra ID, Okta, Google Workspace, Keycloak, Auth0, etc.  
  Set issuer URL, client ID, and client secret. Callback:  
  `https://<your-host>/api/v1/auth/sso/<provider_id>/callback`

- **SAML:** Configuration UI and ACS route are reserved. Use OIDC with Azure Entra where possible, or contact Sqube for SAML enterprise module.

SSO users are provisioned into the configured team with a default role (`viewer` by default).

## Teams

Administrators can create teams and add members with passwords (local accounts) or rely on SSO provisioning.

## Policy lifecycle

- Each policy version is recorded with a **bundle hash** (deterministic identity).
- **Active version** is tracked per `policy_id`.
- Agents show **attached policy** as `policy_id@version` in the dashboard.

## Audit log

Administrative actions (login, agent/policy/webhook/SSO changes, approvals) append to `audit_log` (SQLite). Administrators can read via `GET /api/v1/admin/audit`.

## Current limitations (honest)

- SAML login is not fully implemented in OSS; OIDC is the supported enterprise path.
- SSO JWT signature is not re-validated against JWKS in v1 (token exchange trusts the IdP token endpoint).
- Single-node SQLite sessions (no distributed session store).
- LDAP/SCIM provisioning is not included yet.
- Dev mode (no users) allows open API access for local testing only.

Local agent **execution and policy** remain on the SDK; control plane outage does not block authorized local execution.
