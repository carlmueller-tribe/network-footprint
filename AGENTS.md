# AGENTS.md

This file provides guidance for agents when working with code in this repository.

## Development Commands

### Setup

```bash
uv sync --extra dev      # install all dependencies
pre-commit install       # install git hooks
gt auth                  # authenticate Graphite CLI (one-time)
mise install             # install pinned tool versions (Python 3.11, trivy, ripgrep)
```

### Core checks

```bash
mise run check                                      # lint + typecheck + tests + trivy (one command)
```

Or individually:

```bash
uv run ruff check footprint/ tests/                 # lint
uv run ruff format footprint/ tests/                # format
uv run mypy footprint/                              # strict type check — 0 errors required
uv run pytest                                       # full test suite
mise run trivy:scan                                 # HIGH/CRITICAL vuln scan against uv.lock
pre-commit run --all-files                          # all pre-commit hooks
```

---

## Development Flow

For **any task that edits the codebase**, follow this exact flow. No exceptions.

### 1. Create a branch and worktree

```bash
# On main — Graphite creates and tracks the branch
gt sync
gt create -m "feat(scope): short description"

# Add an isolated worktree for it
git worktree add .worktrees/<short-name> <branch-name>

# All remaining work happens inside the worktree
cd .worktrees/<short-name>
```

`.worktrees/` is gitignored. Use `gt log` to confirm the branch name.

### 2. Implement, then validate

```bash
# run all checks — repeat until all pass
mise run check                                     # lint + typecheck + tests + trivy
uv run ruff check footprint/ tests/ --fix          # auto-fix ruff violations if needed
pre-commit run --all-files                         # full hook suite
```

**STOP on any failure** — fix the root cause before proceeding. Never use `--no-verify`.

### 3. Commit and submit

```bash
# commit inside the worktree
gt modify -am "feat(scope): description"

# open/update PR on GitHub
gt submit
```

Never push directly to `main`. Never `git push` — always `gt submit`.

---

## Stacking strategy

Each implementation task maps to a **branch in a stack**. Graphite stacks branches on top of each other, each targeting its parent as the base.

```
main
 └── feat/phase5-extractor         ← EndpointExtractor + EndpointRecord
      └── feat/phase5-graph        ← NetworkGraph + classification
           └── feat/phase5-report  ← AuditReport (JSON + markdown)
                └── feat/phase5-cli ← footprint audit command
```

**Default rule**: one branch per task (one module or concern).

**Exception**: if a change is naturally atomic (≤ 3 files, one concern), use a single branch.

Submit the full stack at once:

```bash
gt submit --stack
```

Graphite creates one PR per branch, each with a focused diff.

---

## Full implementation workflow

Every feature or bugfix follows the 9-phase process:

> `docs/engineering/user-story-implementation-workflow.md`

**Phase order is fixed: 0 → 0.5 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8**

| Phase | Name | Gate |
|-------|------|------|
| 0 | Validation & Setup | Confirm understanding with user |
| 0.5 | Spec Step | Write design doc before any code |
| 1 | Planning Checkpoint | User approves spec |
| 2 | Implementation | Follow the spec |
| 3 | Testing & Validation | ruff ✓, mypy ✓, pytest ✓, pre-commit ✓ |
| 4 | Code Quality | Pattern consistency, spec compliance |
| 5 | Pre-Push Validation | User approves before committing |
| 6 | Commit & Push | `gt modify` + `gt submit` |
| 7 | Pull Request | `gt submit` (PR per stack layer) |
| 8 | Post-PR | Comments / review responses |

---

## Project architecture

```
footprint/              # library source
├── __init__.py
├── scanner.py          # Phase 1 — repo traversal + pattern matching
├── manifest.py         # Phase 1 — network-footprint.yaml loader
├── patterns.py         # Phase 1 — default pattern packs (node, python, devops)
├── report.py           # Phase 1 — JSON + flat output
├── resolver.py         # Phase 2 — dependency manifest parsing + Claude classifier
├── extractor.py        # Phase 5 — EndpointExtractor, EndpointRecord
├── graph.py            # Phase 5 — NetworkGraph, EndpointNode, classification
├── audit_manifest.py   # Phase 5 — footprint-audit.yaml loader
└── audit_report.py     # Phase 5 — audit.json + audit.md renderer
tests/                  # flat — one file per module
templates/              # stack-specific manifest templates
docs/
├── superpowers/specs/  # design specs
└── engineering/        # development workflow guides
```

### Specs (read before implementing a phase)

| Phase | Spec |
|-------|------|
| 1 | `phase-1-core-scanner.md` |
| 2 | `phase-2-dependency-resolution.md` |
| 3 | `phase-3-hardening-accuracy.md` |
| 4 | `phase-4-distribution.md` |
| 5 | `docs/superpowers/specs/2026-05-03-endpoint-audit-design.md` |

---

## Relevant configuration files

| File | Purpose |
|------|---------|
| `pyproject.toml` | ruff rules, mypy config, pytest config, dependencies |
| `.pre-commit-config.yaml` | hook definitions (ruff, mypy, trivy) |
| `.mise.toml` | pins Python 3.11, trivy, ripgrep |
| `uv.lock` | pinned dependency lockfile — commit changes |
| `graphite.md` | `gt` workflow reference |

---

## Dependency policy

New dependencies go through a PR — never add deps directly on `main`.

```bash
uv add <package>           # core dep
uv add --dev <package>     # dev dep
```

---

## 🚫 Never run `git` directly — always run `gt` instead

Exception: `git worktree add/remove` is fine to run directly.

---

## Commit message format

```
<type>(<scope>): <short description>
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

Multi-line:

```bash
gt modify -am "$(cat <<'EOF'
feat(extractor): add EndpointExtractor with Claude fallback

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

## mypy strict mode

mypy strict is a hard gate on every commit.

- 0 errors required — pre-commit hook blocks on violations
- No `# type: ignore` without an inline comment explaining why
- Missing stubs → add to `[[tool.mypy.overrides]]` in `pyproject.toml`
