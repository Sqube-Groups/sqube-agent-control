---
sidebar_position: 99
title: Documentation site
---

# Documentation site (GitHub Pages)

This site is built with **Docusaurus** from the `website/` directory in the repository.

## Public URL

https://sqube-groups.github.io/sqube-agent-control/docs/intro

## When it updates

The workflow [Deploy docs to GitHub Pages](https://github.com/Sqube-Groups/sqube-agent-control/blob/main/.github/workflows/docs.yml) runs on:

- Pushes to **`main`** or **`staging`** that change `website/**` or the workflow file
- Manual **workflow_dispatch** from the Actions tab

Merges that only touch application code under `src/` do **not** redeploy docs until `website/` changes land on `main` or `staging`.

## Build locally

```bash
cd website
npm ci
npm run build
npm run serve   # preview at http://localhost:3000
```

## Edit content

Markdown lives in `website/docs/`. Sidebar order: `website/sidebars.js`.
