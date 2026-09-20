use crate::models::Decision;
use std::collections::HashSet;
use std::sync::LazyLock;

pub static HIGH_RISK_ACTIONS: LazyLock<HashSet<&'static str>> = LazyLock::new(|| {
    HashSet::from(["db_mutation", "send_email", "file_delete"])
});

pub fn default_policy(action: &str, _resource: Option<&str>, _agent_id: &str) -> Decision {
    if HIGH_RISK_ACTIONS.contains(action) {
        return Decision::RequireApproval;
    }
    if action.starts_with("admin_") {
        return Decision::Block;
    }
    Decision::Allow
}
