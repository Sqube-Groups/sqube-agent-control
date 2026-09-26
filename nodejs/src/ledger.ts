import Database from "better-sqlite3";
import { randomBytes } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { EventType, type ExecutionEvent } from "./events.js";
import { sha256Hex, stableJsonDumps } from "./hashing.js";
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

  close(): void {
    this.db.close();
  }
}
