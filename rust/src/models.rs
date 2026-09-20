use serde::Serialize;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Decision {
    Allow,
    Block,
    RequireApproval,
}

impl Decision {
    pub fn as_str(&self) -> &'static str {
        match self {
            Decision::Allow => "ALLOW",
            Decision::Block => "BLOCK",
            Decision::RequireApproval => "REQUIRE_APPROVAL",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ActionStatus {
    Requested,
    Evaluated,
    Blocked,
    WaitingApproval,
    Approved,
    Denied,
    Expired,
    Executing,
    Succeeded,
    Failed,
    Cancelled,
}

impl ActionStatus {
    pub fn as_str(&self) -> &'static str {
        match self {
            ActionStatus::Requested => "REQUESTED",
            ActionStatus::Evaluated => "EVALUATED",
            ActionStatus::Blocked => "BLOCKED",
            ActionStatus::WaitingApproval => "WAITING_APPROVAL",
            ActionStatus::Approved => "APPROVED",
            ActionStatus::Denied => "DENIED",
            ActionStatus::Expired => "EXPIRED",
            ActionStatus::Executing => "EXECUTING",
            ActionStatus::Succeeded => "SUCCEEDED",
            ActionStatus::Failed => "FAILED",
            ActionStatus::Cancelled => "CANCELLED",
        }
    }
}

#[derive(Debug, Serialize)]
pub struct ActionRecord {
    pub execution_id: String,
    pub created_at: String,
    pub agent_id: String,
    pub action: String,
    pub resource: Option<String>,
    pub parameters_hash: String,
    pub parameters_summary: Option<String>,
    pub decision: String,
    pub policy_id: String,
    pub status: String,
    pub approved_by: Option<String>,
    pub approval_reason: Option<String>,
    pub result_status: Option<String>,
    pub error_message: Option<String>,
    pub duration_ms: Option<i64>,
    pub completed_at: Option<String>,
}
