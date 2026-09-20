# GitHub Pages & releases

Maintainer guide for publishing docs and SDK releases for this repository.

## Enable GitHub Pages (one-time)

The **Deploy docs to GitHub Pages** workflow uses `actions/deploy-pages`. If Pages is not configured for **GitHub Actions**, deploy fails with:

```text
HttpError: Not Found — Ensure GitHub Pages has been enabled
```

Enable it in the GitHub UI:

1. Open the repository on GitHub.
2. **Settings** → **Pages** (left sidebar).
3. Under **Build and deployment**, set **Source** to **GitHub Actions** (not “Deploy from a branch”).
4. Save. No branch or folder selection is required when using GitHub Actions.

Pages cannot be turned on from this repo’s workflows alone; a maintainer must complete the steps above once.

## Docs deploy (automatic)

- **When:** A push to the `main` branch that changes `website/**` or `.github/workflows/docs.yml`, or a manual **workflow_dispatch** run from `main`.
- **What:** CI builds the Docusaurus site and deploys to GitHub Pages.
- **URL:** [https://sqube-groups.github.io/sqube-agent-control/](https://sqube-groups.github.io/sqube-agent-control/)

### Canonical URLs (GitHub About, README, package metadata)

This repo uses a **project** GitHub Pages site (`baseUrl: /sqube-agent-control/` in `website/docusaurus.config.js`). Set the repository **About → Website** field to:

**https://sqube-groups.github.io/sqube-agent-control/**

Docs entry point: **https://sqube-groups.github.io/sqube-agent-control/docs/intro**

`https://sqube-groups.github.io/docs/intro` (no repo prefix) is **wrong** for this deployment—it would only work with an org/user site at the domain root or a custom domain configured differently.

Docs deploy does **not** run for merges to `staging` or other branches—only `main`.

Local preview:

```bash
cd website && npm ci && npm start
```

## Release tags (PyPI & npm)

Releases are published by the **Release** workflow (`.github/workflows/release.yml`) when a semver tag is pushed.

### Prerequisites

Repository secrets (Settings → Secrets and variables → Actions):

| Secret | Used for |
|--------|----------|
| `PYPI_API_TOKEN` | Python package publish to PyPI |
| `NPM_TOKEN` | npm publish (`NODE_AUTH_TOKEN`) |

The Node package is published as the **unscoped** name `sqube-agent-guard` (same as PyPI). Scoped names such as `@sqube/agent-guard` require an npm organization at [npmjs.com](https://www.npmjs.com/org/create) and a token with publish access to that scope; v0.1 does not use a scope.

### Release checklist (new version)

The **Release** workflow publishes whatever versions are in the **tagged commit**—not the tag name alone. If you push `v0.1.1` but `package.json` / `pyproject.toml` still say `0.1.0`, registries get `0.1.0` again (or the job fails as a duplicate). Re-running an old **Release** run for `v0.1.0` does **not** publish a newer build; you need a **new** tag on a commit that already contains the bumps.

1. **Bump every package version** (keep them aligned), then commit:
   - `pyproject.toml` → `version`
   - `src/sqube_agent_guard/__init__.py` → `__version__`
   - `nodejs/package.json` and `nodejs/package-lock.json` → `version`
   - `rust/Cargo.toml` → `version` (for consistency; crates.io publish is still disabled in CI)
2. **Merge to `main`** and update your local clone:

   ```bash
   git checkout main
   git pull origin main
   ```

3. **Create a new semver tag** on that `main` commit—never reuse a tag that already triggered a release:

   ```bash
   git tag -a v0.1.1 -m "Release v0.1.1"
   ```

   Use the next unused version (`v0.1.2`, …) if `v0.1.1` was already pushed.

4. **Push only the new tag** (this starts **Release** once per push):

   ```bash
   git push origin v0.1.1
   ```

   Do **not** rely on “Re-run all jobs” on an old `v0.1.0` workflow to ship fixes or a new npm/PyPI version.

The workflow runs only for tags matching `v*.*.*`. The tagged commit must be on `main`; tags on other branches are rejected.

To remove a mistaken **local** tag before pushing: `git tag -d v0.1.1`. To delete a **remote** tag (use carefully): `git push origin --delete v0.1.1`.

### PyPI setup and troubleshooting

The Release workflow builds from the repo root (`python -m build` → `dist/`) and publishes **`sqube-agent-guard`** (see `pyproject.toml`) using an API token—not PyPI trusted publishing (OIDC).

#### One-time PyPI configuration

1. Sign in at [pypi.org](https://pypi.org/) (create an account if needed).
2. **Account settings** → **API tokens** → **Add API token**.
   - **Scope:** *Entire account* (simplest), or *Project* scoped to `sqube-agent-guard` after the project exists.
   - Copy the token (starts with `pypi-`); PyPI shows it only once.
3. In GitHub: **Settings** → **Secrets and variables** → **Actions** → **New repository secret**
   - Name: **`PYPI_API_TOKEN`** (exact spelling)
   - Value: the `pypi-…` token
4. First successful upload creates the **`sqube-agent-guard`** project on PyPI; you do not need to register the name manually beforehand.

The workflow passes the secret to `pypa/gh-action-pypi-publish` as the **`password`** input (username defaults to `__token__`, which PyPI requires for API tokens).

#### Common Release workflow failures (Python job)

| Symptom / log hint | Likely cause | What to do |
|--------------------|--------------|------------|
| `403 Forbidden` / invalid or missing credentials | Secret missing, wrong name, revoked token, or project-scoped token for a project that does not exist yet | Add or recreate **`PYPI_API_TOKEN`**; use entire-account scope for the first upload |
| `400 … file already exists` / `duplicate` | **`version` in `pyproject.toml`** already on PyPI (common when re-running the same tag or workflow) | Bump `version` in `pyproject.toml`, merge to `main`, tag again—or rely on **`skip-existing: true`** in the workflow to no-op duplicate files on re-runs (does not replace a bad upload) |
| Publish step fails immediately after pulling the Docker image | Often the upload error is in the next log lines; expand the **Publish to PyPI** step | Read the full step output for HTTP status and message |
| Build step fails | Missing `src/` layout, invalid `pyproject.toml`, or `pip install build` / network issues | Run locally: `pip install build && python -m build` and fix reported errors |
| Job never runs | Tag not on `main`, or tag pattern not `v*.*.*` | Tag a commit that is on `main`; use e.g. `v0.1.1` |

Re-running **Release** for the same version without bumping `pyproject.toml` used to fail on PyPI; the workflow sets **`skip-existing: true`** so idempotent re-runs skip wheels/sdists that are already published. npm does not have the same skip behavior—duplicate **`nodejs/package.json`** versions still fail until the version is bumped.
