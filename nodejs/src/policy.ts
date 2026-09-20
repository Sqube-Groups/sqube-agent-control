import { Decision } from "./types.js";

export const HIGH_RISK_ACTIONS = new Set(["db_mutation", "send_email", "file_delete"]);

export function defaultPolicy(
  action: string,
  _resource: string | null,
  _agentId: string
): Decision {
  if (HIGH_RISK_ACTIONS.has(action)) return Decision.REQUIRE_APPROVAL;
  if (action.startsWith("admin_")) return Decision.BLOCK;
  return Decision.ALLOW;
}
