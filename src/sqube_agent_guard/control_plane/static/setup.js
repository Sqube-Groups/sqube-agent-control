const form = document.getElementById("setup-form");
const errEl = document.getElementById("setup-error");

async function checkAlreadyConfigured() {
  const cfg = await fetch("/api/v1/auth/config").then((r) => r.json());
  if (!cfg.setup_required) {
    window.location.href = "/login";
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errEl.classList.add("hidden");
  const data = new FormData(form);
  if (data.get("password") !== data.get("password2")) {
    errEl.textContent = "Passwords do not match";
    errEl.classList.remove("hidden");
    return;
  }
  const res = await fetch("/api/v1/auth/setup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      username: data.get("username"),
      password: data.get("password"),
      email: data.get("email") || null,
      team_name: data.get("team_name") || "Default team",
    }),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    errEl.textContent = body.detail || "Setup failed";
    errEl.classList.remove("hidden");
    return;
  }
  sessionStorage.setItem("sqube_csrf", body.csrf_token);
  window.location.href = "/";
});

checkAlreadyConfigured().catch(() => {});
