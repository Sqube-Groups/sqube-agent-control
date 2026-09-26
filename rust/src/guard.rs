//! v0.1-compatible `wrap_action` API implemented on top of v1 [`ExecutionEngine`].

use crate::execution_engine::{ExecutionContext, ExecutionEngine};
use crate::policy::default_policy;
use uuid::Uuid;

pub type PolicyFn = crate::execution_engine::PolicyFn;
pub type ApprovalCallback = crate::execution_engine::ApprovalCallback;

#[derive(Clone, Copy, PartialEq, Eq)]
pub enum OnErrorMode {
    FailOpen,
    FailClosed,
}

/// Convenience wrapper around [`ExecutionEngine`] for synchronous v1 execution semantics.
pub struct ExecutionGuard {
    engine: ExecutionEngine,
}

pub struct WrapOptions {
    pub action: String,
    pub resource: Option<String>,
    pub agent_id: String,
}

impl ExecutionGuard {
    pub fn new(policy: PolicyFn) -> Self {
        Self {
            engine: ExecutionEngine::new(policy),
        }
    }

    pub fn with_default_policy() -> Self {
        Self::new(default_policy)
    }

    pub fn with_ledger_path(mut self, path: &str) -> Self {
        self.engine = self.engine.with_ledger_path(path);
        self
    }

    /// Retained for API compatibility; policy errors are not recoverable on the `PolicyFn` path.
    pub fn with_on_error(self, _mode: OnErrorMode) -> Self {
        self
    }

    pub fn with_approval_fn(mut self, f: ApprovalCallback) -> Self {
        self.engine = self.engine.with_approval_fn(f);
        self
    }

    pub fn with_policy_id(mut self, id: &str) -> Self {
        self.engine = self.engine.with_policy_id(id);
        self
    }

    pub fn wrap_action<F, R>(
        &self,
        opts: WrapOptions,
        f: F,
        _parameters_summary: &str,
        parameters_payload: &str,
    ) -> Result<R, Box<dyn std::error::Error + Send + Sync>>
    where
        F: FnOnce() -> Result<R, Box<dyn std::error::Error + Send + Sync>>,
    {
        let execution_id = format!(
            "sq_exec_{}",
            Uuid::new_v4().simple().to_string()[..16].to_string()
        );
        let ctx = ExecutionContext {
            execution_id,
            agent_id: opts.agent_id,
            action: opts.action,
            resource: opts.resource,
            parameters_payload: parameters_payload.to_string(),
        };
        self.engine.run_controlled(&ctx, f)
    }

    pub fn latest_status(&self) -> rusqlite::Result<Option<String>> {
        self.engine.latest_status()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::approval::ApprovalRequest;
    use crate::error::{SqubeBlockedError, SqubeDeniedError};
    use crate::models::{ActionStatus, Decision};
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
