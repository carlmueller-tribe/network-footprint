# Network Footprint Scanner — Phase 5: Endpoint Audit

## Goal

Extend the scanner from a file-level candidate list to an endpoint-level audit. Extract individual route definitions and network call sites, cross-reference them across one or more services, and output a structured report identifying active endpoints, orphan candidates (defined but never called, called but never defined), and external callouts.

---

## Overview

Phase 5 adds a `footprint audit` command driven by a `footprint-audit.yaml` manifest. It runs the Phase 1–4 scanner on each declared service, extracts individual endpoint records from matched files using heuristic regex plus a Claude fallback, builds a cross-service network graph, classifies every endpoint, and renders `audit.json` + `audit.md`.

---

## New Modules

```
footprint/
├── extractor.py        # extracts EndpointRecord from matched files
├── graph.py            # builds NetworkGraph, classifies endpoints
├── audit_manifest.py   # loads footprint-audit.yaml
└── audit_report.py     # renders audit.json + audit.md
```

`cli.py` gains a new `audit` subcommand.

---

## Data Flow

```
footprint-audit.yaml
       │
       ▼
AuditManifest.load()
       │
       ▼
Scanner.run() × N services   ← uses cached scan JSON if present
       │
       ▼
EndpointExtractor.extract()  ← regex first, Claude fallback for ambiguous paths
       │
       ▼
NetworkGraph.build()         ← links callers → definitions across all services
       │
       ▼
NetworkGraph.classify()      ← active / orphan_defined / orphan_called / external
       │
       ▼
AuditReport.render()         ← audit.json + audit.md
```

---

## Audit Manifest Schema

`footprint-audit.yaml` is the single control point for a multi-service audit:

```yaml
services:
  frontend:
    path: ./frontend
    scan_output: ./frontend-scan.json   # optional — skip re-scan if present
  backend:
    path: ./backend
  payments-service:
    path: ../payments

# External hostnames that are known/intentional
external_allowlist:
  - "api.stripe.com"
  - "api.openai.com"
  - "api.anthropic.com"

# Override classification for specific paths
known_endpoints:
  keep:
    - path: /api/v1/legacy-export
      reason: "Used by external partner — not visible in codebase"
  remove:
    - path: /api/v1/old-webhook
      reason: "Confirmed deprecated"

output:
  json: ./audit.json
  markdown: ./audit.md
```

**Rules:**
- `scan_output`: re-use a cached Phase 1–4 scan JSON; skip re-traversal
- `external_allowlist`: allowlisted hostnames are catalogued as `allowlisted_external`, not flagged
- `known_endpoints`: human overrides take precedence over graph classification
- Fallback with no manifest: `footprint audit .` treats cwd as a single anonymous service

---

## Endpoint Extraction (`extractor.py`)

Takes a `ScanResult` (file + matched lines) and extracts individual endpoint records.

### Extraction Patterns

**Route definitions** (paths the service *exposes*):
```python
r"(app|router|blueprint)\.(get|post|put|patch|delete|route)\(['\"]([^'\"]+)['\"]"
r"@(app|router)\.(get|post|put|patch|delete|route)\(['\"]([^'\"]+)['\"]"
r"path\(['\"]([^'\"]+)['\"]"       # Django urlpatterns
r"re_path\(['\"]([^'\"]+)['\"]"
```

**Network calls** (URLs/paths the service *calls*):
```python
r"fetch\(['\"]([^'\"]+)['\"]"
r"axios\.(get|post|put|patch|delete)\(['\"]([^'\"]+)['\"]"
r"requests\.(get|post|put|patch|delete)\(['\"]([^'\"]+)['\"]"
r"httpx\.(get|post|put|patch|delete)\(['\"]([^'\"]+)['\"]"
```

### `EndpointRecord` Shape

```python
@dataclass
class EndpointRecord:
    path: str              # raw extracted path
    normalized: str        # normalized: /api/users/{id}
    method: str | None     # GET, POST, etc. — None if not determinable
    kind: str              # "route_definition" | "network_call"
    service: str
    file: str
    line: int
    source: str            # "heuristic" | "claude_resolved"
    confidence: float
    is_external: bool      # True if absolute URL with non-local hostname
    in_test: bool          # inherited from scanner context flag
```

### Path Normalization Rules

- Express `:param` → `{param}`
- FastAPI `{param}` → kept as-is
- Django `<int:pk>` → `{pk}`
- Numeric segments → `{id}` heuristic: `/api/users/123` → `/api/users/{id}`
- Strip query strings: `/api/users?active=true` → `/api/users`
- Strip trailing slashes

### Claude Fallback

Triggered when:
- Extracted path contains a variable reference (`${userId}`, f-strings, template literals)
- Heuristic confidence < 0.6
- Path is a concatenation expression rather than a string literal

Batch pattern: all ambiguous paths from a scan are sent in a single Claude call, same as Phase 2 package classifier.

---

## Network Graph (`graph.py`)

Builds a cross-reference map from all `EndpointRecord`s across all services, then classifies each endpoint.

### `EndpointNode` Shape

```python
@dataclass
class EndpointNode:
    normalized: str
    method: str | None
    definitions: list[EndpointRecord]
    callers: list[EndpointRecord]
    status: str
    confidence: float          # lowest confidence among contributing records
    override: str | None       # "keep" | "remove" from known_endpoints
    override_reason: str | None
```

### Matching Algorithm

1. **Exact match** — normalized paths are identical
2. **Parameterized match** — one path has `{param}` segments where the other has a concrete value; match if all non-param segments align
3. **Prefix/nested match** — `/api/users/{id}/posts` matches `/api/users/123/posts`
4. **Unresolved** — if heuristic confidence < 0.5, batch-send both sides to Claude with file context for judgment

### Classification

| Status | Condition |
|---|---|
| `active` | ≥1 definition AND ≥1 caller |
| `orphan_defined` | ≥1 definition, zero callers across all services |
| `orphan_called` | ≥1 caller, zero matching definitions in any service |
| `external` | Absolute URL with hostname not in `external_allowlist` |
| `allowlisted_external` | Absolute URL hostname in `external_allowlist` |
| `known_keep` | Overridden via `known_endpoints.keep` |
| `known_remove` | Overridden via `known_endpoints.remove` |

**Test file rule:** endpoints called only from test files still classify as `orphan_defined` — test coverage is not production traffic. Test callers are recorded with `in_test: true` but do not prevent the orphan classification.

---

## Output (`audit_report.py`)

### `audit.json`

```json
{
  "services": [
    { "name": "frontend", "path": "./frontend", "scan_output": "./frontend-scan.json" },
    { "name": "backend",  "path": "./backend",  "scan_output": null }
  ],
  "endpoints": [
    {
      "normalized": "/api/users/{id}",
      "method": "GET",
      "status": "active",
      "confidence": 0.92,
      "definitions": [
        { "service": "backend", "file": "src/routes/users.py", "line": 34, "source": "heuristic" }
      ],
      "callers": [
        { "service": "frontend", "file": "src/api/users.ts", "line": 12, "in_test": false }
      ]
    }
  ],
  "external_calls": [
    {
      "url": "https://api.stripe.com/v1/charges",
      "status": "allowlisted_external",
      "callers": [
        { "service": "backend", "file": "src/billing/stripe.py", "line": 55 }
      ]
    }
  ],
  "summary": {
    "audited_at": "2026-05-03T15:00:00Z",
    "services": 2,
    "total_endpoints": 47,
    "active": 31,
    "orphan_defined": 8,
    "orphan_called": 3,
    "external_flagged": 2,
    "external_allowlisted": 3,
    "known_keep": 1,
    "known_remove": 0,
    "low_confidence": 4,
    "test_only_callers": 2,
    "claude_resolved": 6
  }
}
```

### `audit.md`

```markdown
# Network Footprint Audit
**Audited:** 2026-05-03 | **Services:** frontend, backend | **Total endpoints:** 47

## Summary
| Status              | Count |
|---------------------|-------|
| Active              | 31    |
| Orphan — remove?    | 8     |
| Orphan — no def     | 3     |
| External (flagged)  | 2     |
| External (known)    | 3     |
| Low confidence      | 4     |

## Orphan Candidates — Likely Remove
> Defined in codebase, no callers found anywhere.

| Endpoint               | Method | Service  | File                     | Confidence |
|------------------------|--------|----------|--------------------------|------------|
| /api/v1/legacy-export  | GET    | backend  | src/routes/export.py:88  | 0.85       |

## Orphan Candidates — Missing Definition
> Called in codebase, no matching route definition found.

| Endpoint               | Method | Called From                        | Confidence |
|------------------------|--------|------------------------------------|------------|
| /api/internal/refresh  | POST   | frontend/src/auth/session.ts:34    | 0.78       |

## External Callouts — Flagged
| URL                                  | Called From                               |
|--------------------------------------|-------------------------------------------|
| https://api.unknown-vendor.com/data  | backend/src/integrations/vendor.py:22     |

## External Callouts — Known
| Hostname          | Called From                   |
|-------------------|-------------------------------|
| api.stripe.com    | backend/src/billing/stripe.py |

## Active Endpoints
...

_Generated by network-footprint. Low-confidence entries (< 0.7) marked with †._
```

---

## CLI

```bash
# Basic — uses footprint-audit.yaml in cwd
footprint audit

# Explicit manifest
footprint audit --manifest ./footprint-audit.yaml

# Single-repo shorthand
footprint audit . --output json,markdown

# Override output paths
footprint audit --json ./reports/audit.json --markdown ./reports/audit.md

# Confidence filter
footprint audit --min-confidence 0.6

# Use cached scan outputs from manifest
footprint audit --use-cache

# Force fresh scan
footprint audit --no-cache

# Verbose — stderr only
footprint audit --verbose
```

**Exit codes:**
- `0` — clean: no flagged orphans or external callouts
- `1` — findings: orphans or unflagged externals found
- `2` — error: scan or extraction failure

---

## Exit Criteria

- [ ] `footprint audit .` classifies endpoints correctly on fixture repos
- [ ] Route definitions with no callers flagged as `orphan_defined`
- [ ] Network calls with no matching definition flagged as `orphan_called`
- [ ] Absolute URLs with allowlisted hostnames classified as `allowlisted_external`
- [ ] Absolute URLs with unknown hostnames classified as `external` (flagged)
- [ ] Parameterized route matching: `/api/users/{id}` ~ `/api/users/123`
- [ ] Claude fallback triggered for template literal / dynamic path construction
- [ ] Claude fallback fails gracefully — audit completes with confidence downgraded
- [ ] `known_endpoints` overrides respected
- [ ] `--use-cache` skips re-scan when `scan_output` is declared in manifest
- [ ] `audit.json` validates against schema
- [ ] `audit.md` renders all sections with accurate counts
- [ ] Summary block matches endpoint-level data
- [ ] Exit code `1` when orphans or unflagged externals found; `0` when clean
- [ ] Test-file-only callers do not prevent `orphan_defined` classification
- [ ] Claude calls mocked in test suite — no live API dependency in CI
- [ ] Multi-service cross-referencing works across 2+ services in fixtures
- [ ] `--min-confidence` filter applies to audit output same as scan
