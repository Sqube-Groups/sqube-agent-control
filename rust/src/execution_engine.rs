use crate::approval::{prompt_cli_approval, ApprovalRequest};
use crate::error::{
    SqubeApprovalPendingError, SqubeBlockedError, SqubeDeniedError, SqubeGuardError,
};
use crate::ledger::Ledger;
use crate::models::{ActionRecord, ActionStatus, Decision};
use chrono::{Duration, Utc};
use sha2::{Digest, Sha256};
use uuid::Uuid;

pub type PolicyFn = fn(&str, Option<&str>, &str) -> Decision;
pub type ApprovalCallback = fn(&ApprovalRequest) -> (bool, Option<String>, Option<String>);

#[derive(Clone, Copy, PartialEq, Eq)]
pub enum ApprovalMode {
    Sync,
    Deferred,
}

pub struct ExecutionContext {
    pub execution_id: String,
    pub agent_id: String,
    pub action: String,
    pub resource: Option<String>,
    pub parameters_payload: String,
}

pub struct ExecutionEngine {
    ledger_path: String,
    policy: PolicyFn,
    approval_mode: ApprovalMode,
    approval_timeout_seconds: u64,
    approval_fn: ApprovalCallback,
    policy_id: String,
}

impl ExecutionEngine {
    pub fn new(policy: PolicyFn) -> Self {
        Self {
            ledger_path: "sqube_ledger.sqlite3".to_string(),
            policy,
            approval_mode: ApprovalMode::Sync,
            approval_timeout_seconds: 300,
            approval_fn: prompt_cli_approval,
            policy_id: "policy".to_string(),
        }
    }

    pub fn with_ledger_path(mut self, path: &str) -> Self {
        self.ledger_path = path.to_string();
        self
    }

    pub fn with_approval_mode(mut self, mode: ApprovalMode) -> Self {
        self.approval_mode = mode;
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

    pub fn latest_status(&self) -> rusqlite::Result<Option<String>> {
        Ledger::new(&self.ledger_path)?.latest_status()
    }

    pub fn run_controlled<F, R>(
        &self,
        ctx: &ExecutionContext,
        f: F,
    ) -> Result<R, Box<dyn std::error::Error + Send + Sync>>
    where
        F: FnOnce() -> Result<R, Box<dyn std::error::Error + Send + Sync>>,
    {
        let ledger = Ledger::new(&self.ledger_path)?;
        let created_at = Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
        let parameters_hash = hex_hash(&ctx.parameters_payload);

        ledger.insert(&ActionRecord {
            execution_id: ctx.execution_id.clone(),
            created_at: created_at.clone(),
            agent_id: ctx.agent_id.clone(),
            action: ctx.action.clone(),
            resource: ctx.resource.clone(),
            parameters_hash,
            parameters_summary: None,
            decision: Decision::Allow.as_str().to_string(),
            policy_id: self.policy_id.clone(),
            status: ActionStatus::Requested.as_str().to_string(),
            approved_by: None,
            approval_reason: None,
            result_status: None,
            error_message: None,
            duration_ms: None,
            completed_at: None,
        })?;

        ledger.transition_execution(
            &ctx.execution_id,
            ActionStatus::Requested,
            ActionStatus::Evaluated,
        )?;

        let decision = (self.policy)(&ctx.action, ctx.resource.as_deref(), &ctx.agent_id);
        ledger.set_decision(&ctx.execution_id, decision.as_str(), ActionStatus::Evaluated.as_str())?;

        match decision {
            Decision::Block => {
                ledger.transition_execution(
                    &ctx.execution_id,
                    ActionStatus::Evaluated,
                    ActionStatus::Blocked,
                )?;
                ledger.set_completed(&ctx.execution_id, &Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true))?;
                return Err(Box::new(SqubeBlockedError {
                    execution_id: ctx.execution_id.clone(),
                    action: ctx.action.clone(),
                }));
            }
            Decision::RequireApproval => {
                if self.approval_mode == ApprovalMode::Deferred {
                    return self.deferred_approval(&ledger, ctx);
                }
                return self.sync_approval(&ledger, ctx, f);
            }
            Decision::Allow => {}
        }

        self.begin_execute(&ledger, ctx, f, ActionStatus::Evaluated)
    }

    pub fn resume_after_approval<F, R>(
        &self,
        ctx: &ExecutionContext,
        approval_id: &str,
        f: F,
    ) -> Result<R, Box<dyn std::error::Error + Send + Sync>>
    where
        F: FnOnce() -> Result<R, Box<dyn std::error::Error + Send + Sync>>,
    {
        let ledger = Ledger::new(&self.ledger_path)?;
        let row = ledger
            .get_execution(&ctx.execution_id)?
            .ok_or_else(|| SqubeGuardError("unknown execution".into()))?;
        if row.status == ActionStatus::WaitingApproval.as_str() {
            return Err(Box::new(SqubeApprovalPendingError {
                execution_id: ctx.execution_id.clone(),
                approval_id: approval_id.to_string(),
            }));
        }
        let hash = hex_hash(&ctx.parameters_payload);
        if hash != row.parameters_hash {
            return Err(Box::new(SqubeGuardError(
                "parameters changed after authorization".into(),
            )));
        }
        let now = Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
        ledger.consume_approval(approval_id, &ctx.execution_id, &now)?;
        self.run_fn_body(&ledger, &ctx.execution_id, f)
    }

    fn deferred_approval<R>(
        &self,
        ledger: &Ledger,
        ctx: &ExecutionContext,
    ) -> Result<R, Box<dyn std::error::Error + Send + Sync>> {
        ledger.transition_execution(
            &ctx.execution_id,
            ActionStatus::Evaluated,
            ActionStatus::WaitingApproval,
        )?;
        let approval_id = format!("sq_apr_{}", Uuid::new_v4().simple().to_string()[..12].to_string());
        let now = Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
        let expires = (Utc::now() + Duration::seconds(self.approval_timeout_seconds as i64))
            .to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
        ledger.create_approval_request(
            &approval_id,
            &ctx.execution_id,
            &hex_hash(&ctx.parameters_payload),
            &now,
            Some(&expires),
        )?;
        Err(Box::new(SqubeApprovalPendingError {
            execution_id: ctx.execution_id.clone(),
            approval_id,
        }))
    }

    fn sync_approval<F, R>(
        &self,
        ledger: &Ledger,
        ctx: &ExecutionContext,
        f: F,
    ) -> Result<R, Box<dyn std::error::Error + Send + Sync>>
    where
        F: FnOnce() -> Result<R, Box<dyn std::error::Error + Send + Sync>>,
    {
        ledger.transition_execution(
            &ctx.execution_id,
            ActionStatus::Evaluated,
            ActionStatus::WaitingApproval,
        )?;
        let summary = ctx.parameters_payload.clone();
        let (approved, approved_by, reason) = (self.approval_fn)(&ApprovalRequest {
            execution_id: ctx.execution_id.clone(),
            agent_id: ctx.agent_id.clone(),
            action: ctx.action.clone(),
            resource: ctx.resource.clone(),
            summary,
        });
        if !approved {
            let status = if reason.as_deref() == Some("timeout") {
                ActionStatus::Expired
            } else {
                ActionStatus::Denied
            };
            ledger.transition_execution(
                &ctx.execution_id,
                ActionStatus::WaitingApproval,
                status,
            )?;
            ledger.set_denied_meta(
                &ctx.execution_id,
                reason.as_deref().unwrap_or("denied"),
                &Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true),
            )?;
            return Err(Box::new(SqubeDeniedError {
                execution_id: ctx.execution_id.clone(),
                reason: reason.unwrap_or_else(|| "denied".to_string()),
            }));
        }
        ledger.transition_execution(
            &ctx.execution_id,
            ActionStatus::WaitingApproval,
            ActionStatus::Approved,
        )?;
        ledger.set_approved_by(
            &ctx.execution_id,
            approved_by.as_deref().unwrap_or("cli_user"),
        )?;
        self.begin_execute(ledger, ctx, f, ActionStatus::Approved)
    }

    fn begin_execute<F, R>(
        &self,
        ledger: &Ledger,
        ctx: &ExecutionContext,
        f: F,
        from: ActionStatus,
    ) -> Result<R, Box<dyn std::error::Error + Send + Sync>>
    where
        F: FnOnce() -> Result<R, Box<dyn std::error::Error + Send + Sync>>,
    {
        ledger.transition_execution(&ctx.execution_id, from, ActionStatus::Executing)?;
        self.run_fn_body(ledger, &ctx.execution_id, f)
    }

    fn run_fn_body<F, R>(
        &self,
        ledger: &Ledger,
        execution_id: &str,
        f: F,
    ) -> Result<R, Box<dyn std::error::Error + Send + Sync>>
    where
        F: FnOnce() -> Result<R, Box<dyn std::error::Error + Send + Sync>>,
    {
        let start = std::time::Instant::now();
        match f() {
            Ok(value) => {
                let duration_ms = start.elapsed().as_millis() as i64;
                let completed = Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
                ledger.transition_execution(execution_id, ActionStatus::Executing, ActionStatus::Succeeded)?;
                ledger.mark_success_meta(execution_id, duration_ms, &completed)?;
                Ok(value)
            }
            Err(err) => {
                let duration_ms = start.elapsed().as_millis() as i64;
                let completed = Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
                ledger.transition_execution(execution_id, ActionStatus::Executing, ActionStatus::Failed)?;
                ledger.mark_failed(
                    execution_id,
                    &err.to_string(),
                    Some(duration_ms),
                    &completed,
                )?;
                Err(err)
            }
        }
    }
}

fn hex_hash(payload: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(payload.as_bytes());
    format!("{:x}", hasher.finalize())
}
