# Versioning Strategy

## Context

This repository is a uv workspace with multiple packages used as an internal shared library across the Rapsodia project. Other repositories consume individual packages from this repo via uv git sources pinned to a git tag. No PyPI publishing is intended.

## Decisions

| Question | Decision |
|---|---|
| Versioning strategy | Lock-step — all packages share the same version number |
| Distribution | Git tags only — no PyPI publishing |
| Version bumping | Manual — developer edits all `pyproject.toml` files |
| Tooling | None — guided by comments in each `pyproject.toml` |
| CI version guard | Runs on push to `main` only (not on dev branches) |
| Tag creation | Automatic by CI after the version guard passes |

## Rationale

**Lock-step over independent versioning:** The packages are tightly coupled (they depend on each other, share a repo, and are conceptually one project). Independent versioning would add complexity with no meaningful benefit.

**Git tags only, no PyPI:** Consuming repositories reference specific packages from this repo directly via uv's git source support (see below). This avoids the need for a PyPI account and the overhead of a publish pipeline.

**No tooling for version bumping:** Tools like `bump-my-version` require software installed on the developer's machine (Python, uv, etc.), which cannot be assumed — especially on Windows hosts. A comment in each `pyproject.toml` is sufficient to guide developers.

**Version guard on `main` only:** Misaligned versions on dev branches are harmless. The gate at merge to `main` is sufficient to prevent them from ever being tagged and consumed.

## Developer Release Workflow

1. Create a release branch: `git checkout -b release/vX.Y.Z`
2. Edit the `version` field in **all** `pyproject.toml` files (root + all `packages/*/pyproject.toml`) to the new value
3. Commit, push, open a PR to `main`
4. PR is reviewed and merged
5. CI verifies all versions match, then creates and pushes tag `vX.Y.Z` on `main`
6. Consuming repositories can now pin to the new tag

## How Consuming Repositories Reference This Repo

**Local development** (sibling clone):
```toml
[tool.uv.sources]
rpsd-transport = { path = "../rpsd-commons/packages/rpsd-transport" }
```

**CI** (pinned to a tag):
```toml
[tool.uv.sources]
rpsd-transport = { git = "https://github.com/Agenzia-TPL/rpsd-commons", tag = "v0.2.0", subdirectory = "packages/rpsd-transport" }
```

## CI Strategy

**No duplicate runs:** CI (`ci.yml`) triggers on `push` to `main` and on `pull_request`. It does NOT trigger on pushes to dev branches, to avoid duplicate runs when a branch with an open PR is pushed.

**Rationale:** With a protected `main` branch (PR-only merges), the `pull_request` event already provides CI feedback for all branch work. Running on every push to every branch would duplicate runs on PRs without adding value.

**Manual runs:** `ci.yml` includes `workflow_dispatch:` so developers can trigger CI on any branch from the GitHub Actions UI ("Run workflow" button) when needed — e.g. after a "save" push before a PR is opened.

## Implementation

- Each `pyproject.toml` has an alignment comment above the `version` field explaining the lock-step requirement
- `.github/workflows/tag-release.yml` triggers on push to `main`, checks version consistency across all packages using Python stdlib (`tomllib`), and creates the git tag if it does not already exist
- `.github/workflows/ci.yml` triggers on `push: main`, `pull_request`, and `workflow_dispatch`
