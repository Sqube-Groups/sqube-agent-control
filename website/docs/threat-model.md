---
sidebar_position: 4
title: Threat model
---

# Threat model (v1.0 summary)

| Threat | Impact | Mitigation (v1) | Residual risk |
|--------|--------|-----------------|---------------|
| Malicious agent bypasses SDK | Uncontrolled side effects | Interceptor/MCP/gateway; code review | Unguarded code paths |
| Stolen credentials in parameters | Secret leakage | Redaction + hash-only storage | Bugs in redaction rules |
| Policy tampering at runtime | Wrong decisions | Policy versioning + hash on record | Compromised host |
| Ledger modification | False audit trail | Hash chain + `ledger verify` | DB file access on host |
| Approval replay | Action runs without intent | Approval bound to execution + params hash | Concurrent races (mitigate in store) |
| Identity spoofing | Wrong actor blamed | Integrate real IdP later | Local SDK trusts caller |
| Delegation abuse | Over-privileged sub-agent | Scope checks on delegation chain | Incomplete scope modeling |

This is a summary for integrators. Maintainer depth lives in internal review notes, not in public runbooks.
