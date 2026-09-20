import readline from "node:readline";
import type { ApprovalFn } from "./types.js";

export const promptCliApproval: ApprovalFn = async ({
  executionId,
  agentId,
  action,
  resource,
  summary,
  timeoutSeconds,
}) => {
  const lines = [
    "[sqube] Approval required",
    `  execution_id: ${executionId}`,
    `  agent_id:     ${agentId}`,
    `  action:       ${action}`,
    `  resource:     ${resource ?? ""}`,
    `  summary:      ${summary}`,
    "",
    "Approve? [y/N]",
  ];
  process.stderr.write(lines.join("\n") + "\n");

  return new Promise((resolve) => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stderr });
    let settled = false;

    const timer = setTimeout(() => {
      if (!settled) {
        settled = true;
        rl.close();
        resolve({ approved: false, approvedBy: null, reason: "timeout" });
      }
    }, timeoutSeconds * 1000);

    rl.question("", (answer) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      rl.close();
      const normalized = answer.trim().toLowerCase();
      if (normalized === "y" || normalized === "yes") {
        resolve({ approved: true, approvedBy: "cli_user", reason: null });
      } else {
        resolve({ approved: false, approvedBy: null, reason: "denied_by_user" });
      }
    });
  });
};
