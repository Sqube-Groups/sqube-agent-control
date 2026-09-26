const form = document.getElementById("login-form");
const errEl = document.getElementById("login-error");
const ssoSection = document.getElementById("sso-section");
const ssoButtons = document.getElementById("sso-buttons");

async function loadSso() {
  const cfg = await fetch("/api/v1/auth/config").then((r) => r.json());
  if (cfg.setup_required) {
    window.location.href = "/setup";
    return;
  }
  const providers = cfg.sso_providers || [];
  if (!providers.length) return;
  ssoSection.classList.remove("hidden");
  ssoButtons.innerHTML = providers
    .map(
      (p) =>
        `<a class="btn btn-block sso-btn" href="/api/v1/auth/sso/${p.provider_id}/start">${p.display_name}</a>`
    )
    .join("");
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errEl.classList.add("hidden");
  const data = new FormData(form);
  const res = await fetch("/api/v1/auth/login", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      username: data.get("username"),
      password: data.get("password"),
    }),
  });
  if (!res.ok) {
    errEl.textContent = (await res.json()).detail || "Sign in failed";
    errEl.classList.remove("hidden");
    return;
  }
  const body = await res.json();
  sessionStorage.setItem("sqube_csrf", body.csrf_token);
  window.location.href = "/";
});

loadSso().catch(() => {});
