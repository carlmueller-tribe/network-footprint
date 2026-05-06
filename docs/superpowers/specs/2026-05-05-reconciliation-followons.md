# Reconciliation Follow-on Subsystems — Suggestive Spec

**Date:** 2026-05-05
**Status:** Suggestive — not yet designed; documents future-work scope so the main reconciliation pipeline doesn't accidentally absorb it.

This document captures four subsystems intentionally out of scope for the v1 reconciliation pipeline (spec: `2026-05-05-reconciliation-pipeline-design.md`). Each gets its own brainstorm + spec when it becomes the next priority. They are sketched here to:

1. Lock in the boundary — the v1 pipeline's data shapes do not need to anticipate these.
2. Capture the original design intent before context decays.
3. Order them by likely sequencing.

---

## Subsystem B — Outbound destination classification

**Problem.** Today's `footprint scan` returns ~200 `network_call` matches with no hostname classification. The PRR reviewer cares which calls go to third-party services (graph.microsoft.com, api.openai.com, api.anthropic.com), which go to internal platform services (matter-api, foundry, etc.), and which go to internal infrastructure (postgres, valkey, emailengine, temporal). Today they grep.

**Direction.**

1. **Resolve client base URLs.** Track `httpx.AsyncClient(base_url=…)`, `OpenAI(base_url=…)`, `AzureOpenAI(…)`, Microsoft Graph SDK, etc. The base URL is set at construction, not at call site — that's why pattern matching alone misses where most outbound traffic actually goes.
2. **Bucket by destination type.** Three buckets:
   - `third_party` — public hostnames; PRR-relevant
   - `internal_platform` — known internal service hostnames (configurable via manifest)
   - `internal_infra` — compose service hostnames matching the repo's docker-compose / k8s definitions

**Likely shape.** Either a new subcommand (`footprint outbound`) or a `--classify-destinations` flag on `scan`. Independent of the reconciliation pipeline — operates on `network_call` matches, not routes.

**Why not yet.** Base-URL resolution is a real data-flow problem; doing it credibly requires AST + intra-file constant tracking + import resolution. Different shape of work from the reconciliation pipeline; deserves its own design pass.

---

## Subsystem C — Dead-file vs. dead-router distinction

**Problem.** A file like `admin.py` may show up as `unmounted` in the reconciliation report (its router is never `include_router`'d), but it can still export utilities (`AdminUser`, dependencies, helpers) that other endpoint files import. "Router never mounted" and "module never imported" need different remediation:

- **Router never mounted, module imported elsewhere** — the router is dead, but the module isn't. Delete the router; keep the file.
- **Module never imported anywhere** — entire file is dead. Delete the file.

**Direction.** Build a cross-file import graph during AST extraction, then for each `unmounted` file ask: "does any other source file import from this module?"

**Likely shape.** An additional pass in the reconciliation pipeline that runs after Pass 4 and annotates each `unmounted` route with `module_imported_elsewhere: bool`. Or a separate `footprint dead-code` analysis that consumes the reconciliation report.

**Why not yet.** Builds on the AST infrastructure of v1 but introduces a graph data structure that v1 doesn't need. Adding it later is a clean extension; building it now bloats the v1 design.

---

## Subsystem D — Frontend ↔ backend cross-link

**Problem.** `frontend/src/inspector/useCommit.ts` POSTs to `/api/versions`, which doesn't exist in the backend. The scanner picks up the `fetch('/api/versions')` call but doesn't flag the dangling reference. With OpenAPI as the backend's ground truth, every detected frontend `fetch('/api/...')` should resolve to a backend route or be flagged as broken — catches dead-code on both sides.

**Direction.**

1. Parse TS/TSX with `tree-sitter-typescript` or `@babel/parser` (subprocess via Node).
2. Extract every `fetch(url, …)` and library equivalents (axios, ky, common wrappers).
3. Resolve URL strings (literals, simple template strings).
4. Match against the union of `mounted` + `hidden` routes from the reconciliation pipeline.

**Output.**

```json
{
  "frontend_calls": {
    "resolved": [{"file": "...", "line": 42, "method": "GET", "path": "/api/users"}],
    "dangling": [{"file": "...", "line": 88, "method": "POST", "path": "/api/versions"}]
  }
}
```

**Likely shape.** A new subcommand (`footprint frontend-xref`) that takes the reconciliation pipeline's JSON output as input, plus a path to the frontend tree, and emits the resolved/dangling lists.

**Why not yet.** Adds a TypeScript parser dependency and a whole second analysis pipeline. Higher cost than v1's Python-only AST work; deserves its own design pass.

---

## TypeScript server-side route extraction

**Problem.** Express, Fastify, NestJS, and other Node server frameworks define routes the same way FastAPI does: a router object plus a decorator-or-method-call with method + path. v1's reconciliation pipeline is Python-AST-only; TS-server repos can't use it.

**Direction.** Pluggable extractor interface in `reconciler/extract.py`:

```python
class RouteExtractor(Protocol):
    def extract(self, file: Path) -> tuple[list[RouterDef], list[RawRoute]]: ...
```

Python implementation ships in v1 (using `ast`). TS implementation is a separate spec; it would parse with `tree-sitter-typescript` or `@babel/parser`, look for `app.get(...)`, `router.post(...)`, `@Get('...')` (NestJS), and produce the same `RouterDef`/`RawRoute` data shapes.

**Likely shape.** Same `footprint reconcile` command, but with a `--language python|typescript` flag (or auto-detection by file extension). The bucketing, coverage, and rendering passes are language-agnostic and work as-is.

**Why not yet.** No concrete user case; would double the implementation surface for v1. Adding it later is an interface addition, not a refactor — the v1 design contemplates it via the data shapes that already model the universal "router + decorator + path" abstraction.

**Coordination with subsystem D.** D needs a TS parser anyway. If both ship, share the parser infrastructure — likely a single `footprint/parsers/typescript.py` module consumed by both the server-side extractor and the frontend cross-link analyzer.

---

## Suggested sequencing

1. **v1 reconciliation pipeline** (current spec) — Python FastAPI only.
2. **Subsystem C** (dead-file detection) — smallest extension; leverages v1's AST work directly.
3. **Subsystem B** (outbound classification) — independent of reconciliation; can be parallelized with C.
4. **TypeScript server-side** + **Subsystem D** (frontend xref) — share TS parser; ship together.

Sequencing is suggestive; reorder based on user pain.
