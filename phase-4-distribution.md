# Network Footprint Scanner — Phase 4: Distribution

## Goal
Make the tool installable, documented, and runnable in CI. Package it for `pip install`, write usage docs, provide stack-specific manifest templates, and ship a GitHub Actions workflow so it can run automatically on PRs or on-demand.

---

## Deliverables

### 1. Packaging

**`pyproject.toml` (final):**
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "network-footprint"
version = "0.1.0"
description = "Scan a repository for network traffic patterns and API endpoints"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "click>=8.0",
    "pyyaml>=6.0",
    "anthropic>=0.20",
]

[project.scripts]
footprint = "footprint.cli:main"

[project.optional-dependencies]
dev = [
    "pytest",
    "pytest-cov",
    "ruff",
    "mypy",
]
```

**Versioning:** Semantic versioning. `0.1.0` for initial release. No stability guarantees until `1.0.0`.

**PyPI:** Publish to PyPI so it's installable via:
```bash
pip install network-footprint
```

Internal Tribe use can also install directly from GitHub:
```bash
pip install git+https://github.com/TribeAI/network-footprint.git
```

---

### 2. README

Sections:

**Overview**
One paragraph. What it does, why it exists, who it's for.

**Installation**
```bash
pip install network-footprint
```

**Quick Start**
```bash
# Scan current directory
footprint scan .

# Scan a specific repo
footprint scan /path/to/my-repo

# Output flat file list (for piping to Claude)
footprint scan . --output flat > candidate_files.txt
```

**The Manifest**
Explain `network-footprint.yaml`, all fields, defaults. Link to template files.

**Output Format**
Show annotated JSON example. Explain all fields including `confidence`, `source`, `transitive`, `context`.

**Piping to Claude**
Show the recommended downstream usage pattern:
```bash
footprint scan . --output flat | xargs -I {} claude -p \
  "Analyze this file for API endpoints and network calls. 
   Describe each one briefly." {}
```

**Configuration Reference**
Full manifest schema with all options documented.

**Pattern Packs**
List all default patterns per stack with brief rationale for each.

**Contributing**
How to add patterns, how to add a new stack, how to run the test suite.

---

### 3. Manifest Templates

One template per common stack configuration, in `templates/`:

```
templates/
├── node.yaml
├── python.yaml
├── python-fastapi.yaml
├── node-express.yaml
├── fullstack-node-python.yaml
└── devops-only.yaml
```

Each template is a ready-to-use `network-footprint.yaml` pre-configured for that stack with sensible excludes and annotations explaining each field.

**Example — `fullstack-node-python.yaml`:**
```yaml
# network-footprint.yaml
# Template: Full-stack Node + Python application
# Copy this to your repo root and adjust as needed.

stacks:
  - node
  - python
  - devops

exclude:
  # Dependencies
  - node_modules
  - .venv
  - venv
  # Build output
  - dist
  - build
  - .next
  # Python cache
  - __pycache__
  - "*.pyc"
  # Test files (still scanned but flagged as test context)
  # Remove these lines if you want test files fully excluded
  # - "*.test.ts"
  # - "tests/"

# Uncomment and populate to override import names for packages
# where the install name differs from the import name
# overrides:
#   imports:
#     - package: pillow
#       imports_as: PIL

# Uncomment to add project-specific patterns
# overrides:
#   patterns:
#     add:
#       - pattern: "myInternalClient\\("
#         category: network_call
#         stack: node
```

---

### 4. GitHub Actions Workflow

Two workflow modes:

**Mode 1 — PR Check (`network-footprint-check.yml`)**
Runs on every PR. Fails if new network-capable files are introduced without being listed in a `network-footprint-allowlist.yaml`. Useful for keeping the inventory current.

```yaml
name: Network Footprint Check
on: [pull_request]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install network-footprint
      - run: footprint scan . --output json > footprint-report.json
      - uses: actions/upload-artifact@v4
        with:
          name: footprint-report
          path: footprint-report.json
```

**Mode 2 — On-Demand Audit (`network-footprint-audit.yml`)**
Manually triggered. Runs the full scan and uploads the JSON report as an artifact. Used for PRR-style audits.

```yaml
name: Network Footprint Audit
on:
  workflow_dispatch:
    inputs:
      min_confidence:
        description: 'Minimum confidence threshold (0.0–1.0)'
        default: '0.5'

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install network-footprint
      - run: |
          footprint scan . \
            --output json \
            --min-confidence ${{ github.event.inputs.min_confidence }} \
            > footprint-audit.json
      - uses: actions/upload-artifact@v4
        with:
          name: footprint-audit
          path: footprint-audit.json
```

**Environment variable for Claude API key:**
```yaml
env:
  ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

Document in README that `ANTHROPIC_API_KEY` must be set as a repo secret for dependency resolution to work in CI.

---

### 5. CHANGELOG

Start a `CHANGELOG.md` following Keep a Changelog format. Document Phase 1–4 as `0.1.0` initial release.

---

## Exit Criteria
- [ ] `pip install network-footprint` works from PyPI
- [ ] `pip install git+https://...` works from GitHub
- [ ] `footprint scan .` works in a clean environment with only the package installed
- [ ] README covers all features added in Phases 1–3
- [ ] All three manifest templates are valid and tested against fixture repos
- [ ] GitHub Actions PR check workflow runs successfully on a test repo
- [ ] GitHub Actions audit workflow runs successfully and uploads artifact
- [ ] `ANTHROPIC_API_KEY` requirement documented clearly
- [ ] `CHANGELOG.md` present and accurate
