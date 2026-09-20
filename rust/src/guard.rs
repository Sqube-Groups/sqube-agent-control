use crate::approval::{prompt_cli_approval, ApprovalRequest};
use crate::error::{SqubeBlockedError, SqubeDeniedError, SqubeGuardError};
use crate::ledger::Ledger;
use crate::models::{ActionRecord, ActionStatus, Decision};
use crate::policy::default_policy;
use crate::redaction::redact_value;
use chrono::Utc;
use sha2::{Digest, Sha256};
use std::time::Instant;
use uuid::Uuid;

pub type PolicyFn = fn(&str, Option<&str>, &str) -> Decision;
pub type ApprovalCallback =
    fn(&ApprovalRequest) -> (bool, Option<String>, Option<String>);

#[derive(Clone, Copy, PartialEq, Eq)]
pub enum OnErrorMode {
    FailOpen,
    FailClosed,
}

pub struct WrapOptions {
    pub action: String,
    pub resource: Option<String>,
    pub agent_id: String,
}

pub struct ExecutionGuard {
    policy: PolicyFn,
    ledger_path: String,
    approval_timeout_seconds: u64,
    on_error: OnErrorMode,
    approval_fn: ApprovalCallback,
    policy_id: String,
}

impl ExecutionGuard {
    pub fn new(policy: PolicyFn) -> Self {
        Self {
            policy,
            ledger_path: "sqube_ledger.sqlite3".to_string(),
            approval_timeout_seconds: 300,
            on_error: OnErrorMode::FailClosed,
            approval_fn: prompt_cli_approval,
            policy_id: "policy".to_string(),
        }
    }

    pub fn with_default_policy() -> Self {
        Self::new(default_policy)
    }

    pub fn with_ledger_path(mut self, path: &str) -> Self {
        self.ledger_path = path.to_string();
        self
    }

    pub fn with_on_error(mut self, mode: OnErrorMode) -> Self {
        self.on_error = mode;
        self
    }

    pub fn with_approval_fn(mut self, f: ApprovalCallback) -> Self {
        self.approval_fn = f;
        self
    }

    pub fn with_policy_id(mut self, id: &str) -> Self {
        self.policy_id = id.to_string();
        self
    }

    pub fn wrap_action<F, R>(
        &self,
        opts: WrapOptions,
        f: F,
        parameters_summary: &str,
        parameters_payload: &str,
    ) -> Result<R, Box<dyn std::error::Error + Send + Sync>>
    where
        F: FnOnce() -> Result<R, Box<dyn std::error::Error + Send + Sync>>,
    {
        let ledger = Ledger::new(&self.ledger_path)?;
        let execution_id = format!("sq_exec_{}", Uuid::new_v4().simple().to_string()[..16].to_string());
        let created_at = Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
        let parameters_hash = hex_hash(parameters_payload);
        let summary = redact_value(parameters_summary);

        let record = ActionRecord {
            execution_id: execution_id.clone(),
            created_at: created_at.clone(),
            agent_id: opts.agent_id.clone(),
            action: opts.action.clone(),
            resource: opts.resource.clone(),
            parameters_hash,
            parameters_summary: Some(summary.clone()),
            decision: Decision::Allow.as_str().to_string(),
            policy_id: self.policy_id.clone(),
            status: ActionStatus::Requested.as_str().to_string(),
            approved_by: None,
            approval_reason: None,
            result_status: None,
            error_message: None,
            duration_ms: None,
            completed_at: None,
        };
        ledger.insert(&record)?;

        let decision = (self.policy)(&opts.action, opts.resource.as_deref(), &opts.agent_id);

        ledger.set_decision(
            &execution_id,
            decision.as_str(),
            ActionStatus::Evaluated.as_str(),
        )?;

        match decision {
            Decision::Block => {
                ledger.mark_blocked(&execution_id, &Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true))?;
                return Err(Box::new(SqubeBlockedError {
                    execution_id,
                    action: opts.action,
                }));
            }
            Decision::RequireApproval => {
                ledger.mark_approval_wait(&execution_id)?;
                let (approved, approved_by, reason) = (self.approval_fn)(&ApprovalRequest {
                    execution_id: execution_id.clone(),
                    agent_id: opts.agent_id.clone(),
                    action: opts.action.clone(),
                    resource: opts.resource.clone(),
                    summary: summary.clone(),
                });
                if !approved {
                    let status = if reason.as_deref() == Some("timeout") {
                        ActionStatus::Expired.as_str()
                    } else {
                        ActionStatus::Denied.as_str()
                    };
                    ledger.mark_denied(
                        &execution_id,
                        status,
                        reason.as_deref().unwrap_or("denied"),
                        &Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true),
                    )?;
                    return Err(Box::new(SqubeDeniedError {
                        execution_id,
                        reason: reason.unwrap_or_else(|| "denied".to_string()),
                    }));
                }
                ledger.mark_approved(
                    &execution_id,
                    approved_by.as_deref().unwrap_or("cli_user"),
                )?;
            }
            Decision::Allow => {}
        }

        self.run_fn(&ledger, &execution_id, f)
    }

    fn handle_policy_error<F, R>(
        &self,
        ledger: &Ledger,
        execution_id: &str,
        f: F,
        message: &str,
    ) -> Result<R, Box<dyn std::error::Error + Send + Sync>>
    where
        F: FnOnce() -> Result<R, Box<dyn std::error::Error + Send + Sync>>,
    {
        ledger.mark_failed(
            execution_id,
            &format!("policy_error: {message}"),
            None,
            &Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true),
        )?;
        if self.on_error == OnErrorMode::FailOpen {
            return self.run_fn(ledger, execution_id, f);
        }
        Err(Box::new(SqubeGuardError(format!(
            "Policy evaluation failed: {message}"
        ))))
    }

    fn run_fn<F, R>(
        &self,
        ledger: &Ledger,
        execution_id: &str,
        f: F,
    ) -> Result<R, Box<dyn std::error::Error + Send + Sync>>
    where
        F: FnOnce() -> Result<R, Box<dyn std::error::Error + Send + Sync>>,
    {
        ledger.mark_executing(execution_id)?;
        let start = Instant::now();
        match f() {
            Ok(value) => {
                let duration_ms = start.elapsed().as_millis() as i64;
                ledger.mark_succeeded(
                    execution_id,
                    duration_ms,
                    &Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true),
                )?;
                Ok(value)
            }
            Err(err) => {
                let duration_ms = start.elapsed().as_millis() as i64;
                ledger.mark_failed(
                    execution_id,
                    &err.to_string(),
                    Some(duration_ms),
                    &Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true),
                )?;
                Err(err)
            }
        }
    }

    pub fn latest_status(&self) -> rusqlite::Result<Option<String>> {
        Ledger::new(&self.ledger_path)?.latest_status()
    }
}

fn hex_hash(payload: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(payload.as_bytes());
    format!("{:x}", hasher.finalize())
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    fn always_allow(_a: &str, _r: Option<&str>, _id: &str) -> Decision {
        Decision::Allow
    }

    fn always_block(_a: &str, _r: Option<&str>, _id: &str) -> Decision {
        Decision::Block
    }

    fn require_approval(_a: &str, _r: Option<&str>, _id: &str) -> Decision {
        Decision::RequireApproval
    }

    fn approve_yes(_: &ApprovalRequest) -> (bool, Option<String>, Option<String>) {
        (true, Some("test".into()), None)
    }

    fn approve_no(_: &ApprovalRequest) -> (bool, Option<String>, Option<String>) {
        (false, None, Some("denied_by_user".into()))
    }

    fn approve_timeout(_: &ApprovalRequest) -> (bool, Option<String>, Option<String>) {
        (false, None, Some("timeout".into()))
    }

    #[test]
    fn allow_executes() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("l.db");
        let guard = ExecutionGuard::new(always_allow).with_ledger_path(path.to_str().unwrap());
        let result = guard.wrap_action(
            WrapOptions {
                action: "read".into(),
                resource: None,
                agent_id: "default".into(),
            },
            || Ok(42),
            "",
            "{}",
        );
        assert_eq!(result.unwrap(), 42);
        assert_eq!(
            guard.latest_status().unwrap(),
            Some(ActionStatus::Succeeded.as_str().to_string())
        );
    }

    #[test]
    fn block_does_not_run() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("l.db");
        let guard = ExecutionGuard::new(always_block).with_ledger_path(path.to_str().unwrap());
        let err = guard
            .wrap_action(
                WrapOptions {
                    action: "x".into(),
                    resource: None,
                    agent_id: "default".into(),
                },
                || Ok(()),
                "",
                "{}",
            )
            .unwrap_err();
        assert!(err.is::<SqubeBlockedError>());
    }

    #[test]
    fn approval_flows() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("l.db");
        let guard = ExecutionGuard::new(require_approval)
            .with_ledger_path(path.to_str().unwrap())
            .with_approval_fn(approve_yes);
        assert!(guard
            .wrap_action(
                WrapOptions {
                    action: "send_email".into(),
                    resource: None,
                    agent_id: "default".into(),
                },
                || Ok(1),
                "",
                "{}",
            )
            .is_ok());

        let guard = ExecutionGuard::new(require_approval)
            .with_ledger_path(path.to_str().unwrap())
            .with_approval_fn(approve_no);
        assert!(guard
            .wrap_action(
                WrapOptions {
                    action: "send_email".into(),
                    resource: None,
                    agent_id: "default".into(),
                },
                || Ok(1),
                "",
                "{}",
            )
            .unwrap_err()
            .is::<SqubeDeniedError>());
    }
}
