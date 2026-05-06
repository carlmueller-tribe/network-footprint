# Route Reconciliation Pipeline Design

**Date:** 2026-05-05
**Status:** Approved for implementation planning
**Scope:** Subsystem A only — AST extraction + OpenAPI-spine reconciliation + per-route coverage + structured report. Subsystems B (outbound classification), C (dead-file detection), D (frontend cross-link), and TypeScript server-side support are tracked in a separate follow-on spec.

---

## Goal

Add a new `footprint reconcile` subcommand that treats an OpenAPI/inventory file as the authoritative spine and reconciles a FastAPI codebase against it. The output is a four-bucket structured report — `mounted`, `hidden`, `unmounted`, `spec_only` — with per-route test coverage. Replaces the current bolt-on `--openapi` xref flag, which is a degraded form of the same idea.

---

## Why

Today's scanner produces match lists with confidence scores. To know whether a route is real, mounted, hidden by `include_in_schema=False`, or dead, a human has to cross-reference scanner output against an OpenAPI inventory by hand. This wastes the central insight: when an OpenAPI file exists, it's runtime-generated ground truth — every route in `app.routes` resolved through FastAPI's actual dependency tree. The scanner should reconcile against it, not annotate after the fact.

The four-bucket framing is the product:

- **mounted** — decorator exists in code, route is in the inventory.
- **hidden** — decorator exists with `include_in_schema=False`; route is in `app.routes` but not in OpenAPI by design.
- **unmounted** — decorator exists in code but the composed path is not in the inventory. High-value signal: dead router, never-included file, or wrong prefix.
- **spec_only** — route is in the inventory but no decorator in code matches it. Sanity check; should be empty.

Per-route coverage replaces today's file-level coverage so a 14-route file isn't flagged `likely_active` because one test exercises one route.

---

## Architecture: pipeline of passes

```
                                  ┌──────────────┐
   --openapi PATH ──────────────▶ │  Pass 1      │ ─── Inventory
                                  │  load spec   │     {(METHOD, path), …}
                                  └──────────────┘

                                  ┌──────────────┐    RawRoutes
   <repo_path> ─────────────────▶ │  Pass 2      │ ─▶ list[RawRoute]
                                  │  AST extract │     RouterDefs
                                  │  source/.py  │     list[RouterDef]
                                  └──────────────┘

                                  ┌──────────────┐
   --app-init PATH ─────────────▶ │  Pass 3      │ ─── MountMap
   (or auto-discover)             │  AST extract │     {(target_file, var)
                                  │  init file   │       → mount_prefix}
                                  └──────────────┘

   RawRoutes + RouterDefs         ┌──────────────┐
   + MountMap + Inventory ──────▶ │  Pass 4      │ ─── BucketedReport
                                  │  bucket      │
                                  └──────────────┘

   <repo>/test files +            ┌──────────────┐
   BucketedReport ──────────────▶ │  Pass 5      │ ─── BucketedReport
                                  │  coverage    │     (annotated)
                                  └──────────────┘

                                  ┌──────────────┐
                                  │  Pass 6      │ ─── stdout (JSON)
                                  │  render      │     + optional .md file
                                  └──────────────┘
```

Each pass is a pure function (with file I/O at edges) with a single responsibility. Data shapes between passes are small and named. Walking the file tree twice — once for source, once for tests — is acceptable; even on large repos it's sub-second.

---

## Module layout

```
footprint/
  reconciler/
    __init__.py        # re-exports the public surface
    cli.py             # @main.command() reconcile  — wires passes together
    types.py           # dataclasses
    extract.py         # Pass 2: AST walk over source .py files
    mounts.py          # Pass 3: AST walk over the init file
    bucket.py          # Pass 4: prefix composition + bucketing
    coverage.py        # Pass 5: regex test coverage
    render.py          # Pass 6: JSON + Markdown rendering
    pipeline.py        # orchestrates passes 1-6, called from cli.py
```

`reconciler/__init__.py` exports `run_pipeline`, `BucketedReport`, `ResolvedRoute` so the package has a stable public API.

The shared touch point with existing code is `footprint/openapi_xref.py` — `reconciler/cli.py` calls `openapi_xref.load_inventory_routes()` directly. No other imports into the existing scanner.

---

## Data structures (`reconciler/types.py`)

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class RouterDef:
    """An APIRouter(prefix=...) definition found in a source file."""
    file: str          # repo-relative
    var_name: str      # local variable name, e.g. "_admin_router"
    prefix: str        # "" if no prefix kwarg
    line: int

@dataclass(frozen=True)
class RawRoute:
    """A @<var>.<method>("path", **kwargs) decorator on a function."""
    file: str
    line: int
    router_var: str
    method: str               # "GET", "POST", ...
    decorator_path: str       # exact string from the decorator
    include_in_schema: bool   # default True; False marks hidden
    kwargs: dict[str, str]    # other kwargs as repr strings (audit/debug)

@dataclass(frozen=True)
class MountInfo:
    """An app.include_router(target, prefix=...) call from the init file."""
    init_file: str
    target_file: str          # repo-relative, resolved from the alias's import
    target_var: str           # the original variable name in target_file
    mount_prefix: str

@dataclass
class ResolvedRoute:
    """A fully composed route, ready for bucketing and rendering."""
    file: str
    line: int
    method: str
    full_path: str            # composed: mount + apirouter + decorator
    decorator_path: str       # original
    apirouter_prefix: str
    mount_prefix: str
    include_in_schema: bool
    tested: bool = False
    test_files: list[str] = field(default_factory=list)

@dataclass
class BucketedReport:
    mounted: list[ResolvedRoute]
    hidden: list[ResolvedRoute]
    unmounted: list[ResolvedRoute]
    spec_only: list[tuple[str, str]]   # (method, path), no source location
```

`ResolvedRoute` carries both `decorator_path` and `full_path` so a debugging consumer can see how the composition arrived. `BucketedReport.spec_only` deliberately uses tuples — there is no source location to record.

The reconciler does **not** carry inventory metadata (e.g. K&E-specific `walls`, `data_scope`, `auth`) into the report. The output is structural data only. Downstream tooling that wants stack-specific fields rejoins the inventory by `(method, path)`.

---

## CLI shape

```bash
footprint reconcile <repo_path> --openapi <path> [options]
```

| Flag | Required | Description |
|------|----------|-------------|
| `<repo_path>` | yes | Repository root (positional, defaults to `.`) |
| `--openapi PATH` | yes | api_inventory.json or openapi.{yaml,json} |
| `--app-init PATH` | no | App init file. If omitted, auto-discover (`app/initialize.py`, `app/main.py`, `main.py`, `src/main.py`, `app.py`). If none found, emit warning to stderr and skip mount-prefix resolution. |
| `--md PATH` | no | Write Markdown report to this path (in addition to JSON on stdout) |
| `--manifest PATH` | no | Reuses the existing manifest format; only the `exclude` list is honored |
| `--verbose` / `-v` | no | Pipeline progress to stderr |

JSON to stdout always — the canonical machine contract. `--md` is opt-in.

---

## Per-pass specifications

### Pass 1: load spec (`reconciler/cli.py` calls `openapi_xref.load_inventory_routes`)

Reuses the existing loader. Input is a path; output is `frozenset[tuple[str, str]]` of `(METHOD, path)` pairs. Loader auto-detects format by top-level key — `routes` (TribeAI inventory) vs `paths` (OpenAPI 3.x). YAML or JSON.

No new code — this is a function call.

### Pass 2: AST extract source (`reconciler/extract.py`)

For each `.py` file under `<repo_path>` that is **not** matched by the manifest `exclude` list and **not** matched by the test heuristic (Pass 5), parse with `ast.parse(source)`. The reconciler is Python-only by design — it doesn't consult the manifest's `stacks` config. If a file fails to parse (syntax error, encoding issue), log to stderr in verbose mode and skip it.

Walk the tree looking for:

**APIRouter definitions.** Any `Assign` where the right-hand side is a `Call` whose `func` is `Name("APIRouter")` or `Attribute(value=…, attr="APIRouter")`. Collect:

- target file (repo-relative)
- variable name from `Assign.targets[0].id`
- `prefix` kwarg if present (from `keywords` list, looking for `keyword(arg="prefix", value=Constant(value=str))`)
- line number from `Assign.lineno`

Output a `RouterDef` per definition.

**Route decorators.** Any `FunctionDef` or `AsyncFunctionDef` where one of `decorator_list` is a `Call` whose `func` is `Attribute(value=Name(router_var), attr=method)` and `method.lower() in {"get", "post", "put", "patch", "delete", "head", "options"}`. Collect:

- file (repo-relative)
- line number from `decorator.lineno`
- `router_var` from `func.value.id`
- `method` from `func.attr` (uppercased)
- `decorator_path` from `args[0]` if `Constant(value=str)`; if missing or non-literal, skip the decorator (logged in verbose mode)
- `include_in_schema` from kwargs; default `True`. Look for `keyword(arg="include_in_schema", value=Constant(value=bool))`. If the value is non-literal, default to `True` and log.
- `kwargs` dict — every other keyword's `arg → repr(ast.unparse(value))` for audit

Output a `RawRoute` per decorator.

Multiple decorators on the same function (e.g. a route registered for both GET and POST) yield multiple `RawRoute`s. AST handles multi-line decorators trivially — the regex pain disappears.

### Pass 3: AST extract init file (`reconciler/mounts.py`)

If `--app-init` provided, use it. Otherwise auto-discover by checking these paths in order: `app/initialize.py`, `app/main.py`, `main.py`, `src/main.py`, `app.py` (relative to `<repo_path>`). First hit wins. If none exist, emit a stderr warning and return an empty `MountMap`; the bucketing pass falls back to `mount_prefix=""` for every route.

For the chosen file:

1. Parse with `ast.parse(source)`.
2. Walk for `ImportFrom` nodes. For each `name` in the import: build `alias_map[alias_name] = (target_file_repo_relative, original_name)` where:
   - `target_file_repo_relative = module.replace(".", "/") + ".py"`
   - `original_name = name.name`
   - `alias_name = name.asname if name.asname else name.name`
3. Walk for `Call` nodes where `func` is `Attribute(attr="include_router")`. For each:
   - First positional arg is the local-scope variable name (`Name.id`) — look up in `alias_map`. If not found, skip with a verbose-mode log.
   - `prefix` kwarg if present (`keyword(arg="prefix", value=Constant(str))`). Default `""`.
4. Emit `MountInfo(init_file=…, target_file=…, target_var=…, mount_prefix=…)` per resolved call.

Build the `MountMap` as a dict keyed by `(target_file, target_var) → mount_prefix`.

The reconciler intentionally only follows one hop (init file → directly imported routers). Nested router-includes-router across files isn't resolved; if a repo uses that pattern, those routes show as `unmounted` with `mount_prefix=""` — the four-bucket framing makes the symptom legible.

### Pass 4: bucket (`reconciler/bucket.py`)

For each `RawRoute`:

1. Look up the `RouterDef` for `(file, router_var)`. If found, `apirouter_prefix = router_def.prefix`. If not found, `apirouter_prefix = ""` (decorator references a router var with no `APIRouter()` definition in the same file — likely a re-import; log in verbose).
2. Look up the mount prefix from `MountMap[(file, router_var)]`. If missing, `mount_prefix = ""`.
3. Compose `full_path`:
   - Strip trailing `/` from each component.
   - `full_path = mount_prefix + apirouter_prefix + decorator_path`
   - If the result is empty, `full_path = "/"`.
4. Build a `ResolvedRoute`.
5. Bucket:
   - `include_in_schema=False` → `hidden`
   - else `(method, full_path) in inventory` → `mounted`
   - else → `unmounted`

After all routes are bucketed, sweep the inventory: for each `(method, path)` in inventory not seen as `mounted`, append to `spec_only`.

Path normalization for inventory matching: trailing slash stripped on both sides.

### Pass 5: coverage (`reconciler/coverage.py`)

Walk `.py` files under `<repo_path>` matching the test heuristic — file path matches one of: `tests/**/*.py`, `**/test_*.py`, `**/*_test.py`. (Same heuristic the existing `coverage.py` uses; refactor to share if natural, else duplicate.)

For each test file: read as text and apply regex `\.(?:get|post|put|patch|delete|head|options)\s*\(\s*["']([^"']+)["']`. For each match:

- `method` = the matched HTTP verb, uppercased
- `path` = the captured string

Build a set of `(method, path)` references plus, for each, a list of test files where they appeared.

Then, for each `ResolvedRoute` in `mounted`/`hidden`/`unmounted`: if `(route.method, route.full_path)` is in the test reference set, set `tested=True` and populate `test_files`. Otherwise `tested=False`.

`spec_only` entries are not annotated with coverage — they have no code-side existence.

### Pass 6: render (`reconciler/render.py`)

**JSON output** (always to stdout). The example below is illustrative (not derived from the fixture) and shows the canonical shape of every entry type:

```json
{
  "summary": {
    "repo": "/abs/path/to/repo",
    "openapi": "/abs/path/to/api_inventory.json",
    "app_init": "/abs/path/to/app/initialize.py",
    "scanned_at": "2026-05-05T18:00:00Z",
    "counts": {
      "mounted": 187,
      "hidden": 4,
      "unmounted": 21,
      "spec_only": 0,
      "tested": 142,
      "untested": 70
    }
  },
  "endpoints": {
    "mounted": [
      {
        "method": "GET",
        "path": "/api/auth/check",
        "file": "src/app/routes/auth.py",
        "line": 47,
        "decorator_path": "/check",
        "apirouter_prefix": "/auth",
        "mount_prefix": "/api",
        "tested": true,
        "test_files": ["tests/test_auth.py"]
      }
    ],
    "hidden": [
      {
        "method": "POST",
        "path": "/api/user/merge_users",
        "file": "src/app/routes/user.py",
        "line": 213,
        "decorator_path": "/merge_users",
        "apirouter_prefix": "/user",
        "mount_prefix": "/api",
        "include_in_schema": false,
        "tested": false,
        "test_files": []
      }
    ],
    "unmounted": [
      {
        "method": "GET",
        "path": "/admin/health",
        "file": "src/app/routes/admin.py",
        "line": 12,
        "decorator_path": "/health",
        "apirouter_prefix": "/admin",
        "mount_prefix": "",
        "tested": false,
        "test_files": []
      }
    ],
    "spec_only": [
      {"method": "POST", "path": "/api/legacy/refresh"}
    ]
  }
}
```

`include_in_schema` is omitted from `mounted` entries (implicit `true`) and explicit on `hidden`. `mount_prefix: ""` on `unmounted` is the diagnostic signal that we couldn't resolve a mount.

**Markdown output** (only if `--md PATH` provided):

```markdown
# Network Reconciliation Report
Scanned: `/abs/path/to/repo`
OpenAPI: `/abs/path/to/api_inventory.json`
Generated: 2026-05-05 18:00 UTC

## Summary

| Bucket    | Count | Tested |
|-----------|-------|--------|
| Mounted   | 187   | 142    |
| Hidden    | 4     | 0      |
| Unmounted | 21    | —      |
| Spec-only | 0     | —      |

## Mounted (187)

| Method | Path             | File                       | Line | Tested |
|--------|------------------|----------------------------|------|--------|
| GET    | /api/auth/check  | src/app/routes/auth.py     | 47   | ✓      |
| POST   | /api/auth/login  | src/app/routes/auth.py     | 62   | ✓      |

## Hidden (4)

| Method | Path                       | File                       | Line |
|--------|----------------------------|----------------------------|------|
| POST   | /api/user/merge_users      | src/app/routes/user.py     | 213  |

## Unmounted (21)

| Method | Path           | File                       | Line | Mount resolved |
|--------|----------------|----------------------------|------|----------------|
| GET    | /admin/health  | src/app/routes/admin.py    | 12   | no             |

## Spec-only (0)

*No spec routes are missing from code. ✓*
```

A bucket section renders only if its list is non-empty, except `spec_only`, which always renders (the "no missing routes" sanity statement is part of the report's value).

---

## Testing strategy

| Pass | Test file | Strategy |
|------|-----------|----------|
| 1 | reuses `tests/test_openapi_xref.py` | already covered |
| 2 | `tests/reconciler/test_extract.py` | feed crafted source strings; assert `RawRoute` and `RouterDef` lists. Cases: multi-line decorator, `include_in_schema=False`, no-prefix APIRouter, multiple decorators on one function, decorator with non-literal path (skipped). |
| 3 | `tests/reconciler/test_mounts.py` | crafted init-file source strings; assert `MountInfo` list. Cases: aliased imports (`as`), no-prefix mount, unknown var in `include_router` (skipped), missing init file → empty map. |
| 4 | `tests/reconciler/test_bucket.py` | construct `RawRoute`/`RouterDef`/`MountInfo`/inventory directly (no AST); assert four buckets. Cases: hidden vs unmounted distinction, spec-only sweep, prefix composition correctness, trailing-slash normalization. |
| 5 | `tests/reconciler/test_coverage.py` | crafted test-file strings; assert which routes get `tested=True`. Cases: path with params, multiple tests for one route, repos with no test files. |
| 6 | `tests/reconciler/test_render.py` | construct a `BucketedReport` directly; assert JSON structure (keys, counts, fields) and Markdown structure (section headers, table rows). |
| e2e | `tests/reconciler/test_pipeline.py` | run `pipeline.run()` against the new fixture; assert each bucket's contents. |

### Fixture: `tests/fixtures/fastapi-recon-repo/`

Tiny but realistic FastAPI app exhibiting every bucket:

- `app/initialize.py` — `app.include_router(auth_router, prefix="/api/auth")`, `app.include_router(health_router)` (no prefix), and *deliberately omits* `orphan_router`.
- `app/routes/auth.py` — `APIRouter(prefix="")`, three single-line decorators, one multi-line decorator, one `include_in_schema=False` route. With the `/api/auth` mount prefix from `initialize.py`, routes compose to `/api/auth/<decorator_path>`.
- `app/routes/health.py` — `APIRouter()` with no prefix, one route `@router.get("/health")`. Mounted with no prefix at `app.include_router(health_router)`, so it composes to `/health`.
- `app/routes/orphan.py` — `APIRouter(prefix="/orphan")`, two routes. Never `include_router`'d. Both land in `unmounted` with `mount_prefix=""`.
- `app/api_inventory.json` — every mounted/hidden route, plus one extra `POST /api/legacy/refresh` that doesn't exist in code (drives `spec_only`).
- `tests/test_auth.py` — `client.get("/api/auth/check")`, `client.post("/api/auth/login")`. Some auth routes covered, others not.
- `tests/test_health.py` — `client.get("/health")`.

This fixture supports both unit tests (each pass operates on a slice) and the e2e pipeline test.

---

## Migration

| Surface | Disposition |
|---------|-------------|
| `footprint scan` command | Unchanged. |
| `footprint/path_extractor.py` | Unchanged. Still serves `scan`'s path/method extraction. |
| `footprint/mount_tracker.py` | Unchanged. Still serves `scan --app-init`. |
| `footprint/openapi_xref.py` | Loader function shared. Reconciler imports `load_inventory_routes`. |
| `footprint/scanner.py` | Unchanged. `Match.confirmed` and `ScanResult.mounted` stay (for `scan`-mode output). |
| `footprint/cli.py` | One addition: register the new `reconcile` subcommand under `main`. |
| `footprint/reconciler/` | New package; only imports `openapi_xref` from existing code. |
| README | Add a "Reconciliation mode" section explaining when to use `reconcile` vs `scan`. Stack coverage table gets a row for "Route reconciliation against OpenAPI: FastAPI ✓". |
| Tests | New `tests/reconciler/` directory; no changes to existing tests. |

Net diff: ~8 new files in `footprint/reconciler/`, 1 fixture tree, 6 new test files, 1 click registration, README update. Existing PR stack untouched.

---

## Out of scope (tracked elsewhere)

The follow-on spec at `docs/superpowers/specs/2026-05-05-reconciliation-followons.md` covers:

- **Subsystem B** — outbound call destination classification (base_url tracking, hostname bucketing into third-party / internal-platform / internal-infra)
- **Subsystem C** — dead-file vs. dead-router distinction (cross-file import graph)
- **Subsystem D** — frontend ↔ backend cross-link (TS `fetch()` parsing, dangling reference detection)
- **TypeScript server-side** — Express/NestJS route extraction; same shape as Python AST extraction but different parser

None of these depend on the reconciler's internal data shapes — they consume the same inputs (OpenAPI inventory, source tree) but produce additional analyses. The reconciler's output schema does not need to anticipate them.
