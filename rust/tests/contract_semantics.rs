use serde::Deserialize;
use sqube_agent_guard::state_machine::assert_transition;
use sqube_agent_guard::ActionStatus;
use std::fs;
use std::path::PathBuf;

#[derive(Deserialize)]
struct SemanticsFixture {
    illegal_transitions: Vec<(String, String)>,
    deferred_approval_flow: Vec<String>,
}

fn fixture() -> SemanticsFixture {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../tests/contract/v1_semantics.json");
    let text = fs::read_to_string(&path).expect("read v1_semantics.json");
    serde_json::from_str(&text).expect("parse semantics")
}

fn parse_status(value: &str) -> ActionStatus {
    match value {
        "REQUESTED" => ActionStatus::Requested,
        "EVALUATED" => ActionStatus::Evaluated,
        "BLOCKED" => ActionStatus::Blocked,
        "WAITING_APPROVAL" => ActionStatus::WaitingApproval,
        "APPROVED" => ActionStatus::Approved,
        "DENIED" => ActionStatus::Denied,
        "EXPIRED" => ActionStatus::Expired,
        "EXECUTING" => ActionStatus::Executing,
        "SUCCEEDED" => ActionStatus::Succeeded,
        "FAILED" => ActionStatus::Failed,
        "CANCELLED" => ActionStatus::Cancelled,
        other => panic!("unknown status {}", other),
    }
}

#[test]
fn illegal_transitions_rejected() {
    let data = fixture();
    for (from, to) in data.illegal_transitions {
        assert!(assert_transition(parse_status(&from), parse_status(&to)).is_err());
    }
}

#[test]
fn deferred_flow_is_legal() {
    let data = fixture();
    for pair in data.deferred_approval_flow.windows(2) {
        assert!(assert_transition(parse_status(&pair[0]), parse_status(&pair[1])).is_ok());
    }
}
