# Phase 2: Dependency Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich the scanner by parsing dependency manifests, resolving each network-capable package to its canonical import name, and injecting generated patterns before the scan runs. Unknown packages are classified via Claude (subprocess-first, SDK fallback).

**Architecture:** New `resolver.py` module handles all dependency work: parse manifests → resolve via KNOWN_PACKAGES lookup → classify unknowns via Claude → generate regex patterns → inject into scanner. Manifest gains an `overrides` section for edge-case corrections. Each Match gets a `source` field (`default` | `dependency_resolved` | `custom`) and optional `transitive` flag.

**Auth strategy for Claude classifier:** Try `claude -p` subprocess first (uses Claude Code OAuth — zero config for existing users). Fall back to `ANTHROPIC_API_KEY` env var + anthropic SDK. Fail gracefully with clear message if neither is available — scan still runs, unknown packages treated as non-network-capable.

**Tech Stack:** Python 3.11, uv, click≥8, pyyaml≥6, anthropic≥0.20 (new dep), hatchling, ruff, mypy (strict), pytest, mise, Graphite (gt)

**Workflow:** Follow AGENTS.md exactly — `gt create` per branch stacked on the previous, `mise run check` before every commit.

---

## File Map

| File | Status | Responsibility |
|------|--------|----------------|
| `footprint/resolver.py` | **Create** | Manifest parsers, KNOWN_PACKAGES lookup, Claude classifier, pattern generator |
| `footprint/manifest.py` | **Modify** | Add `overrides` field to `ManifestConfig`; parse `overrides.imports` and `overrides.patterns` |
| `footprint/patterns.py` | **Modify** | Add `source: NotRequired[str]` to `PatternSpec` TypedDict |
| `footprint/scanner.py` | **Modify** | Accept injected extra patterns; add `source` and `transitive` to `Match` dataclass |
| `footprint/cli.py` | **Modify** | Run resolver before scanner, pass resolved patterns in |
| `footprint/report.py` | **Modify** | Emit `source` and `transitive` fields in JSON output |
| `tests/fixtures/deps/` | **Create** | Fixture dep files for each ecosystem |
| `tests/test_resolver_parsers.py` | **Create** | Parser unit tests |
| `tests/test_resolver_classifier.py` | **Create** | Classifier tests (mocked subprocess + SDK, no live API) |
| `tests/test_resolver_patterns.py` | **Create** | Pattern generation + manifest override tests |
| `tests/test_scanner_phase2.py` | **Create** | Scanner integration tests with injected patterns |
| `tests/test_report_phase2.py` | **Create** | Report tests for source + transitive fields |

---

## Task 1: Dependency Manifest Parsers

**Branch:** `feat/phase2-parsers` (stacked on `feat/phase1-cli`)

**Files:**
- Create: `footprint/resolver.py` (parsers only — no classifier yet)
- Create: `tests/fixtures/deps/package.json`
- Create: `tests/fixtures/deps/package-lock.json`
- Create: `tests/fixtures/deps/requirements.txt`
- Create: `tests/fixtures/deps/pyproject.toml`
- Create: `tests/fixtures/deps/Pipfile`
- Create: `tests/fixtures/deps/go.mod`
- Create: `tests/fixtures/deps/Cargo.toml`
- Create: `tests/test_resolver_parsers.py`

- [ ] **Step 1: Create fixture dependency files**

Create `tests/fixtures/deps/package.json`:
```json
{
  "dependencies": {
    "axios": "^1.0.0",
    "express": "^4.18.0",
    "stripe": "^12.0.0"
  },
  "devDependencies": {
    "typescript": "^5.0.0"
  }
}
```

Create `tests/fixtures/deps/package-lock.json`:
```json
{
  "name": "test-app",
  "lockfileVersion": 3,
  "packages": {
    "": {
      "dependencies": { "axios": "^1.0.0" }
    },
    "node_modules/axios": { "version": "1.6.0" },
    "node_modules/follow-redirects": { "version": "1.15.0" }
  }
}
```

Create `tests/fixtures/deps/requirements.txt`:
```
requests==2.31.0
httpx>=0.24.0
pillow==10.0.0
# comment line
numpy==1.24.0
```

Create `tests/fixtures/deps/pyproject.toml`:
```toml
[project]
dependencies = [
    "fastapi>=0.100.0",
    "anthropic>=0.20",
    "python-dotenv>=1.0.0",
]
```

Create `tests/fixtures/deps/Pipfile`:
```toml
[packages]
flask = "*"
boto3 = ">=1.28"
requests = ">=2.28"

[dev-packages]
pytest = "*"
```

Create `tests/fixtures/deps/go.mod`:
```
module example.com/myapp

go 1.21

require (
	github.com/gin-gonic/gin v1.9.0
	github.com/go-resty/resty/v2 v2.7.0
)
```

Create `tests/fixtures/deps/Cargo.toml`:
```toml
[package]
name = "my-app"
version = "0.1.0"

[dependencies]
reqwest = { version = "0.11", features = ["json"] }
tokio = { version = "1", features = ["full"] }
serde = "1.0"
```

- [ ] **Step 2: Write failing tests for parsers**

Create `tests/test_resolver_parsers.py`:
```python
from __future__ import annotations

from pathlib import Path

import pytest

from footprint.resolver import (
    ParsedDep,
    parse_cargo_toml,
    parse_go_mod,
    parse_package_json,
    parse_package_lock_json,
    parse_pipfile,
    parse_pyproject_toml,
    parse_requirements_txt,
    parse_all,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "deps"


def test_parse_package_json_direct_deps() -> None:
    deps = parse_package_json(FIXTURE_DIR / "package.json")
    names = [d.name for d in deps]
    assert "axios" in names
    assert "express" in names
    assert "stripe" in names


def test_parse_package_json_excludes_dev_deps() -> None:
    deps = parse_package_json(FIXTURE_DIR / "package.json")
    names = [d.name for d in deps]
    assert "typescript" not in names


def test_parse_package_json_ecosystem() -> None:
    deps = parse_package_json(FIXTURE_DIR / "package.json")
    assert all(d.ecosystem == "node" for d in deps)
    assert all(not d.transitive for d in deps)


def test_parse_package_lock_transitive() -> None:
    deps = parse_package_lock_json(FIXTURE_DIR / "package-lock.json")
    names = [d.name for d in deps]
    assert "follow-redirects" in names
    transitive = [d for d in deps if d.name == "follow-redirects"]
    assert transitive[0].transitive is True


def test_parse_requirements_txt() -> None:
    deps = parse_requirements_txt(FIXTURE_DIR / "requirements.txt")
    names = [d.name for d in deps]
    assert "requests" in names
    assert "httpx" in names
    assert "pillow" in names
    assert "numpy" in names


def test_parse_requirements_txt_skips_comments() -> None:
    deps = parse_requirements_txt(FIXTURE_DIR / "requirements.txt")
    assert not any(d.name.startswith("#") for d in deps)


def test_parse_requirements_txt_strips_version_specifiers() -> None:
    deps = parse_requirements_txt(FIXTURE_DIR / "requirements.txt")
    names = [d.name for d in deps]
    assert "requests" in names
    assert not any("==" in n for n in names)


def test_parse_pyproject_toml() -> None:
    deps = parse_pyproject_toml(FIXTURE_DIR / "pyproject.toml")
    names = [d.name for d in deps]
    assert "fastapi" in names
    assert "anthropic" in names
    assert "python-dotenv" in names


def test_parse_pipfile() -> None:
    deps = parse_pipfile(FIXTURE_DIR / "Pipfile")
    names = [d.name for d in deps]
    assert "flask" in names
    assert "boto3" in names
    assert "requests" in names


def test_parse_pipfile_excludes_dev() -> None:
    deps = parse_pipfile(FIXTURE_DIR / "Pipfile")
    names = [d.name for d in deps]
    assert "pytest" not in names


def test_parse_go_mod() -> None:
    deps = parse_go_mod(FIXTURE_DIR / "go.mod")
    names = [d.name for d in deps]
    assert "github.com/gin-gonic/gin" in names
    assert "github.com/go-resty/resty/v2" in names


def test_parse_go_mod_ecosystem() -> None:
    deps = parse_go_mod(FIXTURE_DIR / "go.mod")
    assert all(d.ecosystem == "go" for d in deps)


def test_parse_cargo_toml() -> None:
    deps = parse_cargo_toml(FIXTURE_DIR / "Cargo.toml")
    names = [d.name for d in deps]
    assert "reqwest" in names
    assert "tokio" in names
    assert "serde" in names


def test_parse_cargo_toml_ecosystem() -> None:
    deps = parse_cargo_toml(FIXTURE_DIR / "Cargo.toml")
    assert all(d.ecosystem == "rust" for d in deps)


def test_parser_tolerates_missing_file() -> None:
    deps = parse_requirements_txt(FIXTURE_DIR / "nonexistent.txt")
    assert deps == []


def test_parse_all_combines_available_files() -> None:
    deps = parse_all(FIXTURE_DIR)
    ecosystems = {d.ecosystem for d in deps}
    assert "node" in ecosystems
    assert "python" in ecosystems


def test_parse_all_empty_dir(tmp_path: Path) -> None:
    deps = parse_all(tmp_path)
    assert deps == []
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/test_resolver_parsers.py -v 2>&1 | head -20
```
Expected: ImportError — `footprint.resolver` doesn't exist yet.

- [ ] **Step 4: Implement the parsers in `footprint/resolver.py`**

```python
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:  # Python < 3.11
    import tomllib  # type: ignore[no-redef]


@dataclass
class ParsedDep:
    name: str
    ecosystem: str  # "node" | "python" | "go" | "rust"
    transitive: bool = False


def parse_package_json(path: Path) -> list[ParsedDep]:
    if not path.exists():
        return []
    try:
        data: dict[str, Any] = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    deps: dict[str, Any] = data.get("dependencies") or {}
    return [ParsedDep(name=name, ecosystem="node") for name in deps]


def parse_package_lock_json(path: Path) -> list[ParsedDep]:
    if not path.exists():
        return []
    try:
        data: dict[str, Any] = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    packages: dict[str, Any] = data.get("packages") or {}
    result: list[ParsedDep] = []
    for key in packages:
        if not key or key == "":
            continue
        # strip "node_modules/" prefix
        name = key.removeprefix("node_modules/")
        if name:
            result.append(ParsedDep(name=name, ecosystem="node", transitive=True))
    return result


def parse_requirements_txt(path: Path) -> list[ParsedDep]:
    if not path.exists():
        return []
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return []
    result: list[ParsedDep] = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # strip version specifiers: ==, >=, <=, !=, ~=, >
        name = re.split(r"[=<>!~;\[]", line)[0].strip()
        if name:
            result.append(ParsedDep(name=name, ecosystem="python"))
    return result


def parse_pyproject_toml(path: Path) -> list[ParsedDep]:
    if not path.exists():
        return []
    try:
        data: dict[str, Any] = tomllib.loads(path.read_text())
    except Exception:
        return []
    deps: list[Any] = data.get("project", {}).get("dependencies") or []
    result: list[ParsedDep] = []
    for dep in deps:
        if not isinstance(dep, str):
            continue
        name = re.split(r"[=<>!~;\[]", dep)[0].strip()
        if name:
            result.append(ParsedDep(name=name, ecosystem="python"))
    return result


def parse_pipfile(path: Path) -> list[ParsedDep]:
    if not path.exists():
        return []
    try:
        import tomllib as _tomllib  # noqa: PLC0415
        data: dict[str, Any] = _tomllib.loads(path.read_text())
    except Exception:
        return []
    packages: dict[str, Any] = data.get("packages") or {}
    return [ParsedDep(name=name, ecosystem="python") for name in packages]


def parse_go_mod(path: Path) -> list[ParsedDep]:
    if not path.exists():
        return []
    try:
        text = path.read_text()
    except OSError:
        return []
    result: list[ParsedDep] = []
    in_require = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("require ("):
            in_require = True
            continue
        if in_require and stripped == ")":
            in_require = False
            continue
        if in_require or stripped.startswith("require "):
            parts = stripped.removeprefix("require ").split()
            if parts:
                result.append(ParsedDep(name=parts[0], ecosystem="go"))
    return result


def parse_cargo_toml(path: Path) -> list[ParsedDep]:
    if not path.exists():
        return []
    try:
        import tomllib as _tomllib  # noqa: PLC0415
        data: dict[str, Any] = _tomllib.loads(path.read_text())
    except Exception:
        return []
    deps: dict[str, Any] = data.get("dependencies") or {}
    return [ParsedDep(name=name, ecosystem="rust") for name in deps]


def parse_all(repo_root: Path) -> list[ParsedDep]:
    result: list[ParsedDep] = []
    result.extend(parse_package_json(repo_root / "package.json"))
    result.extend(parse_package_lock_json(repo_root / "package-lock.json"))
    result.extend(parse_requirements_txt(repo_root / "requirements.txt"))
    result.extend(parse_pyproject_toml(repo_root / "pyproject.toml"))
    result.extend(parse_pipfile(repo_root / "Pipfile"))
    result.extend(parse_go_mod(repo_root / "go.mod"))
    result.extend(parse_cargo_toml(repo_root / "Cargo.toml"))
    return result
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_resolver_parsers.py -v
```
Expected: all 16 tests PASS.

- [ ] **Step 6: Run mise check**

```bash
mise run check
```
Expected: ruff, mypy, pytest all pass.

- [ ] **Step 7: Create branch and commit**

```bash
gt create feat/phase2-parsers
git add footprint/resolver.py tests/test_resolver_parsers.py tests/fixtures/deps/
git commit -m "feat(resolver): dependency manifest parsers for node/python/go/rust"
```

---

## Task 2: Package Classifier

**Branch:** `feat/phase2-classifier` (stacked on `feat/phase2-parsers`)

**Files:**
- Modify: `footprint/resolver.py` (add KNOWN_PACKAGES, ResolvedPackage, ClaudeClassifier, resolve_packages)
- Modify: `pyproject.toml` (add `anthropic>=0.20` to dependencies)
- Create: `tests/test_resolver_classifier.py`

- [ ] **Step 1: Add anthropic to pyproject.toml**

In `pyproject.toml`, update the dependencies list:
```toml
dependencies = [
    "click>=8.0",
    "pyyaml>=6.0",
    "anthropic>=0.20",
]
```

Then run:
```bash
uv sync
```

- [ ] **Step 2: Write failing classifier tests**

Create `tests/test_resolver_classifier.py`:
```python
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from footprint.resolver import (
    ParsedDep,
    ResolvedPackage,
    resolve_packages,
)


def test_known_package_resolved_from_lookup_no_claude() -> None:
    deps = [ParsedDep(name="axios", ecosystem="node")]
    with patch("footprint.resolver._classify_with_claude") as mock_claude:
        results = resolve_packages(deps)
        mock_claude.assert_not_called()
    r = next(r for r in results if r.package == "axios")
    assert r.network_capable is True
    assert r.import_name == "axios"
    assert r.category == "network_call"
    assert r.source == "lookup"


def test_known_package_pillow_not_network_capable() -> None:
    deps = [ParsedDep(name="pillow", ecosystem="python")]
    results = resolve_packages(deps)
    r = next(r for r in results if r.package == "pillow")
    assert r.network_capable is False
    assert r.import_name == "PIL"


def test_unknown_package_batched_to_claude() -> None:
    deps = [
        ParsedDep(name="stripe", ecosystem="node"),
        ParsedDep(name="twilio", ecosystem="node"),
    ]
    claude_response = json.dumps([
        {"package": "stripe", "network_capable": True, "import_name": "stripe", "category": "network_call"},
        {"package": "twilio", "network_capable": True, "import_name": "twilio", "category": "network_call"},
    ])
    with patch("footprint.resolver._classify_with_claude", return_value=claude_response) as mock_claude:
        results = resolve_packages(deps)
        mock_claude.assert_called_once()  # batched — not twice

    stripe = next(r for r in results if r.package == "stripe")
    assert stripe.network_capable is True
    assert stripe.source == "claude"


def test_unknown_packages_and_known_mixed() -> None:
    deps = [
        ParsedDep(name="requests", ecosystem="python"),  # known
        ParsedDep(name="stripe", ecosystem="node"),       # unknown
    ]
    claude_response = json.dumps([
        {"package": "stripe", "network_capable": True, "import_name": "stripe", "category": "network_call"},
    ])
    with patch("footprint.resolver._classify_with_claude", return_value=claude_response):
        results = resolve_packages(deps)

    assert any(r.package == "requests" and r.source == "lookup" for r in results)
    assert any(r.package == "stripe" and r.source == "claude" for r in results)


def test_claude_failure_treated_as_non_network() -> None:
    deps = [ParsedDep(name="unknown-pkg", ecosystem="node")]
    with patch("footprint.resolver._classify_with_claude", side_effect=RuntimeError("no auth")):
        results = resolve_packages(deps)
    r = next(r for r in results if r.package == "unknown-pkg")
    assert r.network_capable is False
    assert r.source == "claude_failed"


def test_transitive_flag_preserved() -> None:
    deps = [ParsedDep(name="axios", ecosystem="node", transitive=True)]
    results = resolve_packages(deps)
    r = next(r for r in results if r.package == "axios")
    assert r.transitive is True


def test_claude_subprocess_tried_before_sdk() -> None:
    import shutil
    deps = [ParsedDep(name="stripe", ecosystem="node")]
    claude_json = json.dumps([
        {"package": "stripe", "network_capable": True, "import_name": "stripe", "category": "network_call"},
    ])
    with patch("shutil.which", return_value="/usr/local/bin/claude"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=claude_json, stderr="")
        with patch("footprint.resolver._classify_with_sdk") as mock_sdk:
            results = resolve_packages(deps)
            mock_run.assert_called_once()
            mock_sdk.assert_not_called()


def test_sdk_used_when_claude_cli_absent() -> None:
    import os
    deps = [ParsedDep(name="stripe", ecosystem="node")]
    sdk_json = json.dumps([
        {"package": "stripe", "network_capable": True, "import_name": "stripe", "category": "network_call"},
    ])
    with patch("shutil.which", return_value=None), \
         patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}), \
         patch("footprint.resolver._classify_with_sdk", return_value=sdk_json) as mock_sdk:
        results = resolve_packages(deps)
        mock_sdk.assert_called_once()
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/test_resolver_classifier.py -v 2>&1 | head -20
```
Expected: ImportError — `ResolvedPackage`, `resolve_packages` not defined yet.

- [ ] **Step 4: Add KNOWN_PACKAGES, ResolvedPackage, and classifier to `footprint/resolver.py`**

Append to `footprint/resolver.py` (after the parser functions):

```python
import os
import shutil
import subprocess
import warnings
from typing import NotRequired


@dataclass
class ResolvedPackage:
    package: str
    import_name: str
    network_capable: bool
    category: str | None
    source: str  # "lookup" | "claude" | "manifest_override" | "claude_failed"
    transitive: bool = False


class _KnownPackageEntry:
    network_capable: bool
    import_name: str
    category: str | None


KNOWN_PACKAGES: dict[str, dict[str, Any]] = {
    # Node
    "axios":            {"network_capable": True,  "import_name": "axios",            "category": "network_call"},
    "node-fetch":       {"network_capable": True,  "import_name": "node-fetch",       "category": "network_call"},
    "got":              {"network_capable": True,  "import_name": "got",              "category": "network_call"},
    "superagent":       {"network_capable": True,  "import_name": "superagent",       "category": "network_call"},
    "ky":               {"network_capable": True,  "import_name": "ky",               "category": "network_call"},
    "undici":           {"network_capable": True,  "import_name": "undici",           "category": "network_call"},
    "ws":               {"network_capable": True,  "import_name": "ws",               "category": "network_call"},
    "socket.io-client": {"network_capable": True,  "import_name": "socket.io-client", "category": "network_call"},
    "@apollo/client":   {"network_capable": True,  "import_name": "@apollo/client",   "category": "network_call"},
    "graphql-request":  {"network_capable": True,  "import_name": "graphql-request",  "category": "network_call"},
    "express":          {"network_capable": True,  "import_name": "express",          "category": "route_definition"},
    "fastify":          {"network_capable": True,  "import_name": "fastify",          "category": "route_definition"},
    "koa":              {"network_capable": True,  "import_name": "koa",              "category": "route_definition"},
    "hapi":             {"network_capable": True,  "import_name": "@hapi/hapi",       "category": "route_definition"},
    # Python
    "requests":         {"network_capable": True,  "import_name": "requests",         "category": "network_call"},
    "httpx":            {"network_capable": True,  "import_name": "httpx",            "category": "network_call"},
    "aiohttp":          {"network_capable": True,  "import_name": "aiohttp",          "category": "network_call"},
    "boto3":            {"network_capable": True,  "import_name": "boto3",            "category": "network_call"},
    "botocore":         {"network_capable": True,  "import_name": "botocore",         "category": "network_call"},
    "openai":           {"network_capable": True,  "import_name": "openai",           "category": "network_call"},
    "anthropic":        {"network_capable": True,  "import_name": "anthropic",        "category": "network_call"},
    "fastapi":          {"network_capable": True,  "import_name": "fastapi",          "category": "route_definition"},
    "flask":            {"network_capable": True,  "import_name": "flask",            "category": "route_definition"},
    "django":           {"network_capable": True,  "import_name": "django",           "category": "route_definition"},
    "pillow":           {"network_capable": False, "import_name": "PIL",              "category": None},
    "opencv-python":    {"network_capable": False, "import_name": "cv2",              "category": None},
    "python-dotenv":    {"network_capable": False, "import_name": "dotenv",           "category": None},
    "numpy":            {"network_capable": False, "import_name": "numpy",            "category": None},
    "pandas":           {"network_capable": False, "import_name": "pandas",           "category": None},
    "pydantic":         {"network_capable": False, "import_name": "pydantic",         "category": None},
}

_CLASSIFIER_PROMPT = """\
You are a code analysis assistant. Given a list of package names, classify each one.

For each package return:
- network_capable: true if the package makes or handles HTTP/TCP/WebSocket or other network calls
- import_name: the canonical Python or JS import name (which may differ from the package name)
- category: "network_call" if it makes outbound calls, "route_definition" if it defines server routes, null if neither

Respond ONLY with a JSON array, no preamble, no markdown fences:
[
  {{ "package": "stripe", "network_capable": true, "import_name": "stripe", "category": "network_call" }},
  ...
]

Packages to classify:
{packages}
"""


def _classify_with_claude(packages: list[str]) -> str:
    """Call Claude for package classification. Tries claude CLI subprocess first."""
    prompt = _CLASSIFIER_PROMPT.format(packages="\n".join(packages))
    if shutil.which("claude"):
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        raise RuntimeError(f"claude CLI failed: {result.stderr.strip()}")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        return _classify_with_sdk(packages)
    raise RuntimeError(
        "No Claude authentication available. "
        "Install Claude Code (claude.ai/code) or set ANTHROPIC_API_KEY."
    )


def _classify_with_sdk(packages: list[str]) -> str:
    """Call Claude via anthropic SDK using ANTHROPIC_API_KEY."""
    import anthropic  # noqa: PLC0415

    prompt = _CLASSIFIER_PROMPT.format(packages="\n".join(packages))
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    content = msg.content[0]
    if content.type != "text":
        raise RuntimeError("Unexpected response type from Claude SDK")
    return content.text


def _parse_claude_response(raw: str, packages: list[str]) -> list[dict[str, Any]]:
    """Extract JSON array from Claude response, handling markdown fences."""
    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    # Find first [ and last ] to be robust
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        return list(json.loads(text[start : end + 1]))
    except json.JSONDecodeError:
        return []


def resolve_packages(
    deps: list[ParsedDep],
    overrides: dict[str, str] | None = None,
) -> list[ResolvedPackage]:
    """Resolve deps to ResolvedPackage list. overrides maps package name → import_name."""
    overrides = overrides or {}
    results: list[ResolvedPackage] = []
    unknown: list[ParsedDep] = []

    for dep in deps:
        name_lower = dep.name.lower()
        # Manifest override takes highest priority
        if dep.name in overrides:
            entry = KNOWN_PACKAGES.get(name_lower, {})
            results.append(ResolvedPackage(
                package=dep.name,
                import_name=overrides[dep.name],
                network_capable=entry.get("network_capable", True),
                category=entry.get("category"),
                source="manifest_override",
                transitive=dep.transitive,
            ))
        elif name_lower in KNOWN_PACKAGES:
            entry = KNOWN_PACKAGES[name_lower]
            results.append(ResolvedPackage(
                package=dep.name,
                import_name=entry["import_name"],
                network_capable=bool(entry["network_capable"]),
                category=entry.get("category"),
                source="lookup",
                transitive=dep.transitive,
            ))
        else:
            unknown.append(dep)

    if unknown:
        try:
            raw = _classify_with_claude([d.name for d in unknown])
            classified = _parse_claude_response(raw, [d.name for d in unknown])
            classified_map = {item["package"]: item for item in classified if isinstance(item, dict)}
        except Exception as exc:
            warnings.warn(f"Claude classifier failed: {exc}. Treating unknown packages as non-network.", stacklevel=2)
            classified_map = {}

        for dep in unknown:
            item = classified_map.get(dep.name)
            if item:
                results.append(ResolvedPackage(
                    package=dep.name,
                    import_name=item.get("import_name", dep.name),
                    network_capable=bool(item.get("network_capable", False)),
                    category=item.get("category"),
                    source="claude",
                    transitive=dep.transitive,
                ))
            else:
                results.append(ResolvedPackage(
                    package=dep.name,
                    import_name=dep.name,
                    network_capable=False,
                    category=None,
                    source="claude_failed",
                    transitive=dep.transitive,
                ))

    return results
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_resolver_classifier.py -v
```
Expected: all 8 tests PASS.

- [ ] **Step 6: Run mise check**

```bash
mise run check
```
Expected: all clean.

- [ ] **Step 7: Create branch and commit**

```bash
gt create feat/phase2-classifier
git add footprint/resolver.py pyproject.toml tests/test_resolver_classifier.py
git commit -m "feat(resolver): package classifier with claude-p subprocess and SDK fallback"
```

---

## Task 3: Pattern Generation + Manifest Overrides

**Branch:** `feat/phase2-patterns` (stacked on `feat/phase2-classifier`)

**Files:**
- Modify: `footprint/resolver.py` (add `generate_patterns`)
- Modify: `footprint/patterns.py` (add `source: NotRequired[str]` to `PatternSpec`)
- Modify: `footprint/manifest.py` (add `OverrideConfig`, `ManifestOverrides`, extend `ManifestConfig`)
- Create: `tests/test_resolver_patterns.py`
- Modify: `tests/test_manifest.py` (add override parsing tests)

- [ ] **Step 1: Write failing tests for pattern generation**

Create `tests/test_resolver_patterns.py`:
```python
from __future__ import annotations

from footprint.resolver import ResolvedPackage, generate_patterns
from footprint.patterns import PatternSpec


def _make_pkg(
    name: str,
    import_name: str,
    ecosystem: str,
    *,
    network_capable: bool = True,
    category: str = "network_call",
) -> ResolvedPackage:
    return ResolvedPackage(
        package=name,
        import_name=import_name,
        network_capable=network_capable,
        category=category,
        source="lookup",
    )


def test_python_package_generates_import_patterns() -> None:
    pkg = _make_pkg("stripe", "stripe", "python")
    patterns = generate_patterns([pkg], ecosystem="python")
    pattern_strs = [p["pattern"] for p in patterns]
    assert any("import stripe" in s for s in pattern_strs)
    assert any(s.startswith("from stripe") for s in pattern_strs)


def test_node_package_generates_import_patterns() -> None:
    pkg = _make_pkg("axios", "axios", "node")
    patterns = generate_patterns([pkg], ecosystem="node")
    pattern_strs = [p["pattern"] for p in patterns]
    assert any("axios" in s for s in pattern_strs)


def test_non_network_package_excluded() -> None:
    pkg = _make_pkg("pillow", "PIL", "python", network_capable=False, category=None)
    patterns = generate_patterns([pkg], ecosystem="python")
    assert patterns == []


def test_patterns_tagged_dependency_resolved() -> None:
    pkg = _make_pkg("httpx", "httpx", "python")
    patterns = generate_patterns([pkg], ecosystem="python")
    assert all(p.get("source") == "dependency_resolved" for p in patterns)


def test_node_special_chars_escaped() -> None:
    pkg = _make_pkg("@apollo/client", "@apollo/client", "node")
    patterns = generate_patterns([pkg], ecosystem="node")
    pattern_strs = [p["pattern"] for p in patterns]
    # @ and / are special in regex — must be escaped or safe
    for s in pattern_strs:
        assert "@apollo/client" in s or r"@apollo\/client" in s or r"\@apollo" in s


def test_transitive_flag_on_generated_pattern() -> None:
    pkg = ResolvedPackage(
        package="follow-redirects",
        import_name="follow-redirects",
        network_capable=True,
        category="network_call",
        source="claude",
        transitive=True,
    )
    patterns = generate_patterns([pkg], ecosystem="node")
    assert all(p.get("transitive") is True for p in patterns)
```

- [ ] **Step 2: Write failing manifest override tests**

Append to `tests/test_manifest.py`:
```python
def test_load_manifest_with_import_overrides(tmp_path: Path) -> None:
    yaml_content = """
stacks:
  - python
overrides:
  imports:
    - package: pillow
      imports_as: PIL
    - package: opencv-python
      imports_as: cv2
"""
    manifest_file = tmp_path / "network-footprint.yaml"
    manifest_file.write_text(yaml_content)
    config = load_manifest(tmp_path)
    assert config.overrides is not None
    overrides_map = {o.package: o.imports_as for o in config.overrides.imports}
    assert overrides_map["pillow"] == "PIL"
    assert overrides_map["opencv-python"] == "cv2"


def test_load_manifest_with_pattern_overrides(tmp_path: Path) -> None:
    yaml_content = """
stacks:
  - node
overrides:
  patterns:
    add:
      - pattern: "myInternalClient\\\\("
        category: network_call
        stack: node
    remove:
      - "\\\\burl\\\\("
"""
    manifest_file = tmp_path / "network-footprint.yaml"
    manifest_file.write_text(yaml_content)
    config = load_manifest(tmp_path)
    assert config.overrides is not None
    assert len(config.overrides.patterns.add) == 1
    assert config.overrides.patterns.add[0]["pattern"] == r"myInternalClient\("
    assert r"\burl\(" in config.overrides.patterns.remove


def test_load_manifest_no_overrides(tmp_path: Path) -> None:
    yaml_content = "stacks:\n  - python\n"
    manifest_file = tmp_path / "network-footprint.yaml"
    manifest_file.write_text(yaml_content)
    config = load_manifest(tmp_path)
    assert config.overrides is None
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/test_resolver_patterns.py tests/test_manifest.py -v 2>&1 | tail -10
```
Expected: ImportError / AttributeError.

- [ ] **Step 4: Update `PatternSpec` in `footprint/patterns.py`**

Add `NotRequired` import and `source` + `transitive` fields to `PatternSpec`:

```python
from typing import NotRequired, TypedDict

class PatternSpec(TypedDict):
    pattern: str
    category: str
    stack: str
    source: NotRequired[str]       # "default" | "dependency_resolved" | "custom"
    transitive: NotRequired[bool]
```

All existing `NODE_PATTERNS`, `PYTHON_PATTERNS`, `DEVOPS_PATTERNS` entries stay unchanged — `NotRequired` means the fields are optional.

- [ ] **Step 5: Update `ManifestConfig` in `footprint/manifest.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from footprint.patterns import PatternSpec

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
class ImportOverride:
    package: str
    imports_as: str


@dataclass
class PatternOverrides:
    add: list[PatternSpec] = field(default_factory=list)
    remove: list[str] = field(default_factory=list)


@dataclass
class ManifestOverrides:
    imports: list[ImportOverride] = field(default_factory=list)
    patterns: PatternOverrides = field(default_factory=PatternOverrides)


@dataclass
class ManifestConfig:
    stacks: list[str]
    exclude: list[str]
    overrides: ManifestOverrides | None = None


def _parse_overrides(raw_overrides: Any) -> ManifestOverrides | None:
    if not isinstance(raw_overrides, dict):
        return None
    result = ManifestOverrides()
    # imports
    raw_imports = raw_overrides.get("imports")
    if isinstance(raw_imports, list):
        for item in raw_imports:
            if isinstance(item, dict) and "package" in item and "imports_as" in item:
                result.imports.append(ImportOverride(
                    package=str(item["package"]),
                    imports_as=str(item["imports_as"]),
                ))
    # patterns
    raw_patterns = raw_overrides.get("patterns")
    if isinstance(raw_patterns, dict):
        raw_add = raw_patterns.get("add") or []
        raw_remove = raw_patterns.get("remove") or []
        for item in raw_add:
            if isinstance(item, dict) and "pattern" in item:
                p: PatternSpec = {
                    "pattern": str(item["pattern"]),
                    "category": str(item.get("category", "network_call")),
                    "stack": str(item.get("stack", "node")),
                    "source": "custom",
                }
                result.patterns.add.append(p)
        result.patterns.remove = [str(r) for r in raw_remove if r]
    return result


def load_manifest(
    repo_root: Path,
    manifest_path: Path | None = None,
) -> ManifestConfig:
    path = manifest_path or (repo_root / "network-footprint.yaml")
    if not path.exists():
        return ManifestConfig(stacks=list(DEFAULT_STACKS), exclude=list(DEFAULT_EXCLUDES))
    with path.open() as f:
        try:
            raw = yaml.safe_load(f)
        except yaml.YAMLError:
            return ManifestConfig(stacks=list(DEFAULT_STACKS), exclude=list(DEFAULT_EXCLUDES))
    data: dict[str, Any] = raw if isinstance(raw, dict) else {}
    raw_stacks = data.get("stacks")
    raw_exclude = data.get("exclude")
    overrides = _parse_overrides(data.get("overrides"))
    return ManifestConfig(
        stacks=list(raw_stacks) if isinstance(raw_stacks, list) else list(DEFAULT_STACKS),
        exclude=list(raw_exclude) if isinstance(raw_exclude, list) else list(DEFAULT_EXCLUDES),
        overrides=overrides,
    )
```

- [ ] **Step 6: Add `generate_patterns` to `footprint/resolver.py`**

Append to `footprint/resolver.py`:

```python
import re as _re


def generate_patterns(
    resolved: list[ResolvedPackage],
    ecosystem: str,
) -> list[PatternSpec]:
    """Generate regex patterns from resolved network-capable packages."""
    from footprint.patterns import PatternSpec  # noqa: PLC0415

    patterns: list[PatternSpec] = []
    for pkg in resolved:
        if not pkg.network_capable:
            continue
        imp = pkg.import_name
        escaped = _re.escape(imp)
        base: dict[str, Any] = {
            "category": pkg.category or "network_call",
            "stack": ecosystem if ecosystem in ("node", "python", "devops") else "node",
            "source": "dependency_resolved",
        }
        if pkg.transitive:
            base["transitive"] = True
        if ecosystem == "python":
            patterns.append(PatternSpec(**base, pattern=f"import {_re.escape(imp)}"))  # type: ignore[misc]
            patterns.append(PatternSpec(**base, pattern=f"from {_re.escape(imp)}"))    # type: ignore[misc]
        else:  # node / default
            patterns.append(PatternSpec(**base, pattern=f"from ['\\"]{escaped}['\\""]"))  # type: ignore[misc]
            patterns.append(PatternSpec(**base, pattern=f"require\\(['\\"]{escaped}['\\""]"))  # type: ignore[misc]
    return patterns
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
uv run pytest tests/test_resolver_patterns.py tests/test_manifest.py -v
```
Expected: all tests PASS.

- [ ] **Step 8: Run mise check**

```bash
mise run check
```
Expected: all clean.

- [ ] **Step 9: Create branch and commit**

```bash
gt create feat/phase2-patterns
git add footprint/resolver.py footprint/patterns.py footprint/manifest.py \
        tests/test_resolver_patterns.py tests/test_manifest.py
git commit -m "feat(resolver): pattern generation from deps; manifest override parsing"
```

---

## Task 4: Scanner Integration + Source Field + Output

**Branch:** `feat/phase2-integration` (stacked on `feat/phase2-patterns`)

**Files:**
- Modify: `footprint/scanner.py` (add `source` and `transitive` to `Match`; accept injected patterns)
- Modify: `footprint/cli.py` (run resolver pipeline before scanner)
- Modify: `footprint/report.py` (emit `source` and `transitive` fields in JSON)
- Create: `tests/test_scanner_phase2.py`
- Create: `tests/test_report_phase2.py`

- [ ] **Step 1: Write failing scanner integration tests**

Create `tests/test_scanner_phase2.py`:
```python
from __future__ import annotations

from pathlib import Path

from footprint.manifest import ManifestConfig
from footprint.patterns import PatternSpec
from footprint.scanner import Scanner


def test_injected_pattern_produces_match(tmp_path: Path) -> None:
    (tmp_path / "app.ts").write_text("import stripe from 'stripe';\n")
    injected: list[PatternSpec] = [{
        "pattern": r"from ['\"]stripe['\"]",
        "category": "network_call",
        "stack": "node",
        "source": "dependency_resolved",
    }]
    manifest = ManifestConfig(stacks=["node"], exclude=[])
    scanner = Scanner(str(tmp_path), manifest, extra_patterns=injected)
    results = scanner.run()
    assert len(results) == 1
    match = results[0].matches[0]
    assert match.source == "dependency_resolved"


def test_default_pattern_tagged_default(tmp_path: Path) -> None:
    (tmp_path / "api.ts").write_text("import axios from 'axios';\n")
    manifest = ManifestConfig(stacks=["node"], exclude=[])
    scanner = Scanner(str(tmp_path), manifest)
    results = scanner.run()
    assert len(results) == 1
    for m in results[0].matches:
        assert m.source == "default"


def test_transitive_match_flagged(tmp_path: Path) -> None:
    (tmp_path / "app.ts").write_text("import x from 'follow-redirects';\n")
    injected: list[PatternSpec] = [{
        "pattern": r"from ['\"]follow-redirects['\"]",
        "category": "network_call",
        "stack": "node",
        "source": "dependency_resolved",
        "transitive": True,
    }]
    manifest = ManifestConfig(stacks=["node"], exclude=[])
    scanner = Scanner(str(tmp_path), manifest, extra_patterns=injected)
    results = scanner.run()
    assert results[0].matches[0].transitive is True


def test_remove_override_suppresses_pattern(tmp_path: Path) -> None:
    (tmp_path / "urls.py").write_text("result = url('home', views.home)\n")
    manifest = ManifestConfig(stacks=["python"], exclude=[])
    scanner = Scanner(str(tmp_path), manifest, remove_patterns=[r"\burl\("])
    results = scanner.run()
    # \burl( should be removed; no match expected
    assert results == [] or not any(m.pattern == r"\burl\(" for r in results for m in r.matches)


def test_custom_pattern_tagged_custom(tmp_path: Path) -> None:
    (tmp_path / "client.ts").write_text("myInternalClient('https://api.example.com');\n")
    injected: list[PatternSpec] = [{
        "pattern": r"myInternalClient\(",
        "category": "network_call",
        "stack": "node",
        "source": "custom",
    }]
    manifest = ManifestConfig(stacks=["node"], exclude=[])
    scanner = Scanner(str(tmp_path), manifest, extra_patterns=injected)
    results = scanner.run()
    assert len(results) == 1
    assert results[0].matches[0].source == "custom"
```

- [ ] **Step 2: Write failing report tests**

Create `tests/test_report_phase2.py`:
```python
from __future__ import annotations

import json

from footprint.report import format_json
from footprint.scanner import Match, ScanResult


def test_json_includes_source_field() -> None:
    results = [
        ScanResult(
            file="src/api.ts",
            categories=["network_call"],
            matches=[Match(
                pattern=r"from ['\"]stripe['\"]",
                category="network_call",
                stack="node",
                line=1,
                source="dependency_resolved",
            )],
        )
    ]
    output = json.loads(format_json(results))
    assert output[0]["matches"][0]["source"] == "dependency_resolved"


def test_json_includes_transitive_field_when_true() -> None:
    results = [
        ScanResult(
            file="src/app.ts",
            categories=["network_call"],
            matches=[Match(
                pattern=r"from ['\"]follow-redirects['\"]",
                category="network_call",
                stack="node",
                line=2,
                source="dependency_resolved",
                transitive=True,
            )],
        )
    ]
    output = json.loads(format_json(results))
    assert output[0]["matches"][0]["transitive"] is True


def test_json_omits_transitive_when_false() -> None:
    results = [
        ScanResult(
            file="src/api.ts",
            categories=["network_call"],
            matches=[Match(
                pattern="import requests",
                category="network_call",
                stack="python",
                line=1,
                source="default",
            )],
        )
    ]
    output = json.loads(format_json(results))
    match = output[0]["matches"][0]
    assert "transitive" not in match or match["transitive"] is False
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/test_scanner_phase2.py tests/test_report_phase2.py -v 2>&1 | head -20
```
Expected: TypeError / AttributeError.

- [ ] **Step 4: Update `Match` dataclass and `Scanner` in `footprint/scanner.py`**

```python
from __future__ import annotations

import re
from dataclasses import dataclass, field
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
DEVOPS_GLOB_NAMES: tuple[str, ...] = (
    "docker-compose*.yml",
    "docker-compose*.yaml",
    "nginx.conf",
)


@dataclass
class Match:
    pattern: str
    category: str
    stack: str
    line: int
    source: str = "default"
    transitive: bool = False


@dataclass
class ScanResult:
    file: str
    categories: list[str]
    matches: list[Match]


class Scanner:
    def __init__(
        self,
        repo_root: str,
        manifest: ManifestConfig,
        extra_patterns: list[PatternSpec] | None = None,
        remove_patterns: list[str] | None = None,
    ) -> None:
        self._root = Path(repo_root).resolve()
        self._manifest = manifest
        remove_set: set[str] = set(remove_patterns or [])
        base: list[PatternSpec] = [
            p for p in ALL_PATTERNS
            if (p["stack"] == "devops" or p["stack"] in manifest.stacks)
            and p["pattern"] not in remove_set
        ]
        injected: list[PatternSpec] = [
            p for p in (extra_patterns or [])
            if p["pattern"] not in remove_set
        ]
        self._patterns: list[PatternSpec] = base + injected

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
        if name in DEVOPS_EXACT_NAMES:
            return True
        if any(name.startswith(prefix) for prefix in DEVOPS_NAME_PREFIXES):
            return True
        if any(fnmatch(name, glob) for glob in DEVOPS_GLOB_NAMES):
            return True
        return any(path.suffix in EXTENSIONS.get(stack, []) for stack in self._manifest.stacks)

    def _is_devops_file(self, path: Path) -> bool:
        name = path.name
        if name in DEVOPS_EXACT_NAMES:
            return True
        if any(name.startswith(prefix) for prefix in DEVOPS_NAME_PREFIXES):
            return True
        if any(fnmatch(name, glob) for glob in DEVOPS_GLOB_NAMES):
            return True
        return path.suffix in EXTENSIONS.get("devops", [])

    def _scan_file(self, path: Path) -> list[Match]:
        is_devops = self._is_devops_file(path)
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return []
        matches: list[Match] = []
        seen: set[tuple[str, int]] = set()
        for lineno, line in enumerate(lines, start=1):
            for p in self._patterns:
                if p["stack"] == "devops" and not is_devops:
                    continue
                if re.search(p["pattern"], line):
                    key = (p["pattern"], lineno)
                    if key not in seen:
                        seen.add(key)
                        matches.append(Match(
                            pattern=p["pattern"],
                            category=p["category"],
                            stack=p["stack"],
                            line=lineno,
                            source=p.get("source", "default"),
                            transitive=bool(p.get("transitive", False)),
                        ))
        return matches
```

- [ ] **Step 5: Update `report.py` to emit source and transitive**

```python
from __future__ import annotations

import json

from footprint.scanner import ScanResult


def format_json(results: list[ScanResult]) -> str:
    data = []
    for r in results:
        matches = []
        for m in r.matches:
            entry: dict[str, object] = {
                "pattern": m.pattern,
                "category": m.category,
                "stack": m.stack,
                "line": m.line,
                "source": m.source,
            }
            if m.transitive:
                entry["transitive"] = True
            matches.append(entry)
        data.append({
            "file": r.file,
            "categories": r.categories,
            "matches": matches,
        })
    return json.dumps(data, indent=2)


def format_flat(results: list[ScanResult]) -> str:
    return "\n".join(r.file for r in results)
```

- [ ] **Step 6: Update `cli.py` to wire in the resolver pipeline**

```python
from __future__ import annotations

import sys
from pathlib import Path

import click

from footprint.manifest import load_manifest
from footprint.patterns import PatternSpec
from footprint.report import format_flat, format_json
from footprint.resolver import generate_patterns, parse_all, resolve_packages
from footprint.scanner import Scanner


@click.group()
def main() -> None:
    """Scan repositories for network traffic patterns and API endpoints."""


@main.command()
@click.argument("repo_path", default=".", type=click.Path(exists=True))
@click.option("--output", default="json", type=click.Choice(["json", "flat"]))
@click.option("--manifest", "manifest_path", default=None, type=click.Path(exists=True))
@click.option("--no-resolve", is_flag=True, default=False,
              help="Skip dependency resolution (use default patterns only)")
def scan(
    repo_path: str,
    output: str,
    manifest_path: str | None,
    no_resolve: bool,
) -> None:
    root = Path(repo_path).resolve()
    manifest = load_manifest(root, Path(manifest_path) if manifest_path else None)

    extra_patterns: list[PatternSpec] = []
    remove_patterns: list[str] = []

    # Apply manifest pattern overrides
    if manifest.overrides:
        if manifest.overrides.patterns.add:
            extra_patterns.extend(manifest.overrides.patterns.add)
        remove_patterns = manifest.overrides.patterns.remove

    # Dependency resolution
    if not no_resolve:
        import_overrides: dict[str, str] = {}
        if manifest.overrides:
            import_overrides = {o.package: o.imports_as for o in manifest.overrides.imports}
        try:
            deps = parse_all(root)
            resolved = resolve_packages(deps, overrides=import_overrides)
            for ecosystem in ("python", "node"):
                eco_resolved = [r for r in resolved if r.network_capable]
                extra_patterns.extend(generate_patterns(eco_resolved, ecosystem=ecosystem))
        except Exception as exc:  # noqa: BLE001
            click.echo(f"Warning: dependency resolution failed: {exc}", err=True)

    scanner = Scanner(str(root), manifest, extra_patterns=extra_patterns, remove_patterns=remove_patterns)
    results = scanner.run()

    if output == "json":
        click.echo(format_json(results))
    else:
        flat = format_flat(results)
        if flat:
            click.echo(flat)
```

- [ ] **Step 7: Run all tests**

```bash
uv run pytest -v
```
Expected: all tests PASS (previous 81 + new phase2 tests).

- [ ] **Step 8: Run mise check**

```bash
mise run check
```
Expected: ruff, mypy, pytest all green.

- [ ] **Step 9: Create branch and commit**

```bash
gt create feat/phase2-integration
git add footprint/scanner.py footprint/cli.py footprint/report.py \
        tests/test_scanner_phase2.py tests/test_report_phase2.py
git commit -m "feat(phase2): wire resolver into scanner; source+transitive fields on matches"
```

- [ ] **Step 10: Submit the stack**

```bash
gt submit --stack --no-edit
```

---

## Exit Criteria

- [ ] All supported manifest files parsed correctly when present
- [ ] Known packages resolved from lookup table without Claude call
- [ ] Unknown packages batched into a single Claude call
- [ ] `claude -p` subprocess used when Claude Code is installed; SDK used as fallback
- [ ] Claude fallback fails gracefully — scan still completes
- [ ] Manifest import overrides take precedence over lookup table and Claude
- [ ] Manifest pattern add/remove overrides applied correctly
- [ ] Generated patterns match actual import statements in test fixtures
- [ ] `source` field present on all matches in output
- [ ] Transitive deps flagged separately in output
- [ ] All tests pass with mocked Claude — no live API dependency in CI
