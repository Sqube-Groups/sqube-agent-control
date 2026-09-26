use serde::Deserialize;
use sqube_agent_guard::default_policy;
use sqube_agent_guard::Decision;
use std::fs;
use std::path::PathBuf;

#[derive(Deserialize)]
struct Fixture {
    name: String,
    context: FixtureContext,
    expected_decision: String,
}

#[derive(Deserialize)]
struct FixtureContext {
    agent_id: String,
    action: String,
    resource: Option<String>,
}

fn fixtures_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../tests/contract/fixtures")
}

#[test]
fn shared_json_contract_fixtures() {
    let dir = fixtures_dir();
    for entry in fs::read_dir(&dir).expect("fixtures dir") {
        let entry = entry.expect("read dir entry");
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("json") {
            continue;
        }
        let text = fs::read_to_string(&path).expect("read fixture");
        let data: Fixture = serde_json::from_str(&text).expect("parse fixture");
        let decision = default_policy(
            &data.context.action,
            data.context.resource.as_deref(),
            &data.context.agent_id,
        );
        let expected = match data.expected_decision.as_str() {
            "ALLOW" => Decision::Allow,
            "BLOCK" => Decision::Block,
            "REQUIRE_APPROVAL" => Decision::RequireApproval,
            other => panic!("unknown decision {} in {}", other, data.name),
        };
        assert_eq!(decision, expected, "fixture {}", data.name);
    }
}
