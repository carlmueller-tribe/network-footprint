# network-footprint

Static analysis tool that maps every place network traffic can occur in a codebase — API endpoints exposed, outbound HTTP calls made, third-party SDKs used, and infrastructure networking config. Produces a structured report suitable for security reviews, architecture docs, and API inventories.

```
footprint scan ./my-repo --output markdown > network-report.md
```

---

## Contents

- [Installation](#installation)
- [Quick start](#quick-start)
- [How it works](#how-it-works)
- [Output formats](#output-formats)
- [CLI reference](#cli-reference)
- [The manifest file](#the-manifest-file)
- [Confidence scores](#confidence-scores)
- [Coverage analysis](#coverage-analysis)
- [Category taxonomy](#category-taxonomy)
- [Claude integration](#claude-integration)
- [Generating a PRR / API inventory](#generating-a-prr--api-inventory)

---

## Installation

Requires Python 3.11+. Install with [uv](https://github.com/astral-sh/uv) (recommended) or pip:

```bash
# uv
uv tool install network-footprint

# pip
pip install network-footprint
```

For Claude-assisted dependency classification (optional but recommended):

```bash
# Option A — Claude Code CLI (uses your existing OAuth session)
# Install from https://claude.ai/code — no extra config needed

# Option B — Anthropic API key
export ANTHROPIC_API_KEY=sk-ant-...
```

---

## Quick start

```bash
# Scan current directory, print JSON
footprint scan .

# Scan a specific repo with Markdown output
footprint scan ./my-repo --output markdown

# Only show high-confidence matches
footprint scan . --min-confidence 0.7

# Skip dependency resolution (faster, no Claude calls)
footprint scan . --no-resolve

# Show what the tool is doing
footprint scan . --verbose
```

---

## How it works

The scanner runs three stages:

### 1. Dependency resolution

Before scanning source files, `footprint` parses your dependency manifests (`package.json`, `pyproject.toml`, `requirements.txt`, `Pipfile`, `go.mod`, `Cargo.toml`) to build a list of direct dependencies. It then classifies each one:

- **Lookup table** — ~200 well-known packages are classified instantly without any external calls (axios, requests, openai, pg, etc.)
- **Prefix rules** — entire families are classified by prefix (`opentelemetry-instrumentation-*`, `@aws-sdk/client-*`, `@sentry/*`, etc.)
- **Claude** — packages not in the lookup table are sent to Claude in batches of 25 for classification. Only *direct* dependencies are sent; transitive lockfile deps are silently skipped.

Network-capable dependencies generate additional import-pattern regexes that are added to the scan.

### 2. File scanning

`footprint` walks the repo (respecting your `exclude` list), reads every file matching the configured stacks, and runs all patterns against each line. It records the line number, the matched line content, whether the match is in a comment or string literal, and whether it's in a test file.

Excluded directories are pruned before descent — `node_modules` and `.venv` are never traversed.

### 3. Confidence scoring

Each match is assigned a confidence score (0–1) based on a set of signals:

| Signal | Effect |
|--------|--------|
| Base score | +0.7 |
| In a comment | −0.4 |
| In a string literal | −0.3 |
| In a test file | −0.1 |
| `route_definition` category | +0.2 |
| From resolved dependency | +0.1 |
| From unverified dependency | −0.3 |
| Additional matches in same file (up to 3) | +0.1 each |

---

## Output formats

### `--output json` (default)

Structured JSON with a summary block and per-file match details. Best for piping into other tools or Claude for further analysis.

```json
{
  "results": [
    {
      "file": "src/api/users.py",
      "categories": ["route_definition"],
      "coverage": "likely_active",
      "matches": [
        {
          "pattern": "@(app|router|blueprint)\\.(get|post|put|patch|delete|route)\\(",
          "category": "route_definition",
          "stack": "python",
          "line": 14,
          "source": "default",
          "confidence": 0.9,
          "context": ""
        }
      ]
    }
  ],
  "summary": {
    "total_files_matched": 23,
    "by_category": { "route_definition": 18, "network_call": 31 },
    "low_confidence_matches": 4
  }
}
```

### `--output markdown`

Human-readable report grouped by category. Includes a confidence legend, per-file coverage indicators (✓ / ⚠), and a line-level match table. Good for sharing with stakeholders.

### `--output flat`

One file path per line. Useful for scripting (`xargs`, `grep`, etc.).

---

## CLI reference

```
footprint scan [REPO_PATH] [OPTIONS]
```

| Flag | Default | Description |
|------|---------|-------------|
| `REPO_PATH` | `.` | Path to the repository root |
| `--output` | `json` | Output format: `json`, `flat`, `markdown` |
| `--manifest PATH` | auto | Path to manifest file (default: `<repo>/network-footprint.yaml`) |
| `--no-resolve` | off | Skip dependency resolution; use built-in patterns only |
| `--min-confidence` | `0.0` | Filter out matches below this threshold (0.0–1.0) |
| `--no-transitive` | off | Exclude matches from transitive dependencies |
| `--verbose` / `-v` | off | Print scan progress to stderr |

### Verbose output

`--verbose` writes progress to stderr (stdout stays clean for piping):

```
[footprint] repo: /path/to/repo
[footprint] stacks: ['node', 'python', 'devops']
[footprint] exclude patterns: 12
[footprint] asking Claude to classify 8 unknown package(s): acme-sdk, internal-rpc...
[footprint]   → calling Claude CLI...
[footprint]   acme-sdk → network_call
[footprint]   internal-rpc → route_definition
[footprint] resolved from lookup: 42
[footprint] resolved via Claude: 8
[footprint] extra patterns generated: 18
[footprint] files matched: 31
[footprint] total matches: 87
```

---

## The manifest file

Place `network-footprint.yaml` in your repository root. The tool auto-discovers it; pass `--manifest <path>` to override.

All sections are optional — without a manifest, sensible defaults apply.

```yaml
stacks:
  - node
  - python
  - devops

exclude:
  - node_modules
  - .venv
  - dist
  - .next
  - __pycache__
  - "*.pyc"

overrides:
  imports:
    # Tell footprint about internal packages the classifier won't know
    - package: "@acme/http-client"
      imports_as: "@acme/http-client"

  patterns:
    add:
      # Inject custom patterns for proprietary clients
      - pattern: "AcmeRpcClient"
        category: network_call
        stack: python

    remove:
      # Suppress patterns that produce false positives in this repo
      - "\\bfetch\\("
```

See [`docs/example-network-footprint.yaml`](docs/example-network-footprint.yaml) for a fully annotated example with all options.

### `stacks`

Controls which file types are scanned. Valid values:

| Stack | File extensions |
|-------|----------------|
| `node` | `.ts` `.tsx` `.js` `.jsx` `.mjs` |
| `python` | `.py` |
| `devops` | `.yml` `.yaml` `.tf` `.tfvars` `.conf` `.sh` + `Dockerfile*` `docker-compose*.yml` `nginx.conf` `Makefile` |

### `exclude`

Glob patterns matched against every path component. `node_modules` matches at any depth. File extensions use shell globs: `"*.pyc"`.

Test files are *not* excluded by default — they are scanned and flagged `context: "test"` with reduced confidence. They also contribute coverage evidence for route definitions. To suppress test file matches entirely, add patterns like `tests`, `"*.spec.ts"`, `"*.test.ts"` to `exclude`.

### `overrides.imports`

Tells the scanner what import name to look for in source code for a given package. Use this for:
- Internal/private packages the lookup table doesn't know about
- Packages where the install name differs from the import name

### `overrides.patterns.add`

Inject custom regex patterns. Each entry requires:

| Field | Required | Description |
|-------|----------|-------------|
| `pattern` | ✓ | Regex string (Python `re` syntax) |
| `category` | ✓ | `network_call` \| `route_definition` \| `telemetry` \| `devops` |
| `stack` | ✓ | `node` \| `python` \| `devops` |

### `overrides.patterns.remove`

List of exact regex strings (from the built-in pattern set) to suppress. Run `footprint scan --output json` and inspect the `pattern` field in matches to find strings to remove.

---

## Confidence scores

Each match gets a score from 0.0 to 1.0 representing the likelihood that it represents a real network call or route definition, not noise.

| Range | Interpretation |
|-------|---------------|
| `0.9–1.0` | Certain — active code, verified dependency |
| `0.7–0.8` | Likely — direct import or route decorator |
| `0.5–0.6` | Uncertain — may be commented out, in a string, or in a test |
| `< 0.5` | Probable noise — comment, string literal, or unknown dep |

Use `--min-confidence 0.7` to focus on high-signal results.

---

## Coverage analysis

For files containing route definitions (`route_definition` category), `footprint` checks whether any test file in the repo calls those routes. It looks for matching URL path segments in:
- Test files that make outbound HTTP calls (`network_call` in test context)
- Test files that register mock routers (e.g. FastAPI `TestClient` route decorators)

The result appears in JSON as `coverage` and in Markdown as a badge:

| Value | Markdown | Meaning |
|-------|----------|---------|
| `likely_active` | ✓ appears in test calls | At least one test references this route's path |
| `no_test_coverage` | ⚠ no test coverage found | No test calls found matching this route |
| *(empty)* | *(none)* | File has no route definitions (coverage not applicable) |

Coverage is a signal, not a guarantee. `likely_active` means the path was seen in a test, not that the route is correct. `no_test_coverage` does not mean the route is unused — it may be tested via integration/E2E tests outside the scanned tree, or called only by external clients.

---

## Category taxonomy

| Category | Description | Examples |
|----------|-------------|---------|
| `route_definition` | Endpoint definitions and internal routing | FastAPI `@router.get(...)`, Express `app.post(...)`, Next.js API routes |
| `network_call` | Explicit outbound calls to external services | `requests.get(...)`, `fetch(...)`, Stripe SDK, OpenAI SDK |
| `telemetry` | Background/implicit calls to observability services | Sentry, DataDog, OpenTelemetry, PostHog |
| `devops` | Infrastructure-level networking config | Dockerfile `EXPOSE`, Kubernetes `ingress:`, `curl` in CI scripts |

---

## Claude integration

When the scanner encounters direct dependencies not in its built-in lookup table, it calls Claude to classify them. This is transparent — you'll see it in `--verbose` output.

**Authentication** (tried in order):

1. **Claude Code CLI** — if `claude` is on your PATH (installed from [claude.ai/code](https://claude.ai/code)), footprint uses your existing OAuth session. No API key needed.
2. **Anthropic API key** — set `ANTHROPIC_API_KEY` and footprint uses the SDK directly.

**What gets sent to Claude:**

Only *direct* dependencies that aren't in the lookup table. Transitive lockfile dependencies (the hundreds of entries in `package-lock.json`) are never sent. The prompt asks Claude to classify each package as network-capable or not, and assign a category.

**Batching:**

Packages are classified in batches of 25 with a 30-second timeout per batch. A progress line is printed for each batch, and individual classification decisions are printed as they arrive:

```
[footprint] asking Claude to classify 12 unknown package(s) (1 batch): acme-sdk, ...
[footprint]   → calling Claude CLI...
[footprint]   acme-sdk → network_call
[footprint]   internal-cache → not network-capable
```

**Skipping Claude:**

Pass `--no-resolve` to skip all dependency resolution and use only the built-in pattern set. Useful for fast local scans or CI runs where Claude is not available.

---

## Generating a PRR / API inventory

`footprint scan` produces the raw material for a security review API inventory. The recommended workflow:

```bash
# 1. Generate structured output
footprint scan ./my-repo --output json > footprint.json

# 2. Give it to Claude with a prompt
claude -p "$(cat <<'EOF'
Convert this network-footprint scan into a markdown table for a security review.

Columns:
- Endpoint / Traffic: the path or service (from line_content)
- Method: HTTP method if discernible, otherwise "TCP" / "SDK call" / etc.
- Service: which app service owns this (from the file path)
- Description: brief plain-English description
- Used: "Yes" if coverage="likely_active", "Review" if coverage="no_test_coverage", "N/A" otherwise
- Notes: flag anything unusual

Focus on route_definition and network_call categories.
Ignore telemetry and devops unless they show unusual external calls.
EOF
)" < footprint.json
```

The `coverage` field in JSON maps directly to the "Used?" column — `likely_active` means the route has test coverage, `no_test_coverage` means it should be reviewed.
