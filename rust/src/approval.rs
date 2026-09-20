use std::io::{self, Write};

pub struct ApprovalRequest {
    pub execution_id: String,
    pub agent_id: String,
    pub action: String,
    pub resource: Option<String>,
    pub summary: String,
}

pub fn prompt_cli_approval(req: &ApprovalRequest) -> (bool, Option<String>, Option<String>) {
    eprintln!("[sqube] Approval required");
    eprintln!("  execution_id: {}", req.execution_id);
    eprintln!("  agent_id:     {}", req.agent_id);
    eprintln!("  action:       {}", req.action);
    eprintln!("  resource:     {}", req.resource.as_deref().unwrap_or(""));
    eprintln!("  summary:      {}", req.summary);
    eprintln!();
    eprint!("Approve? [y/N] ");
    io::stderr().flush().ok();
    let mut line = String::new();
    if io::stdin().read_line(&mut line).is_err() {
        return (false, None, Some("input_error".to_string()));
    }
    let answer = line.trim().to_ascii_lowercase();
    if answer == "y" || answer == "yes" {
        (true, Some("cli_user".to_string()), None)
    } else {
        (false, None, Some("denied_by_user".to_string()))
    }
}
