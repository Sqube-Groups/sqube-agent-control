use std::fs;
use std::path::PathBuf;

#[test]
fn otel_semantics_contract_metrics_present() {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../tests/contract/otel_semantics.json");
    let raw = fs::read_to_string(path).expect("otel_semantics.json");
    let data: serde_json::Value = serde_json::from_str(&raw).expect("json");
    let metrics = data["metrics"].as_array().expect("metrics array");
    let names: Vec<&str> = metrics.iter().map(|v| v.as_str().unwrap()).collect();
    assert!(names.contains(&"sqube.executions.total"));
    assert!(names.contains(&"sqube.execution.duration"));
    assert_eq!(data["root_span_name"].as_str(), Some("sqube.execution"));
}
