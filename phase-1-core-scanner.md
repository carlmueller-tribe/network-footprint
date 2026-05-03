# Network Footprint Scanner — Phase 1: Core Scanner

## Goal
Build the foundational scaffold. A working scanner that traverses a repo, runs regex patterns against files, and outputs a structured candidate file list. No dependency resolution yet — just the engine.

---

## Deliverables

### 1. Project Scaffold
```
network-footprint/
├── footprint/
│   ├── __init__.py
│   ├── scanner.py
│   ├── manifest.py
│   ├── patterns.py
│   └── report.py
├── cli.py
├── pyproject.toml
└── README.md
```

### 2. `pyproject.toml`
- Package name: `network-footprint`
- CLI entry point: `footprint`
- Dependencies: `pyyaml`, `click`, `pathlib`
- Python >= 3.10

### 3. `patterns.py` — Default Pattern Packs
Hardcoded patterns organized by stack and category. Each pattern has:
- `pattern` — regex string
- `category` — one of: `route_definition`, `network_call`, `devops`
- `stack` — one of: `node`, `python`, `devops`

**Node/TS patterns:**
```python
NODE_PATTERNS = [
    # Network calls
    { "pattern": r"import.*axios", "category": "network_call", "stack": "node" },
    { "pattern": r"require.*axios", "category": "network_call", "stack": "node" },
    { "pattern": r"import.*node-fetch", "category": "network_call", "stack": "node" },
    { "pattern": r"import.*got\b", "category": "network_call", "stack": "node" },
    { "pattern": r"import.*superagent", "category": "network_call", "stack": "node" },
    { "pattern": r"import.*ky\b", "category": "network_call", "stack": "node" },
    { "pattern": r"import.*undici", "category": "network_call", "stack": "node" },
    { "pattern": r"import.*ws\b", "category": "network_call", "stack": "node" },
    { "pattern": r"import.*socket\.io", "category": "network_call", "stack": "node" },
    { "pattern": r"import.*@apollo/client", "category": "network_call", "stack": "node" },
    { "pattern": r"import.*graphql-request", "category": "network_call", "stack": "node" },
    # Native
    { "pattern": r"fetch\(", "category": "network_call", "stack": "node" },
    { "pattern": r"new XMLHttpRequest", "category": "network_call", "stack": "node" },
    { "pattern": r"WebSocket\(", "category": "network_call", "stack": "node" },
    { "pattern": r"EventSource\(", "category": "network_call", "stack": "node" },
    # Routes
    { "pattern": r"(app|router)\.(get|post|put|patch|delete|use)\(", "category": "route_definition", "stack": "node" },
    { "pattern": r"createServer\(", "category": "route_definition", "stack": "node" },
]
```

**Python patterns:**
```python
PYTHON_PATTERNS = [
    # Network calls
    { "pattern": r"import requests", "category": "network_call", "stack": "python" },
    { "pattern": r"from requests", "category": "network_call", "stack": "python" },
    { "pattern": r"import httpx", "category": "network_call", "stack": "python" },
    { "pattern": r"from httpx", "category": "network_call", "stack": "python" },
    { "pattern": r"import aiohttp", "category": "network_call", "stack": "python" },
    { "pattern": r"from aiohttp", "category": "network_call", "stack": "python" },
    { "pattern": r"import boto3", "category": "network_call", "stack": "python" },
    { "pattern": r"import botocore", "category": "network_call", "stack": "python" },
    { "pattern": r"from openai", "category": "network_call", "stack": "python" },
    { "pattern": r"from anthropic", "category": "network_call", "stack": "python" },
    { "pattern": r"import urllib", "category": "network_call", "stack": "python" },
    { "pattern": r"import http\.client", "category": "network_call", "stack": "python" },
    # Routes
    { "pattern": r"@(app|router|blueprint)\.(get|post|put|patch|delete|route)\(", "category": "route_definition", "stack": "python" },
    { "pattern": r"\bpath\(", "category": "route_definition", "stack": "python" },
    { "pattern": r"\bre_path\(", "category": "route_definition", "stack": "python" },
    { "pattern": r"\burl\(", "category": "route_definition", "stack": "python" },
]
```

**DevOps patterns:**
```python
DEVOPS_PATTERNS = [
    { "pattern": r"EXPOSE\s+\d+", "category": "devops", "stack": "devops" },
    { "pattern": r"ports:", "category": "devops", "stack": "devops" },
    { "pattern": r"ENV.*(URL|HOST|ENDPOINT)", "category": "devops", "stack": "devops" },
    { "pattern": r"curl\s", "category": "devops", "stack": "devops" },
    { "pattern": r"wget\s", "category": "devops", "stack": "devops" },
    { "pattern": r"ingress:", "category": "devops", "stack": "devops" },
    { "pattern": r"LoadBalancer", "category": "devops", "stack": "devops" },
]
```

---

### 4. `manifest.py` — Config Loader
- Load `network-footprint.yaml` from repo root (or path passed explicitly)
- Validate required fields
- Return a typed config object

**Manifest schema (Phase 1 — minimal):**
```yaml
stacks:
  - node
  - python
  - devops

exclude:
  - node_modules
  - .git
  - dist
  - __pycache__
  - "*.test.ts"
  - "*.spec.py"
```

- `stacks` — which default pattern packs to activate
- `exclude` — directories or glob patterns to skip entirely

If no manifest is found, fall back to all stacks enabled and a sensible default exclude list.

---

### 5. `scanner.py` — Core Engine
```python
class Scanner:
    def __init__(self, repo_root: str, manifest_path: str = None): ...
    def run(self) -> list[ScanResult]: ...
```

**`ScanResult` shape:**
```python
@dataclass
class Match:
    pattern: str
    category: str  # route_definition | network_call | devops
    stack: str
    line: int

@dataclass
class ScanResult:
    file: str       # relative path from repo root
    categories: list[str]   # deduplicated list of categories matched
    matches: list[Match]
```

**Traversal logic:**
1. Walk the repo root recursively using `pathlib`
2. Skip files/dirs matching any `exclude` pattern from manifest
3. For each file, run all patterns from activated stacks
4. Collect matches; if any, emit a `ScanResult`
5. Also scan devops files by name match (`Dockerfile*`, `docker-compose*.yml`, `.github/**`, `*.tf`, `*.tfvars`, `nginx.conf`) regardless of stack config

**File extension filtering:**
- `node` stack: `.ts`, `.tsx`, `.js`, `.jsx`, `.mjs`
- `python` stack: `.py`
- `devops` stack: `.yml`, `.yaml`, `.tf`, `.tfvars`, `.conf`, `.sh`, `Dockerfile*`, `Makefile`

---

### 6. `report.py` — Output Formatter
Two formats:

**JSON (default):**
```json
[
  {
    "file": "src/services/api.ts",
    "categories": ["network_call"],
    "matches": [
      { "pattern": "import.*axios", "category": "network_call", "stack": "node", "line": 2 }
    ]
  }
]
```

**Flat (one file path per line):**
```
src/services/api.ts
src/routes/users.ts
infrastructure/docker-compose.yml
```

---

### 7. `cli.py` — CLI Entry Point
```bash
footprint scan <repo_path> [--output json|flat] [--manifest <path>]
```

- `<repo_path>` — path to repo root (default: `.`)
- `--output` — output format (default: `json`)
- `--manifest` — explicit path to manifest file (default: `<repo_path>/network-footprint.yaml`)

Output goes to stdout so it can be piped.

---

## Exit Criteria
- [ ] `footprint scan ./some-repo` produces valid JSON output
- [ ] `--output flat` produces a clean file list pipeable to other tools
- [ ] Exclude patterns correctly suppress matched files
- [ ] Stack filtering works — activating only `python` doesn't run node patterns
- [ ] DevOps files are always scanned regardless of stack config
- [ ] Library import works: `from footprint import Scanner`
- [ ] No external dependencies beyond `pyyaml` and `click`
