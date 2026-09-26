use crate::error::SqubeGuardError;
use crate::models::ActionStatus;

fn terminal(status: ActionStatus) -> bool {
    matches!(
        status,
        ActionStatus::Blocked
            | ActionStatus::Denied
            | ActionStatus::Expired
            | ActionStatus::Succeeded
            | ActionStatus::Failed
            | ActionStatus::Cancelled
    )
}

fn allowed(from: ActionStatus, to: ActionStatus) -> bool {
    matches!(
        (from, to),
        (ActionStatus::Requested, ActionStatus::Evaluated)
            | (ActionStatus::Requested, ActionStatus::Blocked)
            | (ActionStatus::Requested, ActionStatus::Failed)
            | (ActionStatus::Evaluated, ActionStatus::Blocked)
            | (ActionStatus::Evaluated, ActionStatus::WaitingApproval)
            | (ActionStatus::Evaluated, ActionStatus::Executing)
            | (ActionStatus::Evaluated, ActionStatus::Failed)
            | (ActionStatus::WaitingApproval, ActionStatus::Approved)
            | (ActionStatus::WaitingApproval, ActionStatus::Denied)
            | (ActionStatus::WaitingApproval, ActionStatus::Expired)
            | (ActionStatus::WaitingApproval, ActionStatus::Cancelled)
            | (ActionStatus::Approved, ActionStatus::Executing)
            | (ActionStatus::Approved, ActionStatus::Cancelled)
            | (ActionStatus::Executing, ActionStatus::Succeeded)
            | (ActionStatus::Executing, ActionStatus::Failed)
            | (ActionStatus::Executing, ActionStatus::Cancelled)
    )
}

pub fn assert_transition(from: ActionStatus, to: ActionStatus) -> Result<(), SqubeGuardError> {
    if from == to {
        return Err(SqubeGuardError(format!(
            "Invalid execution transition {} -> {}",
            from.as_str(),
            to.as_str()
        )));
    }
    if terminal(from) {
        return Err(SqubeGuardError(format!(
            "Invalid execution transition {} -> {}",
            from.as_str(),
            to.as_str()
        )));
    }
    if !allowed(from, to) {
        return Err(SqubeGuardError(format!(
            "Invalid execution transition {} -> {}",
            from.as_str(),
            to.as_str()
        )));
    }
    Ok(())
}
