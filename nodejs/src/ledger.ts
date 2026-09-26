import Database from "better-sqlite3";
import { randomBytes } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { EventType, type ExecutionEvent } from "./events.js";
import { sha256Hex, stableJsonDumps } from "./hashing.js";
import { assertTransition } from "./stateMachine.js";
import { SqubeApprovalError } from "./errors.js";
import { ActionStatus, type ActionRecord } from "./types.js";

export interface ApprovalRecord {
  approval_id: string;
  execution_id: string;
  status: string;
  parameters_hash: string;
  requested_at: string;
  expires_at: string | null;
  decided_at: string | null;
  decided_by: string | null;
  decision_reason: string | null;
}

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

CREATE TABLE IF NOT EXISTS execution_events (
  event_id TEXT PRIMARY KEY,
  execution_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  actor TEXT NOT NULL,
  payload TEXT NOT NULL,
  previous_event_hash TEXT,
  event_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approval_requests (
  approval_id TEXT PRIMARY KEY,
  execution_id TEXT NOT NULL,
  status TEXT NOT NULL,
  parameters_hash TEXT NOT NULL,
  requested_at TEXT NOT NULL,
  expires_at TEXT,
  decided_at TEXT,
  decided_by TEXT,
  decision_reason TEXT
);
`;

function newEventId(): string {
  return `sq_evt_${randomBytes(8).toString("hex")}`;
}

export class Ledger {
  private db: Database.Database;

  constructor(ledgerPath = "sqube_ledger.sqlite3") {
    const dir = path.dirname(ledgerPath);
    if (dir && dir !== ".") fs.mkdirSync(dir, { recursive: true });
    this.db = new Database(ledgerPath);
    this.db.exec(SCHEMA);
    this.db.pragma("journal_mode = WAL");
    this.migrate();
  }

  private migrate(): void {
    const cols = this.db.prepare("PRAGMA table_info(execution_records)").all() as Array<{
      name: string;
    }>;
    const names = new Set(cols.map((c) => c.name));
    if (!names.has("correlation_id")) {
      this.db.exec("ALTER TABLE execution_records ADD COLUMN correlation_id TEXT");
    }
    if (!names.has("root_execution_id")) {
      this.db.exec("ALTER TABLE execution_records ADD COLUMN root_execution_id TEXT");
    }
  }

  getExecution(executionId: string): ActionRecord | undefined {
    return this.db
      .prepare("SELECT * FROM execution_records WHERE execution_id = ?")
      .get(executionId) as ActionRecord | undefined;
  }

  transitionExecution(
    executionId: string,
    fromStatus: string,
    toStatus: string,
    fields: Partial<ActionRecord> = {}
  ): void {
    assertTransition(fromStatus, toStatus, executionId);
    const keys = Object.keys(fields);
    const sets = ["status = @to_status", ...keys.map((k) => `${k} = @${k}`)];
    const stmt = this.db.prepare(
      `UPDATE execution_records SET ${sets.join(", ")} WHERE execution_id = @execution_id AND status = @from_status`
    );
    const result = stmt.run({
      ...fields,
      to_status: toStatus,
      execution_id: executionId,
      from_status: fromStatus,
    });
    if (result.changes !== 1) {
      const row = this.getExecution(executionId);
      throw new Error(
        `Invalid execution transition ${row?.status ?? "MISSING"} -> ${toStatus}`
      );
    }
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

  appendEvent(
    executionId: string,
    eventType: EventType,
    actor: string,
    payload: Record<string, unknown>,
    timestamp: string
  ): ExecutionEvent {
    const prev = this.db
      .prepare(
        "SELECT event_hash FROM execution_events WHERE execution_id = ? " +
          "ORDER BY timestamp DESC LIMIT 1"
      )
      .get(executionId) as { event_hash: string } | undefined;
    const previousHash = prev?.event_hash ?? null;
    const eventId = newEventId();
    const body = stableJsonDumps({
      event_id: eventId,
      execution_id: executionId,
      event_type: eventType,
      timestamp,
      actor,
      payload,
      previous_event_hash: previousHash,
    });
    const eventHash = sha256Hex(body);
    this.db
      .prepare(
        `INSERT INTO execution_events (
          event_id, execution_id, event_type, timestamp, actor, payload,
          previous_event_hash, event_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
      )
      .run(
        eventId,
        executionId,
        eventType,
        timestamp,
        actor,
        stableJsonDumps(payload),
        previousHash,
        eventHash
      );
    return {
      event_id: eventId,
      execution_id: executionId,
      event_type: eventType,
      timestamp,
      actor,
      payload,
      previous_event_hash: previousHash,
      event_hash: eventHash,
    };
  }

  getEvents(executionId: string): ExecutionEvent[] {
    const rows = this.db
      .prepare(
        "SELECT * FROM execution_events WHERE execution_id = ? ORDER BY timestamp ASC"
      )
      .all(executionId) as Array<{
      event_id: string;
      execution_id: string;
      event_type: string;
      timestamp: string;
      actor: string;
      payload: string;
      previous_event_hash: string | null;
      event_hash: string;
    }>;
    return rows.map((row) => ({
      event_id: row.event_id,
      execution_id: row.execution_id,
      event_type: row.event_type as EventType,
      timestamp: row.timestamp,
      actor: row.actor,
      payload: JSON.parse(row.payload) as Record<string, unknown>,
      previous_event_hash: row.previous_event_hash,
      event_hash: row.event_hash,
    }));
  }

  verifyChain(executionId?: string): boolean {
    if (executionId) {
      const events = this.getEvents(executionId);
      for (const event of events) {
        const body = stableJsonDumps({
          event_id: event.event_id,
          execution_id: event.execution_id,
          event_type: event.event_type,
          timestamp: event.timestamp,
          actor: event.actor,
          payload: event.payload,
          previous_event_hash: event.previous_event_hash,
        });
        if (sha256Hex(body) !== event.event_hash) return false;
      }
      return true;
    }
    const ids = this.db
      .prepare("SELECT DISTINCT execution_id FROM execution_events")
      .all() as Array<{ execution_id: string }>;
    if (ids.length === 0) return true;
    return ids.every((row) => this.verifyChain(row.execution_id));
  }

  listExecutions(limit = 50, status?: string): ActionRecord[] {
    if (status) {
      return this.db
        .prepare(
          "SELECT * FROM execution_records WHERE status = ? ORDER BY created_at DESC LIMIT ?"
        )
        .all(status, limit) as ActionRecord[];
    }
    return this.db
      .prepare("SELECT * FROM execution_records ORDER BY created_at DESC LIMIT ?")
      .all(limit) as ActionRecord[];
  }

  getLatest(): ActionRecord | undefined {
    const row = this.db
      .prepare("SELECT * FROM execution_records ORDER BY created_at DESC LIMIT 1")
      .get() as ActionRecord | undefined;
    return row;
  }

  createApprovalRequest(
    approvalId: string,
    executionId: string,
    parametersHash: string,
    requestedAt: string,
    expiresAt: string | null
  ): void {
    this.db
      .prepare(
        `INSERT INTO approval_requests (
          approval_id, execution_id, status, parameters_hash, requested_at, expires_at
        ) VALUES (?, ?, 'PENDING', ?, ?, ?)`
      )
      .run(approvalId, executionId, parametersHash, requestedAt, expiresAt);
  }

  getApproval(approvalId: string): ApprovalRecord | undefined {
    return this.db
      .prepare("SELECT * FROM approval_requests WHERE approval_id = ?")
      .get(approvalId) as ApprovalRecord | undefined;
  }

  grantApproval(approvalId: string, decidedBy: string, nowIso: string): string {
    const grant = this.db.transaction(() => {
      const row = this.getApproval(approvalId);
      if (!row) throw new SqubeApprovalError(approvalId, "not found");
      if (row.status !== "PENDING") {
        throw new SqubeApprovalError(approvalId, `status is ${row.status}`);
      }
      if (row.expires_at && row.expires_at < nowIso) {
        throw new SqubeApprovalError(approvalId, "expired");
      }
      const cur = this.db
        .prepare(
          "UPDATE approval_requests SET status = 'GRANTED', decided_at = ?, decided_by = ? WHERE approval_id = ? AND status = 'PENDING'"
        )
        .run(nowIso, decidedBy, approvalId);
      if (cur.changes !== 1) {
        throw new SqubeApprovalError(approvalId, "concurrent decision lost race");
      }
      this.transitionExecution(
        row.execution_id,
        ActionStatus.WAITING_APPROVAL,
        ActionStatus.APPROVED,
        { approved_by: decidedBy }
      );
      return row.execution_id;
    });
    return grant();
  }

  consumeApproval(approvalId: string, executionId: string, nowIso: string): void {
    const consume = this.db.transaction(() => {
      const row = this.getApproval(approvalId);
      if (!row || row.execution_id !== executionId) {
        throw new SqubeApprovalError(approvalId, "not found for execution");
      }
      if (row.status === "CONSUMED") {
        throw new SqubeApprovalError(approvalId, "already consumed");
      }
      if (row.status !== "GRANTED") {
        throw new SqubeApprovalError(approvalId, `status is ${row.status}`);
      }
      const cur = this.db
        .prepare(
          "UPDATE approval_requests SET status = 'CONSUMED', decided_at = ? WHERE approval_id = ? AND status = 'GRANTED'"
        )
        .run(nowIso, approvalId);
      if (cur.changes !== 1) {
        throw new SqubeApprovalError(approvalId, "concurrent consume lost race");
      }
      this.transitionExecution(
        executionId,
        ActionStatus.APPROVED,
        ActionStatus.EXECUTING
      );
    });
    consume();
  }

  close(): void {
    this.db.close();
  }
}
