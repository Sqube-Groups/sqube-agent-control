const content = document.getElementById("content");
const buttons = document.querySelectorAll("nav button");

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const key = localStorage.getItem("sqube_api_key");
  if (key) headers["X-Sqube-Api-Key"] = key;
  const res = await fetch(path, { ...options, headers });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

function table(headers, rows) {
  const head = headers.map((h) => `<th>${h}</th>`).join("");
  const body = rows
    .map((r) => `<tr>${r.map((c) => `<td>${c ?? ""}</td>`).join("")}</tr>`)
    .join("");
  return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

async function renderOverview() {
  const data = await api("/api/v1/overview");
  const c = data.counts;
  content.innerHTML = `
    <h2>Overview</h2>
    <p>Agents: <strong>${data.total_agents}</strong> · Executions (sample): <strong>${data.total_executions_sampled}</strong></p>
    <p>Allowed: ${c.allowed_decisions} · Blocked: ${c.blocked_decisions} · Approval required: ${c.approval_required_decisions}</p>
    <p>Succeeded: ${c.succeeded} · Failed: ${c.failed} · Cancelled: ${c.cancelled} · Pending approvals: ${c.pending_approvals}</p>
    <h3>Recent executions</h3>
    ${table(
      ["Execution", "Agent", "Action", "Decision", "Status", "Created"],
      (data.recent_executions || []).map((e) => [
        `<a href="#" data-exec="${e.execution_id}">${e.execution_id}</a>`,
        e.agent_id,
        e.action,
        e.decision,
        e.status,
        e.created_at,
      ])
    )}
  `;
  content.querySelectorAll("[data-exec]").forEach((el) => {
    el.addEventListener("click", (ev) => {
      ev.preventDefault();
      showExecution(el.getAttribute("data-exec"));
    });
  });
}

async function showExecution(id) {
  const detail = await api(`/api/v1/executions/${id}`);
  const e = detail.execution;
  content.innerHTML = `
    <h2>Execution ${e.execution_id}</h2>
    <p>Agent: ${e.agent_id} · Action: ${e.action} · Decision: ${e.decision} · Status: ${e.status}</p>
    <p>Correlation: ${e.correlation_id || "-"} · Root: ${e.root_execution_id || "-"}</p>
    <h3>Events</h3>
    ${table(
      ["Time", "Type", "Actor"],
      detail.events.map((ev) => [ev.timestamp, ev.event_type, ev.actor])
    )}
    <p><a href="#" id="back">← Back</a></p>
  `;
  document.getElementById("back").onclick = (ev) => {
    ev.preventDefault();
    renderExecutions();
  };
}

async function renderAgents() {
  const agents = await api("/api/v1/agents");
  content.innerHTML = `
    <h2>Agents</h2>
    ${table(
      ["ID", "Name", "Environment", "Status", "Policy"],
      agents.map((a) => [a.agent_id, a.name, a.environment, a.status, a.policy_id])
    )}
  `;
}

async function renderExecutions() {
  const rows = await api("/api/v1/executions?limit=100");
  content.innerHTML = `
    <h2>Executions</h2>
    ${table(
      ["Execution", "Agent", "Action", "Resource", "Decision", "Status", "Created"],
      rows.map((e) => [
        `<a href="#" data-exec="${e.execution_id}">${e.execution_id}</a>`,
        e.agent_id,
        e.action,
        e.resource,
        e.decision,
        e.status,
        e.created_at,
      ])
    )}
  `;
  content.querySelectorAll("[data-exec]").forEach((el) => {
    el.addEventListener("click", (ev) => {
      ev.preventDefault();
      showExecution(el.getAttribute("data-exec"));
    });
  });
}

async function renderApprovals() {
  const pending = await api("/api/v1/approvals/pending");
  content.innerHTML = `
    <h2>Pending approvals</h2>
    ${table(
      ["Approval", "Execution", "Agent", "Action", "Expires", "Actions"],
      pending.map((p) => [
        p.approval_id,
        p.execution_id,
        p.agent_id,
        p.action,
        p.expires_at,
        `<button data-grant="${p.approval_id}">Grant</button>
         <button data-deny="${p.approval_id}">Deny</button>`,
      ])
    )}
  `;
  content.querySelectorAll("[data-grant]").forEach((btn) => {
    btn.onclick = async () => {
      await api(`/api/v1/approvals/${btn.dataset.grant}/grant`, {
        method: "POST",
        body: JSON.stringify({ decided_by: "dashboard" }),
      });
      renderApprovals();
    };
  });
  content.querySelectorAll("[data-deny]").forEach((btn) => {
    btn.onclick = async () => {
      await api(`/api/v1/approvals/${btn.dataset.deny}/deny`, {
        method: "POST",
        body: JSON.stringify({ decided_by: "dashboard", reason: "denied" }),
      });
      renderApprovals();
    };
  });
}

async function renderPolicies() {
  const policies = await api("/api/v1/policies");
  content.innerHTML = `
    <h2>Policies</h2>
    ${table(
      ["Policy", "Version", "Name", "Created"],
      policies.map((p) => [p.policy_id, p.version, p.name, p.created_at])
    )}
  `;
}

const views = {
  overview: renderOverview,
  agents: renderAgents,
  executions: renderExecutions,
  approvals: renderApprovals,
  policies: renderPolicies,
};

async function load(view) {
  buttons.forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  try {
    await views[view]();
  } catch (err) {
    content.innerHTML = `<p class="error">${err.message}</p>`;
  }
}

buttons.forEach((b) => b.addEventListener("click", () => load(b.dataset.view)));
load("overview");
