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

### Steps (only from `main`)

1. Merge your changes into `main` and update your local clone:

   ```bash
   git checkout main
   git pull origin main
   ```

2. Create an annotated tag (example `v0.1.0`):

   ```bash
   git tag v0.1.0
   ```

   Or with a message:

   ```bash
   git tag -a v0.1.0 -m "Release v0.1.0"
   ```

3. Push the tag:

   ```bash
   git push origin v0.1.0
   ```

The workflow runs only for tags matching `v*.*.*`. The tagged commit must be on `main`; tags on other branches are rejected.

To remove a mistaken local tag before pushing: `git tag -d v0.1.0`. To delete a remote tag (use carefully): `git push origin --delete v0.1.0`.
