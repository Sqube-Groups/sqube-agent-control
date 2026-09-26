import { readFileSync } from "node:fs";
import { Decision, type PolicyFn } from "./types.js";

interface BundleRule {
  name?: string;
  when: Record<string, unknown>;
  decision: string;
}

interface PolicyBundle {
  policy_id?: string;
  rules: BundleRule[];
}

function matchesWhen(
  when: Record<string, unknown>,
  action: string,
  resource: string | null,
  agentId: string,
  environment?: string | null
): boolean {
  if (when.all && Array.isArray(when.all)) {
    return when.all.every((item) =>
      matchesWhen(item as Record<string, unknown>, action, resource, agentId, environment)
    );
  }
  if (when.any && Array.isArray(when.any)) {
    return when.any.some((item) =>
      matchesWhen(item as Record<string, unknown>, action, resource, agentId, environment)
    );
  }
  if (when.agent_id !== undefined && String(when.agent_id) !== agentId) return false;
  if (when.environment !== undefined && String(when.environment) !== (environment ?? "")) {
    return false;
  }
  if (when.action !== undefined && String(when.action) !== action) return false;
  if (when.action_prefix !== undefined && !action.startsWith(String(when.action_prefix))) {
    return false;
  }
  if (when.action_in !== undefined) {
    const set = new Set((when.action_in as unknown[]).map(String));
    if (!set.has(action)) return false;
  }
  if (when.resource !== undefined && resource !== String(when.resource)) return false;
  if (when.resource_prefix !== undefined) {
    const prefix = String(when.resource_prefix).replace(/\/$/, "") + "/";
    if (!(resource ?? "").startsWith(prefix)) return false;
  }
  return Object.keys(when).length > 0;
}

function mergeDecisions(decisions: Decision[]): Decision {
  if (decisions.includes(Decision.BLOCK)) return Decision.BLOCK;
  if (decisions.includes(Decision.REQUIRE_APPROVAL)) return Decision.REQUIRE_APPROVAL;
  return Decision.ALLOW;
}

export function policyFromBundle(data: PolicyBundle): PolicyFn {
  const policyId = data.policy_id ?? "bundle_policy";
  const fn: PolicyFn = (action, resource, agentId, ctx) => {
    const environment =
      ctx && typeof ctx.environment === "string" ? ctx.environment : null;
    const matched: Decision[] = [];
    for (const rule of data.rules) {
      if (matchesWhen(rule.when, action, resource, agentId, environment)) {
        matched.push(rule.decision as Decision);
      }
    }
    return mergeDecisions(matched);
  };
  Object.defineProperty(fn, "name", { value: policyId });
  return fn;
}

export function loadPolicyBundle(path: string): PolicyFn {
  const raw = JSON.parse(readFileSync(path, "utf8")) as PolicyBundle;
  if (!raw.rules?.length) {
    throw new Error("policy bundle must include a non-empty rules list");
  }
  return policyFromBundle(raw);
}
