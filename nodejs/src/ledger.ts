import Database from "better-sqlite3";
import fs from "node:fs";
import path from "node:path";
import type { ActionRecord } from "./types.js";

const SCHEMA = `
CREATE TABLE IF NOT EXISTS execution_records (
  execution_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  action TEXT NOT NULL,
  resource TEXT,
  parameters_hash TEXT NOT NULL,
  parameters_summary TEXT,
  decision TEXT NOT NULL,
  policy_id TEXT NOT NULL,
  status TEXT NOT NULL,
  approved_by TEXT,
  approval_reason TEXT,
  result_status TEXT,
  error_message TEXT,
  duration_ms INTEGER,
  completed_at TEXT
);
`;

export class Ledger {
  private db: Database.Database;

  constructor(ledgerPath = "sqube_ledger.sqlite3") {
    const dir = path.dirname(ledgerPath);
    if (dir && dir !== ".") fs.mkdirSync(dir, { recursive: true });
    this.db = new Database(ledgerPath);
    this.db.exec(SCHEMA);
  }

  insert(record: ActionRecord): void {
    const stmt = this.db.prepare(`
      INSERT INTO execution_records (
        execution_id, created_at, agent_id, action, resource,
        parameters_hash, parameters_summary, decision, policy_id, status,
        approved_by, approval_reason, result_status, error_message,
        duration_ms, completed_at
      ) VALUES (
        @execution_id, @created_at, @agent_id, @action, @resource,
        @parameters_hash, @parameters_summary, @decision, @policy_id, @status,
        @approved_by, @approval_reason, @result_status, @error_message,
        @duration_ms, @completed_at
      )
    `);
    stmt.run({
      ...record,
      approved_by: record.approved_by ?? null,
      approval_reason: record.approval_reason ?? null,
      result_status: record.result_status ?? null,
      error_message: record.error_message ?? null,
      duration_ms: record.duration_ms ?? null,
      completed_at: record.completed_at ?? null,
    });
  }

  updateStatus(executionId: string, fields: Partial<ActionRecord>): void {
    const keys = Object.keys(fields);
    if (keys.length === 0) return;
    const sets = keys.map((k) => `${k} = @${k}`).join(", ");
    const stmt = this.db.prepare(
      `UPDATE execution_records SET ${sets} WHERE execution_id = @execution_id`
    );
    stmt.run({ ...fields, execution_id: executionId });
  }

  getLatest(): ActionRecord | undefined {
    const row = this.db
      .prepare("SELECT * FROM execution_records ORDER BY created_at DESC LIMIT 1")
      .get() as ActionRecord | undefined;
    return row;
  }

  close(): void {
    this.db.close();
  }
}
