const content = document.getElementById("content");
const buttons = document.querySelectorAll("nav button");
const liveStatus = document.getElementById("live-status");
const themeToggle = document.getElementById("theme-toggle");
const userChip = document.getElementById("user-chip");
const logoutBtn = document.getElementById("logout-btn");
let currentView = "overview";
let eventSource = null;
let currentUser = null;

function getCsrf() {
  return sessionStorage.getItem("sqube_csrf") || "";
}

function getTheme() {
  return document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
}

function setTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("sqube_theme", theme);
  if (themeToggle) {
    themeToggle.setAttribute(
      "aria-label",
      theme === "light" ? "Switch to dark mode" : "Switch to light mode"
    );
  }
}

if (themeToggle) {
  themeToggle.addEventListener("click", () => {
    setTheme(getTheme() === "light" ? "dark" : "light");
  });
  setTheme(getTheme());
}

function setLiveState(state) {
  if (!liveStatus) return;
  liveStatus.className = `live-pill live-${state}`;
  liveStatus.textContent =
    state === "live" ? "Live" : state === "reconnecting" ? "Reconnecting" : "Offline";
}

function badge(text) {
  if (!text) return "";
  const key = String(text).toLowerCase().replace(/\s+/g, "_");
  return `<span class="badge badge-${key}">${text}</span>`;
}

function startEventStream() {
  if (eventSource) eventSource.close();
  eventSource = new EventSource("/api/v1/events/stream", { withCredentials: true });
  setLiveState("live");
  eventSource.onopen = () => setLiveState("live");
  eventSource.onerror = () => {
    setLiveState("reconnecting");
    eventSource.close();
    setTimeout(startEventStream, 3000);
  };
  eventSource.onmessage = () => refreshCurrentView();
  [
    "execution.created",
    "execution.updated",
    "execution.succeeded",
    "execution.failed",
    "execution.blocked",
    "approval.required",
    "approval.granted",
    "approval.denied",
    "agent.registered",
    "policy.changed",
  ].forEach((t) => eventSource.addEventListener(t, () => refreshCurrentView()));
}

async function refreshCurrentView() {
  try {
    await views[currentView]();
  } catch {
    /* ignore */
  }
}

async function api(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (method !== "GET" && method !== "HEAD") {
    headers["X-Sqube-CSRF-Token"] = getCsrf();
  }
  const res = await fetch(path, { ...options, headers, credentials: "include" });
  if (res.status === 401) {
    window.location.href = "/login";
    throw new Error("unauthorized");
  }
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  if (res.status === 204) return null;
  return res.json();
}

function table(headers, rows) {
  const head = headers.map((h) => `<th>${h}</th>`).join("");
  const body = rows
    .map((r) => `<tr>${r.map((c) => `<td>${c ?? ""}</td>`).join("")}</tr>`)
    .join("");
  return `<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

async function renderOverview() {
  const data = await api("/api/v1/overview");
  const c = data.counts;
  content.innerHTML = `
    <h2>Overview</h2>
    <div class="stat-grid">
      <div class="stat-card"><div class="label">Agents</div><div class="value">${data.total_agents}</div></div>
      <div class="stat-card"><div class="label">Executions (sample)</div><div class="value">${data.total_executions_sampled}</div></div>
      <div class="stat-card"><div class="label">Succeeded</div><div class="value">${c.succeeded}</div></div>
      <div class="stat-card"><div class="label">Pending approvals</div><div class="value">${c.pending_approvals}</div></div>
      <div class="stat-card"><div class="label">Blocked</div><div class="value">${c.blocked_decisions}</div></div>
      <div class="stat-card"><div class="label">Failed</div><div class="value">${c.failed}</div></div>
    </div>
    <h3>Recent executions</h3>
    ${table(
      ["Execution", "Agent", "Action", "Decision", "Status", "Created"],
      (data.recent_executions || []).map((e) => [
        `<a href="#" data-exec="${e.execution_id}">${e.execution_id}</a>`,
        e.agent_id,
        e.action,
        badge(e.decision),
        badge(e.status),
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
    <p class="detail-meta">Agent: <strong>${e.agent_id}</strong> · Action: <strong>${e.action}</strong> · Decision: ${badge(e.decision)} · Status: ${badge(e.status)}</p>
    <p class="detail-meta">Correlation: ${e.correlation_id || "—"} · Root: ${e.root_execution_id || "—"}</p>
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
      ["ID", "Name", "Environment", "Status", "Attached policy"],
      agents.map((a) => [
        a.agent_id,
        a.name,
        a.environment,
        a.status,
        a.attached_policy || "—",
      ])
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
        badge(e.decision),
        badge(e.status),
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
  const canOperate = currentUser && ["operator", "administrator"].includes(currentUser.role);
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
        canOperate
          ? `<button type="button" class="btn btn-primary" data-grant="${p.approval_id}">Grant</button>
         <button type="button" class="btn" data-deny="${p.approval_id}">Deny</button>`
          : "—",
      ])
    )}
  `;
  if (!canOperate) return;
  content.querySelectorAll("[data-grant]").forEach((btn) => {
    btn.onclick = async () => {
      await api(`/api/v1/approvals/${btn.dataset.grant}/grant`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      renderApprovals();
    };
  });
  content.querySelectorAll("[data-deny]").forEach((btn) => {
    btn.onclick = async () => {
      await api(`/api/v1/approvals/${btn.dataset.deny}/deny`, {
        method: "POST",
        body: JSON.stringify({ reason: "denied" }),
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
      ["Policy", "Version", "Active", "Name", "Created"],
      policies.map((p) => [
        p.policy_id,
        p.version,
        p.is_active ? "yes" : "",
        p.name,
        p.created_at,
      ])
    )}
  `;
}

async function renderAdmin() {
  const [teams, sso, audit] = await Promise.all([
    api("/api/v1/admin/teams"),
    api("/api/v1/admin/sso/providers"),
    api("/api/v1/admin/audit?limit=50"),
  ]);
  content.innerHTML = `
    <h2>Administration</h2>
    <h3>Teams</h3>
    ${table(["Team ID", "Name", "Created"], teams.map((t) => [t.team_id, t.name, t.created_at]))}
    <h3>SSO providers</h3>
    <p class="detail-meta">Configure OIDC for Azure Entra ID, Okta, Google, Keycloak, Auth0, etc. SAML ACS is reserved for enterprise module.</p>
    ${table(
      ["ID", "Name", "Protocol", "Enabled"],
      sso.map((p) => [p.provider_id, p.display_name, p.protocol, p.enabled ? "yes" : "no"])
    )}
    <form id="sso-form" class="admin-form">
      <h4>Add / update OIDC provider</h4>
      <label>Display name <input name="display_name" placeholder="Azure AD" required /></label>
      <label>Issuer URL <input name="issuer" placeholder="https://login.microsoftonline.com/{tenant}/v2.0" required /></label>
      <label>Client ID <input name="client_id" required /></label>
      <label>Client secret <input name="client_secret" type="password" /></label>
      <label>Default role
        <select name="default_role">
          <option value="viewer">viewer</option>
          <option value="operator">operator</option>
          <option value="administrator">administrator</option>
        </select>
      </label>
      <label><input type="checkbox" name="enabled" checked /> Enabled</label>
      <button type="submit" class="btn btn-primary">Save OIDC provider</button>
    </form>
    <h3>Audit log (recent)</h3>
    ${table(
      ["Time", "Actor", "Action", "Resource"],
      audit.map((a) => [a.created_at, a.actor_username, a.action, `${a.resource_type || ""}:${a.resource_id || ""}`])
    )}
  `;
  document.getElementById("sso-form").onsubmit = async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    await api("/api/v1/admin/sso/providers", {
      method: "POST",
      body: JSON.stringify({
        protocol: "oidc",
        display_name: f.get("display_name"),
        enabled: f.get("enabled") === "on",
        config: {
          issuer: f.get("issuer"),
          client_id: f.get("client_id"),
          client_secret: f.get("client_secret") || undefined,
          default_role: f.get("default_role"),
        },
      }),
    });
    renderAdmin();
  };
}

const views = {
  overview: renderOverview,
  agents: renderAgents,
  executions: renderExecutions,
  approvals: renderApprovals,
  policies: renderPolicies,
  admin: renderAdmin,
};

async function load(view) {
  currentView = view;
  buttons.forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  try {
    await views[view]();
  } catch (err) {
    content.innerHTML = `<p class="error">${err.message}</p>`;
  }
}

async function bootstrap() {
  const cfg = await fetch("/api/v1/auth/config").then((r) => r.json());
  if (cfg.setup_required) {
    window.location.href = "/setup";
    return;
  }
  if (cfg.auth_required) {
    const me = await fetch("/api/v1/auth/me", { credentials: "include" });
    if (!me.ok) {
      window.location.href = "/login";
      return;
    }
    currentUser = await me.json();
    if (currentUser.csrf_token) {
      sessionStorage.setItem("sqube_csrf", currentUser.csrf_token);
    }
    if (userChip) {
      userChip.textContent = `${currentUser.username} (${currentUser.role})`;
    }
    const adminBtn = document.querySelector('[data-view="admin"]');
    if (adminBtn) {
      adminBtn.classList.toggle("hidden", currentUser.role !== "administrator");
    }
  }
  buttons.forEach((b) => b.addEventListener("click", () => load(b.dataset.view)));
  if (logoutBtn) {
    logoutBtn.onclick = async () => {
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
      await fetch("/api/v1/auth/logout", { method: "POST", credentials: "include" });
      sessionStorage.removeItem("sqube_csrf");
      window.location.replace("/login");
    };
  }
  await load("overview");
  startEventStream();
}

bootstrap();
