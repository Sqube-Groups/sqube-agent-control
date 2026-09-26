use serde::Deserialize;
use sqube_agent_guard::default_policy;
use sqube_agent_guard::{ApprovalMode, ExecutionContext, ExecutionEngine, SqubeApprovalPendingError};
use std::fs;
use std::path::PathBuf;
use tempfile::tempdir;

#[derive(Deserialize)]
struct Fixture {
    context: FixtureContext,
    grant_at: String,
    expected_after_pending_status: String,
    expected_after_grant_status: String,
    expected_final_status: String,
    resume_result: String,
}

#[derive(Deserialize)]
struct FixtureContext {
    agent_id: String,
    action: String,
    resource: Option<String>,
    parameters: serde_json::Value,
}

fn fixture() -> Fixture {
    let path =
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../tests/contract/deferred_approval.json");
    let text = fs::read_to_string(&path).expect("read deferred_approval.json");
    serde_json::from_str(&text).expect("parse fixture")
}

fn require_email(action: &str, _r: Option<&str>, _id: &str) -> sqube_agent_guard::Decision {
    if action == "send_email" {
        sqube_agent_guard::Decision::RequireApproval
    } else {
        default_policy(action, None, "bot")
    }
}

#[test]
fn deferred_approval_contract_scenario() {
    let data = fixture();
    let dir = tempdir().unwrap();
    let path = dir.path().join("ledger.db");
    let engine = ExecutionEngine::new(require_email)
        .with_ledger_path(path.to_str().unwrap())
        .with_approval_mode(ApprovalMode::Deferred);

    let payload = serde_json::to_string(&data.context.parameters).unwrap();
    let ctx = ExecutionContext {
        execution_id: "sq_exec_contract_def".into(),
        agent_id: data.context.agent_id.clone(),
        action: data.context.action.clone(),
        resource: data.context.resource.clone(),
        parameters_payload: payload,
    };

    let err = engine
        .run_controlled(&ctx, || Ok(data.resume_result.clone()))
        .unwrap_err();
    assert!(err.is::<SqubeApprovalPendingError>());
    let pending = err.downcast_ref::<SqubeApprovalPendingError>().unwrap();
    let approval_id = pending.approval_id.clone();

    let ledger = sqube_agent_guard::ledger::Ledger::new(path.to_str().unwrap()).unwrap();
    let row = ledger.get_execution(&ctx.execution_id).unwrap().unwrap();
    assert_eq!(row.status, data.expected_after_pending_status);

    ledger
        .grant_approval(&approval_id, "human", &data.grant_at)
        .unwrap();
    let row = ledger.get_execution(&ctx.execution_id).unwrap().unwrap();
    assert_eq!(row.status, data.expected_after_grant_status);

    let out = engine
        .resume_after_approval(&ctx, &approval_id, || Ok(data.resume_result.clone()))
        .unwrap();
    assert_eq!(out, data.resume_result);
    let row = ledger.get_execution(&ctx.execution_id).unwrap().unwrap();
    assert_eq!(row.status, data.expected_final_status);
}
