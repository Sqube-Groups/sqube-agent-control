use crate::error::{SqubeApprovalError, SqubeGuardError};
use crate::models::{ActionRecord, ActionStatus};
use crate::state_machine::assert_transition;
use rusqlite::{params, Connection, OptionalExtension};
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

    pub fn get_execution(&self, execution_id: &str) -> rusqlite::Result<Option<ActionRecord>> {
        self.conn
            .query_row(
                "SELECT execution_id, created_at, agent_id, action, resource, parameters_hash,
                 parameters_summary, decision, policy_id, status, approved_by, approval_reason,
                 result_status, error_message, duration_ms, completed_at
                 FROM execution_records WHERE execution_id = ?1",
                params![execution_id],
                |row| {
                    Ok(ActionRecord {
                        execution_id: row.get(0)?,
                        created_at: row.get(1)?,
                        agent_id: row.get(2)?,
                        action: row.get(3)?,
                        resource: row.get(4)?,
                        parameters_hash: row.get(5)?,
                        parameters_summary: row.get(6)?,
                        decision: row.get(7)?,
                        policy_id: row.get(8)?,
                        status: row.get(9)?,
                        approved_by: row.get(10)?,
                        approval_reason: row.get(11)?,
                        result_status: row.get(12)?,
                        error_message: row.get(13)?,
                        duration_ms: row.get(14)?,
                        completed_at: row.get(15)?,
                    })
                },
            )
            .optional()
    }

    pub fn transition_execution(
        &self,
        execution_id: &str,
        from: ActionStatus,
        to: ActionStatus,
    ) -> rusqlite::Result<()> {
        assert_transition(from, to).map_err(|e| rusqlite::Error::ToSqlConversionFailure(Box::new(e)))?;
        let n = self.conn.execute(
            "UPDATE execution_records SET status = ?1 WHERE execution_id = ?2 AND status = ?3",
            params![to.as_str(), execution_id, from.as_str()],
        )?;
        if n != 1 {
            return Err(rusqlite::Error::ToSqlConversionFailure(Box::new(
                SqubeGuardError(format!("transition failed {} -> {}", from.as_str(), to.as_str())),
            )));
        }
        Ok(())
    }

    pub fn set_completed(&self, execution_id: &str, completed_at: &str) -> rusqlite::Result<()> {
        self.conn.execute(
            "UPDATE execution_records SET completed_at = ?1 WHERE execution_id = ?2",
            params![completed_at, execution_id],
        )?;
        Ok(())
    }

    pub fn set_denied_meta(
        &self,
        execution_id: &str,
        reason: &str,
        completed_at: &str,
    ) -> rusqlite::Result<()> {
        self.conn.execute(
            "UPDATE execution_records SET approval_reason = ?1, completed_at = ?2 WHERE execution_id = ?3",
            params![reason, completed_at, execution_id],
        )?;
        Ok(())
    }

    pub fn set_approved_by(&self, execution_id: &str, approved_by: &str) -> rusqlite::Result<()> {
        self.conn.execute(
            "UPDATE execution_records SET approved_by = ?1 WHERE execution_id = ?2",
            params![approved_by, execution_id],
        )?;
        Ok(())
    }

    pub fn mark_success_meta(
        &self,
        execution_id: &str,
        duration_ms: i64,
        completed_at: &str,
    ) -> rusqlite::Result<()> {
        self.conn.execute(
            "UPDATE execution_records SET result_status = 'SUCCESS', duration_ms = ?1, completed_at = ?2 WHERE execution_id = ?3",
            params![duration_ms, completed_at, execution_id],
        )?;
        Ok(())
    }

    pub fn create_approval_request(
        &self,
        approval_id: &str,
        execution_id: &str,
        parameters_hash: &str,
        requested_at: &str,
        expires_at: Option<&str>,
    ) -> rusqlite::Result<()> {
        self.conn.execute(
            "INSERT INTO approval_requests (approval_id, execution_id, status, parameters_hash, requested_at, expires_at)
             VALUES (?1, ?2, 'PENDING', ?3, ?4, ?5)",
            params![approval_id, execution_id, parameters_hash, requested_at, expires_at],
        )?;
        Ok(())
    }

    pub fn grant_approval(
        &self,
        approval_id: &str,
        decided_by: &str,
        now_iso: &str,
    ) -> rusqlite::Result<String> {
        let tx = self.conn.unchecked_transaction()?;
        let row = tx
            .query_row(
                "SELECT execution_id, status FROM approval_requests WHERE approval_id = ?1",
                params![approval_id],
                |row| Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?)),
            )
            .optional()?;
        let (execution_id, status) = row.ok_or_else(|| {
            rusqlite::Error::ToSqlConversionFailure(Box::new(SqubeApprovalError {
                approval_id: approval_id.to_string(),
                reason: "not found".into(),
            }))
        })?;
        if status != "PENDING" {
            return Err(rusqlite::Error::ToSqlConversionFailure(Box::new(SqubeApprovalError {
                approval_id: approval_id.to_string(),
                reason: format!("status is {}", status),
            })));
        }
        let n = tx.execute(
            "UPDATE approval_requests SET status = 'GRANTED', decided_at = ?1, decided_by = ?2
             WHERE approval_id = ?3 AND status = 'PENDING'",
            params![now_iso, decided_by, approval_id],
        )?;
        if n != 1 {
            return Err(rusqlite::Error::ToSqlConversionFailure(Box::new(SqubeApprovalError {
                approval_id: approval_id.to_string(),
                reason: "concurrent decision lost race".into(),
            })));
        }
        assert_transition(ActionStatus::WaitingApproval, ActionStatus::Approved)
            .map_err(|e| rusqlite::Error::ToSqlConversionFailure(Box::new(e)))?;
        let n2 = tx.execute(
            "UPDATE execution_records SET status = 'APPROVED', approved_by = ?1
             WHERE execution_id = ?2 AND status = 'WAITING_APPROVAL'",
            params![decided_by, execution_id],
        )?;
        if n2 != 1 {
            return Err(rusqlite::Error::ToSqlConversionFailure(Box::new(SqubeGuardError(
                "execution transition failed".into(),
            ))));
        }
        tx.commit()?;
        Ok(execution_id)
    }

    pub fn consume_approval(
        &self,
        approval_id: &str,
        execution_id: &str,
        now_iso: &str,
    ) -> rusqlite::Result<()> {
        let tx = self.conn.unchecked_transaction()?;
        let status: String = tx.query_row(
            "SELECT status FROM approval_requests WHERE approval_id = ?1 AND execution_id = ?2",
            params![approval_id, execution_id],
            |row| row.get(0),
        )?;
        if status == "CONSUMED" {
            return Err(rusqlite::Error::ToSqlConversionFailure(Box::new(SqubeApprovalError {
                approval_id: approval_id.to_string(),
                reason: "already consumed".into(),
            })));
        }
        if status != "GRANTED" {
            return Err(rusqlite::Error::ToSqlConversionFailure(Box::new(SqubeApprovalError {
                approval_id: approval_id.to_string(),
                reason: format!("status is {}", status),
            })));
        }
        let n = tx.execute(
            "UPDATE approval_requests SET status = 'CONSUMED', decided_at = ?1
             WHERE approval_id = ?2 AND status = 'GRANTED'",
            params![now_iso, approval_id],
        )?;
        if n != 1 {
            return Err(rusqlite::Error::ToSqlConversionFailure(Box::new(SqubeApprovalError {
                approval_id: approval_id.to_string(),
                reason: "concurrent consume lost race".into(),
            })));
        }
        assert_transition(ActionStatus::Approved, ActionStatus::Executing)
            .map_err(|e| rusqlite::Error::ToSqlConversionFailure(Box::new(e)))?;
        let n2 = tx.execute(
            "UPDATE execution_records SET status = 'EXECUTING' WHERE execution_id = ?1 AND status = 'APPROVED'",
            params![execution_id],
        )?;
        if n2 != 1 {
            return Err(rusqlite::Error::ToSqlConversionFailure(Box::new(SqubeGuardError(
                "execution transition failed".into(),
            ))));
        }
        tx.commit()?;
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
