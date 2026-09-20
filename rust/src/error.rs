use thiserror::Error;

#[derive(Debug, Error)]
#[error("Action '{action}' blocked (execution_id={execution_id})")]
pub struct SqubeBlockedError {
    pub execution_id: String,
    pub action: String,
}

#[derive(Debug, Error)]
#[error("Action denied: {reason} (execution_id={execution_id})")]
pub struct SqubeDeniedError {
    pub execution_id: String,
    pub reason: String,
}

#[derive(Debug, Error)]
#[error("{0}")]
pub struct SqubeGuardError(pub String);
