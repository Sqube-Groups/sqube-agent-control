use crate::models::ActionRecord;
use rusqlite::{params, Connection};
use std::path::Path;

const SCHEMA: &str = "
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
";

pub struct Ledger {
    conn: Connection,
}

impl Ledger {
    pub fn new(path: &str) -> rusqlite::Result<Self> {
        if let Some(parent) = Path::new(path).parent() {
            if !parent.as_os_str().is_empty() {
                std::fs::create_dir_all(parent).map_err(|e| {
                    rusqlite::Error::ToSqlConversionFailure(Box::new(e))
                })?;
            }
        }
        let conn = Connection::open(path)?;
        conn.execute_batch(SCHEMA)?;
        Ok(Self { conn })
    }

    pub fn insert(&self, record: &ActionRecord) -> rusqlite::Result<()> {
        self.conn.execute(
            "INSERT INTO execution_records (
                execution_id, created_at, agent_id, action, resource,
                parameters_hash, parameters_summary, decision, policy_id, status,
                approved_by, approval_reason, result_status, error_message,
                duration_ms, completed_at
            ) VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13,?14,?15,?16)",
            params![
                record.execution_id,
                record.created_at,
                record.agent_id,
                record.action,
                record.resource,
                record.parameters_hash,
                record.parameters_summary,
                record.decision,
                record.policy_id,
                record.status,
                record.approved_by,
                record.approval_reason,
                record.result_status,
                record.error_message,
                record.duration_ms,
                record.completed_at,
            ],
        )?;
        Ok(())
    }

    pub fn set_status(&self, execution_id: &str, status: &str) -> rusqlite::Result<()> {
        self.conn.execute(
            "UPDATE execution_records SET status = ?1 WHERE execution_id = ?2",
            params![status, execution_id],
        )?;
        Ok(())
    }

    pub fn set_decision(&self, execution_id: &str, decision: &str, status: &str) -> rusqlite::Result<()> {
        self.conn.execute(
            "UPDATE execution_records SET decision = ?1, status = ?2 WHERE execution_id = ?3",
            params![decision, status, execution_id],
        )?;
        Ok(())
    }

    pub fn mark_blocked(&self, execution_id: &str, completed_at: &str) -> rusqlite::Result<()> {
        self.conn.execute(
            "UPDATE execution_records SET status = 'BLOCKED', completed_at = ?1 WHERE execution_id = ?2",
            params![completed_at, execution_id],
        )?;
        Ok(())
    }

    pub fn mark_approval_wait(&self, execution_id: &str) -> rusqlite::Result<()> {
        self.set_status(execution_id, "WAITING_APPROVAL")
    }

    pub fn mark_denied(
        &self,
        execution_id: &str,
        status: &str,
        reason: &str,
        completed_at: &str,
    ) -> rusqlite::Result<()> {
        self.conn.execute(
            "UPDATE execution_records SET status = ?1, approval_reason = ?2, completed_at = ?3 WHERE execution_id = ?4",
            params![status, reason, completed_at, execution_id],
        )?;
        Ok(())
    }

    pub fn mark_approved(&self, execution_id: &str, approved_by: &str) -> rusqlite::Result<()> {
        self.conn.execute(
            "UPDATE execution_records SET status = 'APPROVED', approved_by = ?1 WHERE execution_id = ?2",
            params![approved_by, execution_id],
        )?;
        Ok(())
    }

    pub fn mark_executing(&self, execution_id: &str) -> rusqlite::Result<()> {
        self.set_status(execution_id, "EXECUTING")
    }

    pub fn mark_succeeded(
        &self,
        execution_id: &str,
        duration_ms: i64,
        completed_at: &str,
    ) -> rusqlite::Result<()> {
        self.conn.execute(
            "UPDATE execution_records SET status = 'SUCCEEDED', result_status = 'SUCCESS', duration_ms = ?1, completed_at = ?2 WHERE execution_id = ?3",
            params![duration_ms, completed_at, execution_id],
        )?;
        Ok(())
    }

    pub fn mark_failed(
        &self,
        execution_id: &str,
        error_message: &str,
        duration_ms: Option<i64>,
        completed_at: &str,
    ) -> rusqlite::Result<()> {
        self.conn.execute(
            "UPDATE execution_records SET status = 'FAILED', result_status = 'FAILED', error_message = ?1, duration_ms = ?2, completed_at = ?3 WHERE execution_id = ?4",
            params![error_message, duration_ms, completed_at, execution_id],
        )?;
        Ok(())
    }

    pub fn latest_status(&self) -> rusqlite::Result<Option<String>> {
        let mut stmt = self
            .conn
            .prepare("SELECT status FROM execution_records ORDER BY created_at DESC LIMIT 1")?;
        let mut rows = stmt.query([])?;
        if let Some(row) = rows.next()? {
            Ok(Some(row.get(0)?))
        } else {
            Ok(None)
        }
    }
}
