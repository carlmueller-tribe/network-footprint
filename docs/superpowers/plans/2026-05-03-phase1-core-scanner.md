# Network Footprint Scanner — Phase 1: Core Scanner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase 1 core scanner — project scaffold, pattern packs, manifest loader, file traversal engine, and JSON/flat output formatter with a working `footprint scan` CLI command.

**Architecture:** Scanner walks a repo with pathlib, runs compiled regex patterns per stack against each file, and emits ScanResult objects. Patterns are organised by stack (node/python/devops) and loaded selectively based on manifest config. Output is JSON (default) or flat file list to stdout.

**Tech Stack:** Python 3.11, uv, click≥8, pyyaml≥6, hatchling (build), ruff, mypy (strict), pytest, pre-commit, mise, Graphite (gt)

**Workflow:** Follow AGENTS.md exactly — `gt create` + `git worktree add` per branch, `mise run check` before every commit, `gt submit --stack` to open PRs.

---

## File Map

| File | Status | Responsibility |
|------|--------|----------------|
| `pyproject.toml` | Create | Package metadata, deps, ruff/mypy/pytest config |
| `.gitignore` | Create | Ignore .venv, __pycache__, .worktrees, dist |
| `.pre-commit-config.yaml` | Create | ruff + ruff-format + mypy hooks |
| `.mise.toml` | Create | Pin Python 3.11; define `check` and `trivy:scan` tasks |
| `footprint/__init__.py` | Create | Re-export Scanner, ScanResult, Match |
| `footprint/patterns.py` | Create | NODE_PATTERNS, PYTHON_PATTERNS, DEVOPS_PATTERNS, ALL_PATTERNS |
| `footprint/manifest.py` | Create | ManifestConfig dataclass, load_manifest() |
| `footprint/scanner.py` | Create | Match, ScanResult dataclasses, Scanner class |
| `footprint/report.py` | Create | format_json(), format_flat() |
| `footprint/cli.py` | Create | click CLI — `footprint scan` command |
| `tests/__init__.py` | Create | Empty, marks tests as package |
| `tests/test_patterns.py` | Create | Parametrised positive + negative fixtures per pattern pack |
| `tests/test_manifest.py` | Create | Load from file, fallback, explicit path, empty file |
| `tests/test_scanner.py` | Create | Fixture-based end-to-end scanner tests |
| `tests/test_report.py` | Create | JSON structure, flat format, empty input |
| `tests/fixtures/node-repo/src/services/api.ts` | Create | Positive: axios import (network_call) |
| `tests/fixtures/node-repo/src/routes/users.ts` | Create | Positive: router.get/post (route_definition) |
| `tests/fixtures/node-repo/src/utils/strings.ts` | Create | Negative: no network patterns |
| `tests/fixtures/python-repo/src/routes.py` | Create | Positive: @app.get + requests (route_definition + network_call) |
| `tests/fixtures/python-repo/src/utils.py` | Create | Negative: no network patterns |
| `tests/fixtures/devops-repo/docker-compose.yml` | Create | Positive: ports + ENV URL (devops) |

## Stacking Plan

```
main
 └── feat/phase1-scaffold     ← Task 1 — tooling only, no tests
      └── feat/phase1-patterns ← Task 2 — patterns.py + test_patterns.py
           └── feat/phase1-manifest ← Task 3 — manifest.py + test_manifest.py
                └── feat/phase1-scanner ← Task 4 — scanner.py + fixtures + test_scanner.py
                     └── feat/phase1-cli ← Task 5 — report.py + cli.py + test_report.py
```

---

## Task 1: Project Scaffold

**Branch:** `feat/phase1-scaffold`

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.pre-commit-config.yaml`
- Create: `.mise.toml`
- Create: `footprint/__init__.py`

- [ ] **Step 1: Create the branch and worktree**

```bash
gt sync
gt create -m "chore(scaffold): project tooling and package config"
git worktree add .worktrees/phase1-scaffold feat/phase1-scaffold
cd .worktrees/phase1-scaffold
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "network-footprint"
version = "0.1.0"
description = "Scan a repository for network traffic patterns and API endpoints"
requires-python = ">=3.11"
dependencies = [
    "click>=8.0",
    "pyyaml>=6.0",
]

[project.scripts]
footprint = "footprint.cli:main"

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "ruff>=0.4",
    "mypy>=1.10",
    "types-pyyaml>=6.0",
]

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.11"
strict = true

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 3: Write `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.mypy_cache/
.ruff_cache/
.pytest_cache/
dist/
*.egg-info/
.worktrees/
*.lock.bak
```

- [ ] **Step 4: Write `.pre-commit-config.yaml`**

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.4
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        additional_dependencies:
          - pyyaml
          - types-pyyaml
          - click
        args: [--strict]
```

- [ ] **Step 5: Write `.mise.toml`**

```toml
[tools]
python = "3.11"
trivy = "0.69.3"
ripgrep = "14.1.1"

[tasks.check]
run = [
  "uv run ruff check footprint/ tests/",
  "uv run ruff format --check footprint/ tests/",
  "uv run mypy footprint/",
  "uv run pytest",
]

[tasks."trivy:scan"]
run = "trivy fs --exit-code 1 --severity HIGH,CRITICAL uv.lock"
```

- [ ] **Step 6: Write `footprint/__init__.py`**

```python
from footprint.scanner import Match, Scanner, ScanResult

__all__ = ["Match", "Scanner", "ScanResult"]
```

- [ ] **Step 7: Install dependencies**

```bash
uv sync --extra dev
pre-commit install
mise install
```

Expected: no errors.

- [ ] **Step 8: Commit**

```bash
gt modify -am "$(cat <<'EOF'
chore(scaffold): project tooling and package config

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Pattern Packs

**Branch:** `feat/phase1-patterns`  (stacked on `feat/phase1-scaffold`)

**Files:**
- Create: `footprint/patterns.py`
- Create: `tests/__init__.py`
- Create: `tests/test_patterns.py`

- [ ] **Step 1: Create the branch and worktree**

```bash
# from repo root (not inside a worktree)
gt sync
gt create -m "feat(patterns): node, python, and devops pattern packs"
git worktree add .worktrees/phase1-patterns feat/phase1-patterns
cd .worktrees/phase1-patterns
```

- [ ] **Step 2: Write the failing tests**

Create `tests/__init__.py` (empty file), then create `tests/test_patterns.py`:

```python
import re
import pytest
from footprint.patterns import ALL_PATTERNS, DEVOPS_PATTERNS, NODE_PATTERNS, PYTHON_PATTERNS


@pytest.mark.parametrize(
    "line,expected_category",
    [
        ("import axios from 'axios';", "network_call"),
        ("import { get } from 'node-fetch';", "network_call"),
        ("const res = fetch('https://api.example.com/data');", "network_call"),
        ("const ws = new WebSocket('wss://example.com');", "network_call"),
        ("app.get('/users', handler);", "route_definition"),
        ("router.post('/items', handler);", "route_definition"),
        ("router.delete('/items/:id', handler);", "route_definition"),
    ],
)
def test_node_patterns_positive(line: str, expected_category: str) -> None:
    matched = [p for p in NODE_PATTERNS if re.search(p["pattern"], line)]
    categories = [p["category"] for p in matched]
    assert expected_category in categories, (
        f"Expected category {expected_category!r} not matched in {line!r}\n"
        f"Got: {categories}"
    )


@pytest.mark.parametrize(
    "line",
    [
        "export function formatDate(d: Date): string { return d.toISOString(); }",
        "const PI = 3.14159;",
        "type UserId = string;",
    ],
)
def test_node_patterns_no_false_positive(line: str) -> None:
    matched = [p for p in NODE_PATTERNS if re.search(p["pattern"], line)]
    assert not matched, f"Unexpected match for: {line!r} — matched: {matched}"


@pytest.mark.parametrize(
    "line,expected_category",
    [
        ("import requests", "network_call"),
        ("from requests import Session", "network_call"),
        ("import httpx", "network_call"),
        ("from httpx import AsyncClient", "network_call"),
        ("import aiohttp", "network_call"),
        ("import boto3", "network_call"),
        ("@app.get('/health')", "route_definition"),
        ("@router.post('/items')", "route_definition"),
        ("@blueprint.delete('/items/<int:item_id>')", "route_definition"),
    ],
)
def test_python_patterns_positive(line: str, expected_category: str) -> None:
    matched = [p for p in PYTHON_PATTERNS if re.search(p["pattern"], line)]
    categories = [p["category"] for p in matched]
    assert expected_category in categories, (
        f"Expected {expected_category!r} not matched in {line!r}\nGot: {categories}"
    )


@pytest.mark.parametrize(
    "line",
    [
        "def slugify(text: str) -> str:",
        "return text.lower().replace(' ', '-')",
        "PI = 3.14159",
    ],
)
def test_python_patterns_no_false_positive(line: str) -> None:
    matched = [p for p in PYTHON_PATTERNS if re.search(p["pattern"], line)]
    assert not matched, f"Unexpected match for: {line!r}"


@pytest.mark.parametrize(
    "line,expected_category",
    [
        ("EXPOSE 8080", "devops"),
        ("    ports:", "devops"),
        ("ENV API_URL=https://api.example.com", "devops"),
        ("    ENV HOST=localhost", "devops"),
        ("  curl https://example.com/health", "devops"),
        ("  wget https://example.com/file.tar.gz", "devops"),
        ("ingress:", "devops"),
        ("  LoadBalancer", "devops"),
    ],
)
def test_devops_patterns_positive(line: str, expected_category: str) -> None:
    matched = [p for p in DEVOPS_PATTERNS if re.search(p["pattern"], line)]
    categories = [p["category"] for p in matched]
    assert expected_category in categories, (
        f"Expected {expected_category!r} not matched in {line!r}\nGot: {categories}"
    )


def test_all_patterns_contains_all_stacks() -> None:
    stacks = {p["stack"] for p in ALL_PATTERNS}
    assert stacks == {"node", "python", "devops"}


def test_each_pattern_has_required_keys() -> None:
    for p in ALL_PATTERNS:
        assert "pattern" in p
        assert "category" in p
        assert "stack" in p
        assert p["category"] in ("route_definition", "network_call", "devops")
        assert p["stack"] in ("node", "python", "devops")
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/test_patterns.py -v
```

Expected: `ModuleNotFoundError: No module named 'footprint.patterns'`

- [ ] **Step 4: Write `footprint/patterns.py`**

```python
from typing import TypedDict


class PatternSpec(TypedDict):
    pattern: str
    category: str
    stack: str


NODE_PATTERNS: list[PatternSpec] = [
    # Network calls — library imports
    {"pattern": r"import.*axios", "category": "network_call", "stack": "node"},
    {"pattern": r"require.*axios", "category": "network_call", "stack": "node"},
    {"pattern": r"import.*node-fetch", "category": "network_call", "stack": "node"},
    {"pattern": r"import.*\bgot\b", "category": "network_call", "stack": "node"},
    {"pattern": r"import.*superagent", "category": "network_call", "stack": "node"},
    {"pattern": r"import.*\bky\b", "category": "network_call", "stack": "node"},
    {"pattern": r"import.*undici", "category": "network_call", "stack": "node"},
    {"pattern": r"import.*\bws\b", "category": "network_call", "stack": "node"},
    {"pattern": r"import.*socket\.io", "category": "network_call", "stack": "node"},
    {"pattern": r"import.*@apollo/client", "category": "network_call", "stack": "node"},
    {"pattern": r"import.*graphql-request", "category": "network_call", "stack": "node"},
    # Network calls — native APIs
    {"pattern": r"fetch\(", "category": "network_call", "stack": "node"},
    {"pattern": r"new XMLHttpRequest", "category": "network_call", "stack": "node"},
    {"pattern": r"WebSocket\(", "category": "network_call", "stack": "node"},
    {"pattern": r"EventSource\(", "category": "network_call", "stack": "node"},
    # Route definitions
    {
        "pattern": r"(app|router)\.(get|post|put|patch|delete|use)\(",
        "category": "route_definition",
        "stack": "node",
    },
    {"pattern": r"createServer\(", "category": "route_definition", "stack": "node"},
]

PYTHON_PATTERNS: list[PatternSpec] = [
    # Network calls — library imports
    {"pattern": r"import requests", "category": "network_call", "stack": "python"},
    {"pattern": r"from requests", "category": "network_call", "stack": "python"},
    {"pattern": r"import httpx", "category": "network_call", "stack": "python"},
    {"pattern": r"from httpx", "category": "network_call", "stack": "python"},
    {"pattern": r"import aiohttp", "category": "network_call", "stack": "python"},
    {"pattern": r"from aiohttp", "category": "network_call", "stack": "python"},
    {"pattern": r"import boto3", "category": "network_call", "stack": "python"},
    {"pattern": r"import botocore", "category": "network_call", "stack": "python"},
    {"pattern": r"from openai", "category": "network_call", "stack": "python"},
    {"pattern": r"from anthropic", "category": "network_call", "stack": "python"},
    {"pattern": r"import urllib", "category": "network_call", "stack": "python"},
    {"pattern": r"import http\.client", "category": "network_call", "stack": "python"},
    # Route definitions
    {
        "pattern": r"@(app|router|blueprint)\.(get|post|put|patch|delete|route)\(",
        "category": "route_definition",
        "stack": "python",
    },
    {"pattern": r"\bpath\(", "category": "route_definition", "stack": "python"},
    {"pattern": r"\bre_path\(", "category": "route_definition", "stack": "python"},
    {"pattern": r"\burl\(", "category": "route_definition", "stack": "python"},
]

DEVOPS_PATTERNS: list[PatternSpec] = [
    {"pattern": r"EXPOSE\s+\d+", "category": "devops", "stack": "devops"},
    {"pattern": r"ports:", "category": "devops", "stack": "devops"},
    {"pattern": r"ENV.*(URL|HOST|ENDPOINT)", "category": "devops", "stack": "devops"},
    {"pattern": r"curl\s", "category": "devops", "stack": "devops"},
    {"pattern": r"wget\s", "category": "devops", "stack": "devops"},
    {"pattern": r"ingress:", "category": "devops", "stack": "devops"},
    {"pattern": r"LoadBalancer", "category": "devops", "stack": "devops"},
]

ALL_PATTERNS: list[PatternSpec] = NODE_PATTERNS + PYTHON_PATTERNS + DEVOPS_PATTERNS
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_patterns.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Run full checks**

```bash
mise run check
```

Expected: ruff ✓, mypy ✓, pytest ✓ — all pass.

- [ ] **Step 7: Commit**

```bash
gt modify -am "$(cat <<'EOF'
feat(patterns): add node, python, and devops pattern packs

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Manifest Loader

**Branch:** `feat/phase1-manifest`  (stacked on `feat/phase1-patterns`)

**Files:**
- Create: `footprint/manifest.py`
- Create: `tests/test_manifest.py`

- [ ] **Step 1: Create the branch and worktree**

```bash
gt sync
gt create -m "feat(manifest): network-footprint.yaml config loader"
git worktree add .worktrees/phase1-manifest feat/phase1-manifest
cd .worktrees/phase1-manifest
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_manifest.py`:

```python
from pathlib import Path

import pytest
import yaml

from footprint.manifest import DEFAULT_EXCLUDES, DEFAULT_STACKS, ManifestConfig, load_manifest


def test_fallback_when_no_manifest(tmp_path: Path) -> None:
    config = load_manifest(tmp_path)
    assert config.stacks == DEFAULT_STACKS
    assert config.exclude == DEFAULT_EXCLUDES


def test_load_stacks_and_exclude(tmp_path: Path) -> None:
    (tmp_path / "network-footprint.yaml").write_text(
        yaml.dump({"stacks": ["node"], "exclude": ["node_modules", "dist"]})
    )
    config = load_manifest(tmp_path)
    assert config.stacks == ["node"]
    assert config.exclude == ["node_modules", "dist"]


def test_load_explicit_path(tmp_path: Path) -> None:
    custom = tmp_path / "custom.yaml"
    custom.write_text(yaml.dump({"stacks": ["python"]}))
    config = load_manifest(tmp_path, manifest_path=custom)
    assert config.stacks == ["python"]
    assert config.exclude == DEFAULT_EXCLUDES


def test_empty_file_uses_defaults(tmp_path: Path) -> None:
    (tmp_path / "network-footprint.yaml").write_text("")
    config = load_manifest(tmp_path)
    assert config.stacks == DEFAULT_STACKS
    assert config.exclude == DEFAULT_EXCLUDES


def test_partial_config_fills_missing_with_defaults(tmp_path: Path) -> None:
    (tmp_path / "network-footprint.yaml").write_text(yaml.dump({"stacks": ["devops"]}))
    config = load_manifest(tmp_path)
    assert config.stacks == ["devops"]
    assert config.exclude == DEFAULT_EXCLUDES


def test_manifest_config_is_dataclass() -> None:
    config = ManifestConfig(stacks=["node"], exclude=["node_modules"])
    assert config.stacks == ["node"]
    assert config.exclude == ["node_modules"]
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/test_manifest.py -v
```

Expected: `ModuleNotFoundError: No module named 'footprint.manifest'`

- [ ] **Step 4: Write `footprint/manifest.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_STACKS: list[str] = ["node", "python", "devops"]

DEFAULT_EXCLUDES: list[str] = [
    "node_modules",
    ".git",
    "dist",
    "build",
    "__pycache__",
    ".venv",
    "venv",
    "*.pyc",
]


@dataclass
class ManifestConfig:
    stacks: list[str]
    exclude: list[str]


def load_manifest(
    repo_root: Path,
    manifest_path: Path | None = None,
) -> ManifestConfig:
    path = manifest_path or (repo_root / "network-footprint.yaml")
    if not path.exists():
        return ManifestConfig(stacks=DEFAULT_STACKS, exclude=DEFAULT_EXCLUDES)
    with path.open() as f:
        data: dict[str, object] = yaml.safe_load(f) or {}
    return ManifestConfig(
        stacks=list(data.get("stacks", DEFAULT_STACKS)),  # type: ignore[arg-type]
        exclude=list(data.get("exclude", DEFAULT_EXCLUDES)),  # type: ignore[arg-type]
    )
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_manifest.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Run full checks**

```bash
mise run check
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
gt modify -am "$(cat <<'EOF'
feat(manifest): add ManifestConfig and load_manifest with fallback defaults

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Scanner Engine + Fixtures

**Branch:** `feat/phase1-scanner`  (stacked on `feat/phase1-manifest`)

**Files:**
- Create: `footprint/scanner.py`
- Create: `tests/fixtures/node-repo/src/services/api.ts`
- Create: `tests/fixtures/node-repo/src/routes/users.ts`
- Create: `tests/fixtures/node-repo/src/utils/strings.ts`
- Create: `tests/fixtures/python-repo/src/routes.py`
- Create: `tests/fixtures/python-repo/src/utils.py`
- Create: `tests/fixtures/devops-repo/docker-compose.yml`
- Create: `tests/test_scanner.py`

- [ ] **Step 1: Create the branch and worktree**

```bash
gt sync
gt create -m "feat(scanner): core traversal engine with ScanResult output"
git worktree add .worktrees/phase1-scanner feat/phase1-scanner
cd .worktrees/phase1-scanner
```

- [ ] **Step 2: Create fixture repos**

`tests/fixtures/node-repo/src/services/api.ts` (positive — network_call):
```typescript
import axios from 'axios';

export async function getUser(id: string) {
  return axios.get(`/api/users/${id}`);
}

export async function createItem(data: object) {
  return axios.post('/api/items', data);
}
```

`tests/fixtures/node-repo/src/routes/users.ts` (positive — route_definition):
```typescript
import express from 'express';

const router = express.Router();

router.get('/users', (req, res) => {
  res.json([]);
});

router.post('/users', (req, res) => {
  res.status(201).json({ id: '1' });
});

router.delete('/users/:id', (req, res) => {
  res.status(204).send();
});

export default router;
```

`tests/fixtures/node-repo/src/utils/strings.ts` (negative — should NOT be matched):
```typescript
export function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function slugify(s: string): string {
  return s.toLowerCase().replace(/\s+/g, '-');
}
```

`tests/fixtures/python-repo/src/routes.py` (positive — route_definition + network_call):
```python
from flask import Flask
import requests

app = Flask(__name__)


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}


@app.post('/sync')
def sync() -> dict[str, object]:
    resp = requests.get('https://api.example.com/data')
    return resp.json()
```

`tests/fixtures/python-repo/src/utils.py` (negative — should NOT be matched):
```python
def slugify(text: str) -> str:
    return text.lower().replace(' ', '-')


def truncate(text: str, max_len: int) -> str:
    return text[:max_len] if len(text) > max_len else text
```

`tests/fixtures/devops-repo/docker-compose.yml` (positive — devops):
```yaml
version: '3.8'
services:
  api:
    image: myapp:latest
    ports:
      - "8080:8080"
    environment:
      - API_URL=https://api.example.com
      - HOST=0.0.0.0
```

- [ ] **Step 3: Write the failing tests**

Create `tests/test_scanner.py`:

```python
from pathlib import Path

import pytest

from footprint.manifest import ManifestConfig
from footprint.scanner import Match, ScanResult, Scanner

FIXTURES = Path(__file__).parent / "fixtures"


def test_detects_axios_import_as_network_call() -> None:
    manifest = ManifestConfig(stacks=["node"], exclude=["node_modules"])
    results = Scanner(str(FIXTURES / "node-repo"), manifest).run()
    files = [r.file for r in results]
    assert any("api.ts" in f for f in files), f"Expected api.ts in results, got: {files}"


def test_detects_router_methods_as_route_definition() -> None:
    manifest = ManifestConfig(stacks=["node"], exclude=["node_modules"])
    results = Scanner(str(FIXTURES / "node-repo"), manifest).run()
    route_results = [r for r in results if "route_definition" in r.categories]
    assert route_results, "Expected at least one route_definition result"
    route_files = [r.file for r in route_results]
    assert any("users.ts" in f for f in route_files)


def test_utility_file_not_matched() -> None:
    manifest = ManifestConfig(stacks=["node"], exclude=["node_modules"])
    results = Scanner(str(FIXTURES / "node-repo"), manifest).run()
    files = [r.file for r in results]
    assert not any("strings.ts" in f for f in files), (
        f"strings.ts should not be matched but appeared in: {files}"
    )


def test_python_repo_detects_route_and_network() -> None:
    manifest = ManifestConfig(stacks=["python"], exclude=[])
    results = Scanner(str(FIXTURES / "python-repo"), manifest).run()
    assert results, "Expected matches in python fixture repo"
    all_categories = {c for r in results for c in r.categories}
    assert "route_definition" in all_categories
    assert "network_call" in all_categories


def test_python_utility_file_not_matched() -> None:
    manifest = ManifestConfig(stacks=["python"], exclude=[])
    results = Scanner(str(FIXTURES / "python-repo"), manifest).run()
    files = [r.file for r in results]
    assert not any("utils.py" in f for f in files)


def test_devops_files_scanned_regardless_of_stack() -> None:
    manifest = ManifestConfig(stacks=["node"], exclude=[])
    results = Scanner(str(FIXTURES / "devops-repo"), manifest).run()
    assert results, "Expected devops-repo files to be scanned even with node-only stack"
    files = [r.file for r in results]
    assert any("docker-compose" in f for f in files)


def test_stack_filtering_python_only_skips_ts_files() -> None:
    manifest = ManifestConfig(stacks=["python"], exclude=[])
    results = Scanner(str(FIXTURES / "node-repo"), manifest).run()
    # node-repo has no .py files, so python-only stack should produce no results
    # (devops files not present here either)
    ts_results = [r for r in results if r.file.endswith(".ts")]
    assert not ts_results, f"Python-only stack should not scan .ts files, got: {ts_results}"


def test_exclude_pattern_suppresses_files() -> None:
    manifest = ManifestConfig(stacks=["node", "python"], exclude=["src"])
    results = Scanner(str(FIXTURES / "node-repo"), manifest).run()
    assert all("src" not in r.file for r in results), (
        "Files under 'src/' should be excluded"
    )


def test_scan_result_categories_are_deduplicated() -> None:
    manifest = ManifestConfig(stacks=["python"], exclude=[])
    results = Scanner(str(FIXTURES / "python-repo"), manifest).run()
    for r in results:
        assert len(r.categories) == len(set(r.categories)), (
            f"Duplicate categories in {r.file}: {r.categories}"
        )


def test_match_has_required_fields() -> None:
    manifest = ManifestConfig(stacks=["node"], exclude=[])
    results = Scanner(str(FIXTURES / "node-repo"), manifest).run()
    assert results, "Need at least one result to test Match fields"
    match = results[0].matches[0]
    assert isinstance(match.pattern, str)
    assert match.category in ("route_definition", "network_call", "devops")
    assert match.stack in ("node", "python", "devops")
    assert isinstance(match.line, int)
    assert match.line >= 1


def test_scan_result_file_is_relative_path() -> None:
    manifest = ManifestConfig(stacks=["node"], exclude=[])
    results = Scanner(str(FIXTURES / "node-repo"), manifest).run()
    for r in results:
        assert not r.file.startswith("/"), (
            f"Expected relative path, got absolute: {r.file}"
        )
```

- [ ] **Step 4: Run tests to verify they fail**

```bash
uv run pytest tests/test_scanner.py -v
```

Expected: `ModuleNotFoundError: No module named 'footprint.scanner'`

- [ ] **Step 5: Write `footprint/scanner.py`**

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

from footprint.manifest import ManifestConfig
from footprint.patterns import ALL_PATTERNS, PatternSpec

EXTENSIONS: dict[str, list[str]] = {
    "node": [".ts", ".tsx", ".js", ".jsx", ".mjs"],
    "python": [".py"],
    "devops": [".yml", ".yaml", ".tf", ".tfvars", ".conf", ".sh"],
}

DEVOPS_NAME_PREFIXES: tuple[str, ...] = ("Dockerfile",)
DEVOPS_EXACT_NAMES: frozenset[str] = frozenset({"Makefile"})
DEVOPS_GLOB_NAMES: tuple[str, ...] = ("docker-compose*.yml", "nginx.conf")


@dataclass
class Match:
    pattern: str
    category: str
    stack: str
    line: int


@dataclass
class ScanResult:
    file: str
    categories: list[str]
    matches: list[Match]


class Scanner:
    def __init__(self, repo_root: str, manifest: ManifestConfig) -> None:
        self._root = Path(repo_root).resolve()
        self._manifest = manifest
        self._patterns: list[PatternSpec] = [
            p for p in ALL_PATTERNS if p["stack"] in manifest.stacks
        ]

    def run(self) -> list[ScanResult]:
        results: list[ScanResult] = []
        for path in sorted(self._root.rglob("*")):
            if path.is_dir():
                continue
            rel = path.relative_to(self._root)
            if self._is_excluded(rel):
                continue
            if not self._should_scan(path):
                continue
            matches = self._scan_file(path)
            if matches:
                results.append(
                    ScanResult(
                        file=str(rel),
                        categories=sorted({m.category for m in matches}),
                        matches=matches,
                    )
                )
        return results

    def _is_excluded(self, rel: Path) -> bool:
        for pattern in self._manifest.exclude:
            for part in rel.parts:
                if fnmatch(part, pattern):
                    return True
            if fnmatch(str(rel), pattern):
                return True
        return False

    def _should_scan(self, path: Path) -> bool:
        name = path.name
        # devops files are always scanned regardless of stack config
        if name in DEVOPS_EXACT_NAMES:
            return True
        if any(name.startswith(prefix) for prefix in DEVOPS_NAME_PREFIXES):
            return True
        if any(fnmatch(name, glob) for glob in DEVOPS_GLOB_NAMES):
            return True
        # stack-based extension filtering
        for stack in self._manifest.stacks:
            if path.suffix in EXTENSIONS.get(stack, []):
                return True
        return False

    def _scan_file(self, path: Path) -> list[Match]:
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return []
        matches: list[Match] = []
        seen: set[tuple[str, int]] = set()
        for lineno, line in enumerate(lines, start=1):
            for p in self._patterns:
                if re.search(p["pattern"], line):
                    key = (p["pattern"], lineno)
                    if key not in seen:
                        seen.add(key)
                        matches.append(
                            Match(
                                pattern=p["pattern"],
                                category=p["category"],
                                stack=p["stack"],
                                line=lineno,
                            )
                        )
        return matches
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/test_scanner.py -v
```

Expected: all tests PASS.

- [ ] **Step 7: Run full checks**

```bash
mise run check
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
gt modify -am "$(cat <<'EOF'
feat(scanner): core traversal engine with Match and ScanResult

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Report Formatter + CLI

**Branch:** `feat/phase1-cli`  (stacked on `feat/phase1-scanner`)

**Files:**
- Create: `footprint/report.py`
- Modify: `footprint/cli.py` (create if absent)
- Create: `tests/test_report.py`

- [ ] **Step 1: Create the branch and worktree**

```bash
gt sync
gt create -m "feat(cli): footprint scan command with json and flat output"
git worktree add .worktrees/phase1-cli feat/phase1-cli
cd .worktrees/phase1-cli
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_report.py`:

```python
import json

import pytest

from footprint.report import format_flat, format_json
from footprint.scanner import Match, ScanResult


def _make_results() -> list[ScanResult]:
    return [
        ScanResult(
            file="src/services/api.ts",
            categories=["network_call"],
            matches=[
                Match(
                    pattern="import.*axios",
                    category="network_call",
                    stack="node",
                    line=1,
                )
            ],
        ),
        ScanResult(
            file="src/routes/users.ts",
            categories=["route_definition"],
            matches=[
                Match(
                    pattern=r"(app|router)\.(get|post|put|patch|delete|use)\(",
                    category="route_definition",
                    stack="node",
                    line=5,
                )
            ],
        ),
    ]


def test_format_json_is_valid_json() -> None:
    output = format_json(_make_results())
    data = json.loads(output)
    assert isinstance(data, list)


def test_format_json_structure() -> None:
    output = format_json(_make_results())
    data = json.loads(output)
    assert len(data) == 2
    assert data[0]["file"] == "src/services/api.ts"
    assert data[0]["categories"] == ["network_call"]
    assert len(data[0]["matches"]) == 1
    assert data[0]["matches"][0]["line"] == 1
    assert data[0]["matches"][0]["pattern"] == "import.*axios"
    assert data[0]["matches"][0]["category"] == "network_call"
    assert data[0]["matches"][0]["stack"] == "node"


def test_format_json_empty_returns_empty_array() -> None:
    assert format_json([]) == "[]"


def test_format_flat_one_file_per_line() -> None:
    output = format_flat(_make_results())
    lines = output.splitlines()
    assert lines == ["src/services/api.ts", "src/routes/users.ts"]


def test_format_flat_empty_returns_empty_string() -> None:
    assert format_flat([]) == ""


def test_format_flat_preserves_order() -> None:
    results = _make_results()
    output = format_flat(results)
    lines = output.splitlines()
    assert lines[0] == results[0].file
    assert lines[1] == results[1].file
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/test_report.py -v
```

Expected: `ModuleNotFoundError: No module named 'footprint.report'`

- [ ] **Step 4: Write `footprint/report.py`**

```python
from __future__ import annotations

import json

from footprint.scanner import ScanResult


def format_json(results: list[ScanResult]) -> str:
    data = [
        {
            "file": r.file,
            "categories": r.categories,
            "matches": [
                {
                    "pattern": m.pattern,
                    "category": m.category,
                    "stack": m.stack,
                    "line": m.line,
                }
                for m in r.matches
            ],
        }
        for r in results
    ]
    return json.dumps(data, indent=2)


def format_flat(results: list[ScanResult]) -> str:
    return "\n".join(r.file for r in results)
```

- [ ] **Step 5: Run report tests to verify they pass**

```bash
uv run pytest tests/test_report.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Write `footprint/cli.py`**

```python
from __future__ import annotations

from pathlib import Path

import click

from footprint.manifest import load_manifest
from footprint.report import format_flat, format_json
from footprint.scanner import Scanner


@click.group()
def main() -> None:
    pass


@main.command()
@click.argument("repo_path", default=".", type=click.Path(exists=True))
@click.option(
    "--output",
    default="json",
    type=click.Choice(["json", "flat"]),
    show_default=True,
    help="Output format.",
)
@click.option(
    "--manifest",
    "manifest_path",
    default=None,
    type=click.Path(),
    help="Explicit path to network-footprint.yaml.",
)
def scan(repo_path: str, output: str, manifest_path: str | None) -> None:
    """Scan REPO_PATH for network traffic patterns."""
    root = Path(repo_path)
    mpath = Path(manifest_path) if manifest_path else None
    manifest = load_manifest(root, mpath)
    scanner = Scanner(repo_root=str(root), manifest=manifest)
    results = scanner.run()
    if output == "json":
        click.echo(format_json(results))
    else:
        click.echo(format_flat(results))
```

- [ ] **Step 7: Smoke-test the CLI end-to-end**

```bash
uv run footprint scan tests/fixtures/node-repo --output json
```

Expected: valid JSON array with at least two entries — `src/services/api.ts` and `src/routes/users.ts`. `src/utils/strings.ts` must NOT appear.

```bash
uv run footprint scan tests/fixtures/node-repo --output flat
```

Expected: one file path per line, no blank lines.

```bash
uv run footprint scan tests/fixtures/python-repo
```

Expected: JSON with `src/routes.py` showing both `route_definition` and `network_call` categories.

- [ ] **Step 8: Run full checks**

```bash
mise run check
```

Expected: all pass.

- [ ] **Step 9: Commit**

```bash
gt modify -am "$(cat <<'EOF'
feat(cli): add footprint scan command with json and flat output

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Submit the Stack

- [ ] **Step 1: Submit all branches as a stack**

```bash
gt submit --stack
```

Expected: Graphite opens one PR per branch (5 PRs total), each targeting its parent branch.

- [ ] **Step 2: Verify exit criteria from Phase 1 spec**

```bash
# Valid JSON output
uv run footprint scan tests/fixtures/node-repo --output json | python3 -c "import sys,json; json.load(sys.stdin); print('valid JSON')"

# Flat output is pipeable
uv run footprint scan tests/fixtures/node-repo --output flat | wc -l

# Exclude suppresses files
uv run footprint scan tests/fixtures/node-repo --manifest /dev/stdin <<'EOF' --output flat
stacks: [node]
exclude: [src]
EOF

# Stack filtering — python-only on node repo
uv run footprint scan tests/fixtures/node-repo --manifest /dev/stdin --output flat <<'EOF'
stacks: [python]
EOF
# Expected: empty output (no .py files in node-repo)

# DevOps always scanned
uv run footprint scan tests/fixtures/devops-repo --manifest /dev/stdin --output flat <<'EOF'
stacks: [node]
EOF
# Expected: docker-compose.yml appears

# Library import works
python3 -c "from footprint import Scanner; print('import OK')"
```

---

## Self-Review Notes

**Spec coverage check:**

| Spec requirement | Covered by |
|---|---|
| `footprint scan <repo_path>` produces valid JSON | Task 5 Step 7 |
| `--output flat` produces pipeable file list | Task 5 Step 7 |
| Exclude patterns suppress matched files | Task 4 test_exclude_pattern_suppresses_files |
| Stack filtering works | Task 4 test_stack_filtering_python_only_skips_ts_files |
| DevOps files always scanned | Task 4 test_devops_files_scanned_regardless_of_stack |
| `from footprint import Scanner` works | Task 6 exit criteria |
| No external deps beyond pyyaml and click | pyproject.toml in Task 1 |

All Phase 1 exit criteria covered.

**Next:** Phase 2 plan → `docs/superpowers/plans/2026-05-03-phase2-dependency-resolution.md`
