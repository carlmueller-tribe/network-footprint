# Reconciliation Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `footprint reconcile` subcommand: AST-driven, OpenAPI-spine reconciliation of a FastAPI codebase, producing a four-bucket structured report with per-route coverage.

**Architecture:** Pipeline of pure functions — load OpenAPI → AST-extract source → AST-extract init file → bucket → annotate test coverage → render. Each pass has a single responsibility and is independently testable. Internal package at `footprint/reconciler/`, registered as a click subcommand on the existing `main` group.

**Tech Stack:** Python 3.11+, stdlib `ast`, click, pytest, pyyaml. Reuses `footprint/openapi_xref.py`'s loader; otherwise no imports into the existing scanner.

**Spec:** `docs/superpowers/specs/2026-05-05-reconciliation-pipeline-design.md`

**Graphite stack:** Each task is one Graphite PR. Tasks branch sequentially via `gt create`, which auto-tracks the parent. After all tasks complete, run `gt submit --stack` once to push the entire stack.

---

## File structure

| Path | Created in | Purpose |
|------|-----------|---------|
| `footprint/reconciler/__init__.py` | Task 1 | Package init; exports public API |
| `footprint/reconciler/types.py` | Task 1 | Dataclasses: `RouterDef`, `RawRoute`, `MountInfo`, `ResolvedRoute`, `BucketedReport` |
| `footprint/reconciler/extract.py` | Task 2 | Pass 2: AST walk over source `.py` files |
| `footprint/reconciler/mounts.py` | Task 3 | Pass 3: AST walk over the app init file + auto-discover |
| `footprint/reconciler/bucket.py` | Task 4 | Pass 4: prefix composition + four-bucket assignment |
| `footprint/reconciler/coverage.py` | Task 5 | Pass 5: regex test coverage extraction |
| `footprint/reconciler/render.py` | Task 6 | Pass 6: JSON + Markdown rendering |
| `footprint/reconciler/pipeline.py` | Task 7 | Orchestrates passes 1–6 |
| `footprint/reconciler/cli.py` | Task 8 | `reconcile` click subcommand |
| `tests/reconciler/test_extract.py` | Task 2 | Unit tests for extract |
| `tests/reconciler/test_mounts.py` | Task 3 | Unit tests for mounts |
| `tests/reconciler/test_bucket.py` | Task 4 | Unit tests for bucket |
| `tests/reconciler/test_coverage.py` | Task 5 | Unit tests for coverage |
| `tests/reconciler/test_render.py` | Task 6 | Unit tests for render |
| `tests/reconciler/test_pipeline.py` | Task 7 | E2E test against fixture |
| `tests/reconciler/test_cli.py` | Task 8 | CLI integration test |
| `tests/fixtures/fastapi-recon-repo/` | Task 7 | Full fixture tree |
| `footprint/cli.py` | Task 8 | Adds `main.add_command(reconcile)` |
| `README.md` | Task 9 | Adds reconciliation mode section + stack-coverage row |

---

## Task 1: Scaffold the reconciler package + dataclasses

**Branch:** `feat/reconciler-types` (parent: `docs/reconciler-design`)

**Files:**
- Create: `footprint/reconciler/__init__.py`
- Create: `footprint/reconciler/types.py`
- Create: `tests/reconciler/__init__.py`
- Create: `tests/reconciler/test_types.py`

- [ ] **Step 1: Create the branch**

```bash
gt create feat/reconciler-types
```

- [ ] **Step 2: Create `tests/reconciler/__init__.py`**

Empty file (marks tests/reconciler/ as a package for pytest collection).

```bash
mkdir -p tests/reconciler
touch tests/reconciler/__init__.py
```

- [ ] **Step 3: Write the failing test**

Create `tests/reconciler/test_types.py`:

```python
from __future__ import annotations

from footprint.reconciler.types import (
    BucketedReport,
    MountInfo,
    RawRoute,
    ResolvedRoute,
    RouterDef,
)


def test_router_def_is_frozen() -> None:
    rd = RouterDef(file="src/auth.py", var_name="router", prefix="/auth", line=10)
    assert rd.file == "src/auth.py"
    assert rd.prefix == "/auth"


def test_raw_route_defaults() -> None:
    rr = RawRoute(
        file="src/auth.py",
        line=20,
        router_var="router",
        method="GET",
        decorator_path="/check",
        include_in_schema=True,
        kwargs={},
    )
    assert rr.method == "GET"
    assert rr.include_in_schema is True


def test_mount_info_fields() -> None:
    mi = MountInfo(
        init_file="app/main.py",
        target_file="src/auth.py",
        target_var="router",
        mount_prefix="/api/auth",
    )
    assert mi.target_file == "src/auth.py"


def test_resolved_route_default_coverage() -> None:
    rr = ResolvedRoute(
        file="src/auth.py",
        line=20,
        method="GET",
        full_path="/api/auth/check",
        decorator_path="/check",
        apirouter_prefix="",
        mount_prefix="/api/auth",
        include_in_schema=True,
    )
    assert rr.tested is False
    assert rr.test_files == []


def test_bucketed_report_construction() -> None:
    report = BucketedReport(mounted=[], hidden=[], unmounted=[], spec_only=[])
    assert report.mounted == []
    assert report.spec_only == []


def test_public_exports() -> None:
    from footprint.reconciler import BucketedReport as B
    from footprint.reconciler import ResolvedRoute as R

    assert B is BucketedReport
    assert R is ResolvedRoute
```

- [ ] **Step 4: Run test to verify it fails**

```bash
uv run pytest tests/reconciler/test_types.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'footprint.reconciler'`

- [ ] **Step 5: Create `footprint/reconciler/types.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RouterDef:
    """An ``APIRouter(prefix=...)`` definition found in a source file."""

    file: str
    var_name: str
    prefix: str
    line: int


@dataclass(frozen=True)
class RawRoute:
    """A ``@<var>.<method>("path", **kwargs)`` decorator on a function."""

    file: str
    line: int
    router_var: str
    method: str
    decorator_path: str
    include_in_schema: bool
    kwargs: dict[str, str]


@dataclass(frozen=True)
class MountInfo:
    """An ``app.include_router(target, prefix=...)`` call from the init file."""

    init_file: str
    target_file: str
    target_var: str
    mount_prefix: str


@dataclass
class ResolvedRoute:
    """A fully composed route, ready for bucketing and rendering."""

    file: str
    line: int
    method: str
    full_path: str
    decorator_path: str
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
    spec_only: list[tuple[str, str]]
```

- [ ] **Step 6: Create `footprint/reconciler/__init__.py`**

```python
from __future__ import annotations

from footprint.reconciler.types import (
    BucketedReport,
    MountInfo,
    RawRoute,
    ResolvedRoute,
    RouterDef,
)

__all__ = [
    "BucketedReport",
    "MountInfo",
    "RawRoute",
    "ResolvedRoute",
    "RouterDef",
]
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
uv run pytest tests/reconciler/test_types.py -v
```

Expected: 6 passed.

- [ ] **Step 8: Run full check suite**

```bash
mise run check
```

Expected: All passed (trivy, ruff, ruff format, mypy, pytest — should be green with the new module added).

- [ ] **Step 9: Commit**

```bash
git add footprint/reconciler/ tests/reconciler/
git commit -m "feat(reconciler): scaffold package and core dataclasses

Adds footprint/reconciler/ with the public dataclasses (RouterDef,
RawRoute, MountInfo, ResolvedRoute, BucketedReport) used by all
subsequent passes. No behavior yet — types only."
```

---

## Task 2: Pass 2 — AST source extraction (`extract.py`)

**Branch:** `feat/reconciler-extract` (parent: `feat/reconciler-types`)

**Files:**
- Create: `footprint/reconciler/extract.py`
- Create: `tests/reconciler/test_extract.py`

- [ ] **Step 1: Create the branch**

```bash
gt create feat/reconciler-extract
```

- [ ] **Step 2: Write the failing test**

Create `tests/reconciler/test_extract.py`:

```python
from __future__ import annotations

import textwrap
from pathlib import Path

from footprint.reconciler.extract import (
    extract_from_source,
    extract_from_tree,
    walk_source_tree,
)


def _parse(src: str) -> tuple[list, list]:
    return extract_from_source(textwrap.dedent(src), file="src/x.py")


def test_simple_apirouter_with_prefix() -> None:
    routers, _ = _parse(
        '''
        from fastapi import APIRouter
        router = APIRouter(prefix="/auth", tags=["Auth"])
        '''
    )
    assert len(routers) == 1
    assert routers[0].var_name == "router"
    assert routers[0].prefix == "/auth"
    assert routers[0].file == "src/x.py"


def test_apirouter_no_prefix_is_empty_string() -> None:
    routers, _ = _parse('router = APIRouter(tags=["X"])')
    assert len(routers) == 1
    assert routers[0].prefix == ""


def test_multiline_apirouter() -> None:
    routers, _ = _parse(
        '''
        router = APIRouter(
            prefix="/api/long/prefix",
            tags=["X"],
        )
        '''
    )
    assert len(routers) == 1
    assert routers[0].prefix == "/api/long/prefix"


def test_simple_route_decorator() -> None:
    _, routes = _parse(
        '''
        @router.get("/check")
        def check():
            ...
        '''
    )
    assert len(routes) == 1
    assert routes[0].router_var == "router"
    assert routes[0].method == "GET"
    assert routes[0].decorator_path == "/check"
    assert routes[0].include_in_schema is True


def test_async_function_decorator() -> None:
    _, routes = _parse(
        '''
        @router.post("/login")
        async def login():
            ...
        '''
    )
    assert len(routes) == 1
    assert routes[0].method == "POST"


def test_multiline_decorator() -> None:
    _, routes = _parse(
        '''
        @router.get(
            "/history",
            response_model=list[dict],
        )
        def history():
            ...
        '''
    )
    assert len(routes) == 1
    assert routes[0].decorator_path == "/history"


def test_include_in_schema_false_extracted() -> None:
    _, routes = _parse(
        '''
        @router.post("/secret", include_in_schema=False)
        def secret():
            ...
        '''
    )
    assert len(routes) == 1
    assert routes[0].include_in_schema is False


def test_multiple_decorators_on_one_function() -> None:
    _, routes = _parse(
        '''
        @router.get("/x")
        @router.post("/x")
        def both():
            ...
        '''
    )
    assert len(routes) == 2
    methods = {r.method for r in routes}
    assert methods == {"GET", "POST"}


def test_decorator_with_non_literal_path_skipped() -> None:
    _, routes = _parse(
        '''
        PATH = "/dyn"
        @router.get(PATH)
        def dyn():
            ...
        '''
    )
    assert routes == []


def test_underscore_router_var() -> None:
    routers, routes = _parse(
        '''
        _admin_router = APIRouter(prefix="/admin")
        @_admin_router.get("/users")
        def users():
            ...
        '''
    )
    assert routers[0].var_name == "_admin_router"
    assert routes[0].router_var == "_admin_router"


def test_extract_from_tree_aggregates_files(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text(
        'from fastapi import APIRouter\nrouter = APIRouter(prefix="/a")\n@router.get("/x")\ndef x(): ...\n'
    )
    (tmp_path / "b.py").write_text(
        'from fastapi import APIRouter\nrouter = APIRouter(prefix="/b")\n@router.get("/y")\ndef y(): ...\n'
    )
    files = [Path("a.py"), Path("b.py")]
    routers, routes = extract_from_tree(tmp_path, files)
    assert len(routers) == 2
    assert len(routes) == 2
    assert {r.file for r in routers} == {"a.py", "b.py"}


def test_walk_source_tree_excludes_tests(tmp_path: Path) -> None:
    (tmp_path / "src.py").write_text("# src")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_x.py").write_text("# test")
    (tmp_path / "test_top.py").write_text("# test top")
    (tmp_path / "y_test.py").write_text("# test y")

    found = sorted(walk_source_tree(tmp_path, exclude=[]))
    assert "src.py" in found
    assert "tests/test_x.py" not in found
    assert "test_top.py" not in found
    assert "y_test.py" not in found


def test_walk_source_tree_honors_exclude(tmp_path: Path) -> None:
    (tmp_path / "keep.py").write_text("")
    skip_dir = tmp_path / ".venv"
    skip_dir.mkdir()
    (skip_dir / "drop.py").write_text("")
    found = sorted(walk_source_tree(tmp_path, exclude=[".venv"]))
    assert "keep.py" in found
    assert ".venv/drop.py" not in found


def test_syntax_error_skipped(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def f(:\n")
    (tmp_path / "ok.py").write_text(
        'from fastapi import APIRouter\nrouter = APIRouter(prefix="/x")\n'
    )
    files = [Path("broken.py"), Path("ok.py")]
    routers, _ = extract_from_tree(tmp_path, files)
    assert len(routers) == 1
    assert routers[0].file == "ok.py"
```

- [ ] **Step 3: Run test to verify it fails**

```bash
uv run pytest tests/reconciler/test_extract.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'footprint.reconciler.extract'`

- [ ] **Step 4: Create `footprint/reconciler/extract.py`**

```python
from __future__ import annotations

import ast
import os
from fnmatch import fnmatch
from pathlib import Path

from footprint.reconciler.types import RawRoute, RouterDef

_HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete", "head", "options"})


def extract_from_source(source: str, file: str) -> tuple[list[RouterDef], list[RawRoute]]:
    """Parse a single source string and return its RouterDefs and RawRoutes.

    Returns ([], []) on syntax errors. ``file`` is the repo-relative path
    recorded on each emitted record.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [], []
    return _extract_from_tree(tree, file)


def extract_from_tree(
    repo_root: Path, files: list[Path]
) -> tuple[list[RouterDef], list[RawRoute]]:
    """Read each file under ``repo_root`` and aggregate extracted records."""
    all_routers: list[RouterDef] = []
    all_routes: list[RawRoute] = []
    for rel in files:
        path = repo_root / rel
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        routers, routes = extract_from_source(source, file=rel.as_posix())
        all_routers.extend(routers)
        all_routes.extend(routes)
    return all_routers, all_routes


def walk_source_tree(repo_root: Path, exclude: list[str]) -> list[str]:
    """Return repo-relative .py paths under ``repo_root`` minus tests + excludes."""
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        rel_dir = Path(dirpath).relative_to(repo_root)
        dirnames[:] = sorted(
            d for d in dirnames if not _excluded(rel_dir / d, exclude)
        )
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            rel = rel_dir / filename
            if _excluded(rel, exclude):
                continue
            if _is_test_path(rel):
                continue
            found.append(rel.as_posix())
    return found


def _excluded(rel: Path, patterns: list[str]) -> bool:
    rel_str = rel.as_posix()
    for pattern in patterns:
        for part in rel.parts:
            if fnmatch(part, pattern):
                return True
        if fnmatch(rel_str, pattern):
            return True
    return False


def _is_test_path(rel: Path) -> bool:
    parts = rel.parts
    if "tests" in parts:
        return True
    name = rel.name
    if name.startswith("test_") and name.endswith(".py"):
        return True
    if name.endswith("_test.py"):
        return True
    return False


def _extract_from_tree(
    tree: ast.AST, file: str
) -> tuple[list[RouterDef], list[RawRoute]]:
    routers: list[RouterDef] = []
    routes: list[RawRoute] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            rd = _try_router_def(node, file)
            if rd is not None:
                routers.append(rd)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                rr = _try_route(dec, file)
                if rr is not None:
                    routes.append(rr)
    return routers, routes


def _try_router_def(node: ast.Assign, file: str) -> RouterDef | None:
    if not isinstance(node.value, ast.Call):
        return None
    if not _call_attr_is(node.value.func, "APIRouter"):
        return None
    if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
        return None
    var_name = node.targets[0].id
    prefix = ""
    for kw in node.value.keywords:
        if kw.arg == "prefix" and isinstance(kw.value, ast.Constant) and isinstance(
            kw.value.value, str
        ):
            prefix = kw.value.value
            break
    return RouterDef(file=file, var_name=var_name, prefix=prefix, line=node.lineno)


def _try_route(dec: ast.expr, file: str) -> RawRoute | None:
    if not isinstance(dec, ast.Call):
        return None
    if not isinstance(dec.func, ast.Attribute):
        return None
    if not isinstance(dec.func.value, ast.Name):
        return None
    method_name = dec.func.attr
    if method_name.lower() not in _HTTP_METHODS:
        return None
    if not dec.args or not isinstance(dec.args[0], ast.Constant):
        return None
    if not isinstance(dec.args[0].value, str):
        return None

    router_var = dec.func.value.id
    method = method_name.upper()
    decorator_path = dec.args[0].value
    include_in_schema = True
    kwargs: dict[str, str] = {}
    for kw in dec.keywords:
        if kw.arg is None:
            continue
        if (
            kw.arg == "include_in_schema"
            and isinstance(kw.value, ast.Constant)
            and isinstance(kw.value.value, bool)
        ):
            include_in_schema = kw.value.value
            continue
        try:
            kwargs[kw.arg] = ast.unparse(kw.value)
        except Exception:  # noqa: BLE001
            kwargs[kw.arg] = "<unparseable>"
    return RawRoute(
        file=file,
        line=dec.lineno,
        router_var=router_var,
        method=method,
        decorator_path=decorator_path,
        include_in_schema=include_in_schema,
        kwargs=kwargs,
    )


def _call_attr_is(func: ast.expr, name: str) -> bool:
    if isinstance(func, ast.Name):
        return func.id == name
    if isinstance(func, ast.Attribute):
        return func.attr == name
    return False
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/reconciler/test_extract.py -v
```

Expected: 14 passed.

- [ ] **Step 6: Run full check suite**

```bash
mise run check
```

Expected: All passed.

- [ ] **Step 7: Commit**

```bash
git add footprint/reconciler/extract.py tests/reconciler/test_extract.py
git commit -m "feat(reconciler): AST source extraction (Pass 2)

Adds extract.py: walks Python source files via stdlib ast, returns
RouterDef per APIRouter(...) assignment and RawRoute per route decorator.
Handles multi-line APIRouter and multi-line decorators trivially.
Skips non-literal decorator paths and syntax-error files."
```

---

## Task 3: Pass 3 — Init-file mount extraction (`mounts.py`)

**Branch:** `feat/reconciler-mounts` (parent: `feat/reconciler-extract`)

**Files:**
- Create: `footprint/reconciler/mounts.py`
- Create: `tests/reconciler/test_mounts.py`

- [ ] **Step 1: Create the branch**

```bash
gt create feat/reconciler-mounts
```

- [ ] **Step 2: Write the failing test**

Create `tests/reconciler/test_mounts.py`:

```python
from __future__ import annotations

import textwrap
from pathlib import Path

from footprint.reconciler.mounts import (
    auto_discover_init,
    build_mount_map,
    extract_mounts_from_source,
)


def _src(s: str) -> str:
    return textwrap.dedent(s)


def test_simple_aliased_import_and_include() -> None:
    src = _src(
        '''
        from app.routes.auth import router as auth_router
        app.include_router(auth_router, prefix="/api/auth")
        '''
    )
    mounts = extract_mounts_from_source(src, init_file="app/main.py")
    assert len(mounts) == 1
    m = mounts[0]
    assert m.target_file == "app/routes/auth.py"
    assert m.target_var == "router"
    assert m.mount_prefix == "/api/auth"


def test_import_without_alias() -> None:
    src = _src(
        '''
        from app.routes.health import router
        app.include_router(router)
        '''
    )
    mounts = extract_mounts_from_source(src, init_file="app/main.py")
    assert len(mounts) == 1
    assert mounts[0].target_file == "app/routes/health.py"
    assert mounts[0].target_var == "router"
    assert mounts[0].mount_prefix == ""


def test_multiple_mounts() -> None:
    src = _src(
        '''
        from app.routes.auth import router as auth_router
        from app.routes.users import router as users_router
        app.include_router(auth_router, prefix="/api/auth")
        app.include_router(users_router, prefix="/api/users")
        '''
    )
    mounts = extract_mounts_from_source(src, init_file="app/main.py")
    assert len(mounts) == 2
    by_target = {m.target_file: m.mount_prefix for m in mounts}
    assert by_target["app/routes/auth.py"] == "/api/auth"
    assert by_target["app/routes/users.py"] == "/api/users"


def test_unknown_var_skipped() -> None:
    src = _src(
        '''
        app.include_router(some_router_not_imported, prefix="/api/x")
        '''
    )
    assert extract_mounts_from_source(src, init_file="app/main.py") == []


def test_dotted_module_path() -> None:
    src = _src(
        '''
        from app.v1.endpoints.health import router as health_router
        app.include_router(health_router)
        '''
    )
    mounts = extract_mounts_from_source(src, init_file="app/main.py")
    assert mounts[0].target_file == "app/v1/endpoints/health.py"


def test_unparseable_source_returns_empty() -> None:
    assert extract_mounts_from_source("def f(:\n", init_file="app/main.py") == []


def test_build_mount_map() -> None:
    src = _src(
        '''
        from app.routes.auth import router as auth_router
        app.include_router(auth_router, prefix="/api/auth")
        '''
    )
    mounts = extract_mounts_from_source(src, init_file="app/main.py")
    mm = build_mount_map(mounts)
    assert mm[("app/routes/auth.py", "router")] == "/api/auth"


def test_auto_discover_finds_initialize(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    init = tmp_path / "app" / "initialize.py"
    init.write_text("# init")
    found = auto_discover_init(tmp_path)
    assert found is not None
    assert found.name == "initialize.py"


def test_auto_discover_prefers_initialize_over_main(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "initialize.py").write_text("# init")
    (tmp_path / "app" / "main.py").write_text("# main")
    found = auto_discover_init(tmp_path)
    assert found is not None
    assert found.name == "initialize.py"


def test_auto_discover_falls_back_to_main_py(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("# main")
    found = auto_discover_init(tmp_path)
    assert found is not None
    assert found.name == "main.py"


def test_auto_discover_returns_none_when_nothing_found(tmp_path: Path) -> None:
    assert auto_discover_init(tmp_path) is None
```

- [ ] **Step 3: Run test to verify it fails**

```bash
uv run pytest tests/reconciler/test_mounts.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'footprint.reconciler.mounts'`

- [ ] **Step 4: Create `footprint/reconciler/mounts.py`**

```python
from __future__ import annotations

import ast
from pathlib import Path

from footprint.reconciler.types import MountInfo

_AUTO_DISCOVER_PATHS: tuple[str, ...] = (
    "app/initialize.py",
    "app/main.py",
    "main.py",
    "src/main.py",
    "app.py",
)


def extract_mounts_from_source(source: str, init_file: str) -> list[MountInfo]:
    """Parse an app init source string; return one MountInfo per resolvable
    ``app.include_router(target, prefix=...)`` call.

    Imports inside the file are followed: ``from a.b.c import router as x``
    + ``app.include_router(x, prefix="/api")`` → MountInfo with
    target_file="a/b/c.py", target_var="router", mount_prefix="/api".
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    alias_map: dict[str, tuple[str, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            target_file = node.module.replace(".", "/") + ".py"
            for alias in node.names:
                local_name = alias.asname or alias.name
                alias_map[local_name] = (target_file, alias.name)

    mounts: list[MountInfo] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "include_router":
            continue
        if not node.args or not isinstance(node.args[0], ast.Name):
            continue
        local_name = node.args[0].id
        if local_name not in alias_map:
            continue
        target_file, target_var = alias_map[local_name]
        prefix = ""
        for kw in node.keywords:
            if (
                kw.arg == "prefix"
                and isinstance(kw.value, ast.Constant)
                and isinstance(kw.value.value, str)
            ):
                prefix = kw.value.value
                break
        mounts.append(
            MountInfo(
                init_file=init_file,
                target_file=target_file,
                target_var=target_var,
                mount_prefix=prefix,
            )
        )
    return mounts


def build_mount_map(mounts: list[MountInfo]) -> dict[tuple[str, str], str]:
    """Index mounts by (target_file, target_var) for O(1) lookup during bucketing."""
    return {(m.target_file, m.target_var): m.mount_prefix for m in mounts}


def auto_discover_init(repo_root: Path) -> Path | None:
    """Probe for a likely app init file under standard paths. First hit wins."""
    for candidate in _AUTO_DISCOVER_PATHS:
        path = repo_root / candidate
        if path.is_file():
            return path
    return None
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/reconciler/test_mounts.py -v
```

Expected: 11 passed.

- [ ] **Step 6: Run full check suite**

```bash
mise run check
```

Expected: All passed.

- [ ] **Step 7: Commit**

```bash
git add footprint/reconciler/mounts.py tests/reconciler/test_mounts.py
git commit -m "feat(reconciler): init-file mount extraction (Pass 3)

Adds mounts.py: AST-walks an app init file to build a {(target_file,
target_var) → mount_prefix} map by resolving import aliases against
include_router(...) calls. Includes auto-discover for standard init
file locations (app/initialize.py, app/main.py, main.py, etc.)."
```

---

## Task 4: Pass 4 — Bucketing + path composition (`bucket.py`)

**Branch:** `feat/reconciler-bucket` (parent: `feat/reconciler-mounts`)

**Files:**
- Create: `footprint/reconciler/bucket.py`
- Create: `tests/reconciler/test_bucket.py`

- [ ] **Step 1: Create the branch**

```bash
gt create feat/reconciler-bucket
```

- [ ] **Step 2: Write the failing test**

Create `tests/reconciler/test_bucket.py`:

```python
from __future__ import annotations

from footprint.reconciler.bucket import bucket_routes, compose_path
from footprint.reconciler.types import RawRoute, RouterDef


def _route(
    file: str = "src/auth.py",
    method: str = "GET",
    var: str = "router",
    decorator_path: str = "/check",
    include_in_schema: bool = True,
) -> RawRoute:
    return RawRoute(
        file=file,
        line=10,
        router_var=var,
        method=method,
        decorator_path=decorator_path,
        include_in_schema=include_in_schema,
        kwargs={},
    )


def _router_def(
    file: str = "src/auth.py", var: str = "router", prefix: str = "/auth"
) -> RouterDef:
    return RouterDef(file=file, var_name=var, prefix=prefix, line=1)


# --- compose_path ---


def test_compose_all_three_components() -> None:
    assert compose_path(mount="/api", apirouter="/auth", decorator="/check") == "/api/auth/check"


def test_compose_strips_trailing_slashes() -> None:
    assert compose_path(mount="/api/", apirouter="/auth/", decorator="/check") == "/api/auth/check"


def test_compose_empty_apirouter() -> None:
    assert compose_path(mount="/api", apirouter="", decorator="/health") == "/api/health"


def test_compose_empty_mount() -> None:
    assert compose_path(mount="", apirouter="/auth", decorator="/check") == "/auth/check"


def test_compose_all_empty_returns_root() -> None:
    assert compose_path(mount="", apirouter="", decorator="") == "/"


def test_compose_decorator_empty_string_uses_prefixes() -> None:
    assert compose_path(mount="/api", apirouter="/auth", decorator="") == "/api/auth"


# --- bucket_routes ---


def test_mounted_route_lands_in_mounted() -> None:
    routes = [_route()]
    routers = [_router_def()]
    mounts = {("src/auth.py", "router"): "/api"}
    inventory = frozenset({("GET", "/api/auth/check")})
    report = bucket_routes(routes, routers, mounts, inventory)
    assert len(report.mounted) == 1
    assert report.mounted[0].full_path == "/api/auth/check"
    assert report.unmounted == []
    assert report.hidden == []


def test_unmounted_when_not_in_inventory() -> None:
    routes = [_route(decorator_path="/dead")]
    routers = [_router_def()]
    mounts = {("src/auth.py", "router"): "/api"}
    inventory: frozenset[tuple[str, str]] = frozenset({("GET", "/api/auth/check")})
    report = bucket_routes(routes, routers, mounts, inventory)
    assert len(report.unmounted) == 1
    assert report.unmounted[0].full_path == "/api/auth/dead"


def test_hidden_when_include_in_schema_false() -> None:
    routes = [_route(include_in_schema=False, decorator_path="/secret")]
    routers = [_router_def()]
    mounts = {("src/auth.py", "router"): "/api"}
    inventory = frozenset({("GET", "/api/auth/secret")})  # even if in inventory
    report = bucket_routes(routes, routers, mounts, inventory)
    assert len(report.hidden) == 1
    assert report.mounted == []
    assert report.hidden[0].include_in_schema is False


def test_unmounted_with_no_mount_resolves_apirouter_only() -> None:
    routes = [_route(decorator_path="/foo")]
    routers = [_router_def(prefix="/orphan")]
    mounts: dict[tuple[str, str], str] = {}
    inventory: frozenset[tuple[str, str]] = frozenset()
    report = bucket_routes(routes, routers, mounts, inventory)
    assert len(report.unmounted) == 1
    assert report.unmounted[0].full_path == "/orphan/foo"
    assert report.unmounted[0].mount_prefix == ""


def test_no_router_def_uses_empty_apirouter_prefix() -> None:
    routes = [_route(var="ghost", decorator_path="/x")]
    routers: list[RouterDef] = []
    mounts: dict[tuple[str, str], str] = {("src/auth.py", "ghost"): "/api"}
    inventory: frozenset[tuple[str, str]] = frozenset({("GET", "/api/x")})
    report = bucket_routes(routes, routers, mounts, inventory)
    assert len(report.mounted) == 1
    assert report.mounted[0].apirouter_prefix == ""
    assert report.mounted[0].full_path == "/api/x"


def test_spec_only_sweep() -> None:
    routes = [_route(decorator_path="/check")]
    routers = [_router_def()]
    mounts = {("src/auth.py", "router"): "/api"}
    inventory = frozenset(
        {("GET", "/api/auth/check"), ("POST", "/api/legacy/refresh")}
    )
    report = bucket_routes(routes, routers, mounts, inventory)
    assert report.spec_only == [("POST", "/api/legacy/refresh")]


def test_trailing_slash_normalized_for_inventory_match() -> None:
    routes = [_route(decorator_path="/check/")]
    routers = [_router_def(prefix="/auth/")]
    mounts = {("src/auth.py", "router"): "/api/"}
    inventory = frozenset({("GET", "/api/auth/check")})
    report = bucket_routes(routes, routers, mounts, inventory)
    assert len(report.mounted) == 1


def test_multiple_routes_independent_buckets() -> None:
    routes = [
        _route(decorator_path="/a"),
        _route(decorator_path="/b"),
        _route(decorator_path="/c", include_in_schema=False),
    ]
    routers = [_router_def()]
    mounts = {("src/auth.py", "router"): "/api"}
    inventory = frozenset({("GET", "/api/auth/a")})
    report = bucket_routes(routes, routers, mounts, inventory)
    assert len(report.mounted) == 1  # /a
    assert len(report.unmounted) == 1  # /b
    assert len(report.hidden) == 1  # /c
```

- [ ] **Step 3: Run test to verify it fails**

```bash
uv run pytest tests/reconciler/test_bucket.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'footprint.reconciler.bucket'`

- [ ] **Step 4: Create `footprint/reconciler/bucket.py`**

```python
from __future__ import annotations

from footprint.reconciler.types import (
    BucketedReport,
    RawRoute,
    ResolvedRoute,
    RouterDef,
)


def compose_path(mount: str, apirouter: str, decorator: str) -> str:
    """Concatenate the three prefix components into a full path.

    Strips trailing slashes from each component before joining. Returns
    "/" if the result would be the empty string.
    """
    parts = [p.rstrip("/") for p in (mount, apirouter, decorator)]
    joined = "".join(parts)
    return joined if joined else "/"


def _normalize(path: str) -> str:
    stripped = path.rstrip("/")
    return stripped if stripped else "/"


def bucket_routes(
    routes: list[RawRoute],
    routers: list[RouterDef],
    mounts: dict[tuple[str, str], str],
    inventory: frozenset[tuple[str, str]],
) -> BucketedReport:
    """Bucket every RawRoute into mounted/hidden/unmounted; sweep inventory for spec_only."""
    router_index: dict[tuple[str, str], str] = {
        (r.file, r.var_name): r.prefix for r in routers
    }

    mounted: list[ResolvedRoute] = []
    hidden: list[ResolvedRoute] = []
    unmounted: list[ResolvedRoute] = []
    claimed: set[tuple[str, str]] = set()

    for route in routes:
        apirouter_prefix = router_index.get((route.file, route.router_var), "")
        mount_prefix = mounts.get((route.file, route.router_var), "")
        full_path = compose_path(
            mount=mount_prefix, apirouter=apirouter_prefix, decorator=route.decorator_path
        )
        resolved = ResolvedRoute(
            file=route.file,
            line=route.line,
            method=route.method,
            full_path=full_path,
            decorator_path=route.decorator_path,
            apirouter_prefix=apirouter_prefix,
            mount_prefix=mount_prefix,
            include_in_schema=route.include_in_schema,
        )
        if not route.include_in_schema:
            hidden.append(resolved)
            continue
        normalized_inventory = frozenset(
            (m, _normalize(p)) for (m, p) in inventory
        )
        if (route.method, _normalize(full_path)) in normalized_inventory:
            mounted.append(resolved)
            claimed.add((route.method, _normalize(full_path)))
        else:
            unmounted.append(resolved)

    spec_only: list[tuple[str, str]] = []
    for method, path in inventory:
        if (method, _normalize(path)) not in claimed:
            spec_only.append((method, path))

    return BucketedReport(
        mounted=mounted, hidden=hidden, unmounted=unmounted, spec_only=spec_only
    )
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/reconciler/test_bucket.py -v
```

Expected: 14 passed.

- [ ] **Step 6: Run full check suite**

```bash
mise run check
```

Expected: All passed.

- [ ] **Step 7: Commit**

```bash
git add footprint/reconciler/bucket.py tests/reconciler/test_bucket.py
git commit -m "feat(reconciler): bucket + path composition (Pass 4)

Adds bucket.py: composes mount + APIRouter + decorator paths and assigns
each route to mounted/hidden/unmounted; sweeps inventory entries no
mounted route claimed into spec_only. Trailing-slash normalization on
both sides of the inventory match."
```

---

## Task 5: Pass 5 — Per-route test coverage (`coverage.py`)

**Branch:** `feat/reconciler-coverage` (parent: `feat/reconciler-bucket`)

**Files:**
- Create: `footprint/reconciler/coverage.py`
- Create: `tests/reconciler/test_coverage.py`

- [ ] **Step 1: Create the branch**

```bash
gt create feat/reconciler-coverage
```

- [ ] **Step 2: Write the failing test**

Create `tests/reconciler/test_coverage.py`:

```python
from __future__ import annotations

from pathlib import Path

from footprint.reconciler.coverage import (
    annotate_coverage,
    extract_test_calls,
    walk_test_tree,
)
from footprint.reconciler.types import BucketedReport, ResolvedRoute


def _resolved(method: str, path: str) -> ResolvedRoute:
    return ResolvedRoute(
        file="src/x.py",
        line=1,
        method=method,
        full_path=path,
        decorator_path=path,
        apirouter_prefix="",
        mount_prefix="",
        include_in_schema=True,
    )


# --- extract_test_calls ---


def test_extract_simple_get_call() -> None:
    calls = extract_test_calls('client.get("/api/auth/check")')
    assert ("GET", "/api/auth/check") in calls


def test_extract_post_call() -> None:
    calls = extract_test_calls('client.post("/api/auth/login", json={})')
    assert ("POST", "/api/auth/login") in calls


def test_extract_multiple_methods_in_one_file() -> None:
    src = '\n'.join([
        'client.get("/a")',
        'client.post("/b")',
        'client.delete("/c")',
    ])
    calls = extract_test_calls(src)
    assert ("GET", "/a") in calls
    assert ("POST", "/b") in calls
    assert ("DELETE", "/c") in calls


def test_single_quoted_string() -> None:
    calls = extract_test_calls("client.get('/api/x')")
    assert ("GET", "/api/x") in calls


def test_method_uppercased() -> None:
    calls = extract_test_calls('client.GET("/x")')
    assert ("GET", "/x") in calls


def test_no_match_returns_empty() -> None:
    calls = extract_test_calls("# nothing here")
    assert calls == []


def test_non_http_method_attr_ignored() -> None:
    calls = extract_test_calls('config.read("/etc/config")')
    assert calls == []


# --- annotate_coverage ---


def test_annotate_marks_tested(tmp_path: Path) -> None:
    test_file = tmp_path / "test_x.py"
    test_file.write_text('client.get("/api/auth/check")')
    report = BucketedReport(
        mounted=[_resolved("GET", "/api/auth/check")],
        hidden=[],
        unmounted=[],
        spec_only=[],
    )
    annotate_coverage(report, tmp_path, [test_file.relative_to(tmp_path).as_posix()])
    assert report.mounted[0].tested is True
    assert "test_x.py" in report.mounted[0].test_files


def test_annotate_unmatched_stays_false(tmp_path: Path) -> None:
    test_file = tmp_path / "test_x.py"
    test_file.write_text('client.get("/different/path")')
    report = BucketedReport(
        mounted=[_resolved("GET", "/api/auth/check")],
        hidden=[],
        unmounted=[],
        spec_only=[],
    )
    annotate_coverage(report, tmp_path, [test_file.relative_to(tmp_path).as_posix()])
    assert report.mounted[0].tested is False
    assert report.mounted[0].test_files == []


def test_annotate_handles_hidden_and_unmounted(tmp_path: Path) -> None:
    test_file = tmp_path / "test_x.py"
    test_file.write_text(
        'client.get("/api/secret")\nclient.get("/api/dead")\n'
    )
    report = BucketedReport(
        mounted=[],
        hidden=[_resolved("GET", "/api/secret")],
        unmounted=[_resolved("GET", "/api/dead")],
        spec_only=[],
    )
    annotate_coverage(report, tmp_path, [test_file.relative_to(tmp_path).as_posix()])
    assert report.hidden[0].tested is True
    assert report.unmounted[0].tested is True


def test_annotate_multiple_test_files_aggregated(tmp_path: Path) -> None:
    (tmp_path / "test_a.py").write_text('client.get("/x")')
    (tmp_path / "test_b.py").write_text('client.get("/x")')
    report = BucketedReport(
        mounted=[_resolved("GET", "/x")],
        hidden=[],
        unmounted=[],
        spec_only=[],
    )
    annotate_coverage(report, tmp_path, ["test_a.py", "test_b.py"])
    assert sorted(report.mounted[0].test_files) == ["test_a.py", "test_b.py"]


# --- walk_test_tree ---


def test_walk_finds_test_directory_files(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_a.py").write_text("")
    (tests_dir / "helpers.py").write_text("")
    (tmp_path / "src.py").write_text("")
    found = sorted(walk_test_tree(tmp_path, exclude=[]))
    assert "tests/test_a.py" in found
    assert "tests/helpers.py" in found
    assert "src.py" not in found


def test_walk_finds_top_level_test_prefixed_files(tmp_path: Path) -> None:
    (tmp_path / "test_top.py").write_text("")
    (tmp_path / "y_test.py").write_text("")
    (tmp_path / "main.py").write_text("")
    found = sorted(walk_test_tree(tmp_path, exclude=[]))
    assert "test_top.py" in found
    assert "y_test.py" in found
    assert "main.py" not in found


def test_walk_honors_exclude(tmp_path: Path) -> None:
    skip = tmp_path / ".venv"
    skip.mkdir()
    tests = skip / "tests"
    tests.mkdir()
    (tests / "test_x.py").write_text("")
    found = walk_test_tree(tmp_path, exclude=[".venv"])
    assert ".venv/tests/test_x.py" not in found
```

- [ ] **Step 3: Run test to verify it fails**

```bash
uv run pytest tests/reconciler/test_coverage.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'footprint.reconciler.coverage'`

- [ ] **Step 4: Create `footprint/reconciler/coverage.py`**

```python
from __future__ import annotations

import os
import re
from fnmatch import fnmatch
from pathlib import Path

from footprint.reconciler.types import BucketedReport, ResolvedRoute

_CALL_RE = re.compile(
    r"\.(get|post|put|patch|delete|head|options)\s*\(\s*[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)


def extract_test_calls(source: str) -> list[tuple[str, str]]:
    """Return ``(METHOD, path)`` pairs for each ``client.METHOD("path")`` style call."""
    calls: list[tuple[str, str]] = []
    for match in _CALL_RE.finditer(source):
        calls.append((match.group(1).upper(), match.group(2)))
    return calls


def annotate_coverage(
    report: BucketedReport, repo_root: Path, test_files: list[str]
) -> None:
    """Set ``tested`` and ``test_files`` on every ResolvedRoute that matches a test call."""
    references: dict[tuple[str, str], list[str]] = {}
    for rel in test_files:
        path = repo_root / rel
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for method, route_path in extract_test_calls(source):
            references.setdefault((method, route_path), []).append(rel)

    for bucket in (report.mounted, report.hidden, report.unmounted):
        for route in bucket:
            files = references.get((route.method, route.full_path))
            if files:
                _mark(route, files)


def _mark(route: ResolvedRoute, files: list[str]) -> None:
    route.tested = True
    seen: set[str] = set()
    for f in files:
        if f not in seen:
            route.test_files.append(f)
            seen.add(f)


def walk_test_tree(repo_root: Path, exclude: list[str]) -> list[str]:
    """Return repo-relative .py paths matching the test heuristic."""
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        rel_dir = Path(dirpath).relative_to(repo_root)
        dirnames[:] = sorted(
            d for d in dirnames if not _excluded(rel_dir / d, exclude)
        )
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            rel = rel_dir / filename
            if _excluded(rel, exclude):
                continue
            if _is_test_path(rel):
                found.append(rel.as_posix())
    return found


def _excluded(rel: Path, patterns: list[str]) -> bool:
    rel_str = rel.as_posix()
    for pattern in patterns:
        for part in rel.parts:
            if fnmatch(part, pattern):
                return True
        if fnmatch(rel_str, pattern):
            return True
    return False


def _is_test_path(rel: Path) -> bool:
    if "tests" in rel.parts:
        return True
    name = rel.name
    if name.startswith("test_") and name.endswith(".py"):
        return True
    if name.endswith("_test.py"):
        return True
    return False
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/reconciler/test_coverage.py -v
```

Expected: 13 passed.

- [ ] **Step 6: Run full check suite**

```bash
mise run check
```

Expected: All passed.

- [ ] **Step 7: Commit**

```bash
git add footprint/reconciler/coverage.py tests/reconciler/test_coverage.py
git commit -m "feat(reconciler): per-route test coverage (Pass 5)

Adds coverage.py: regex-extracts client.METHOD(\"path\") references from
test files and intersects them with the bucketed route set. Each route
in mounted/hidden/unmounted gets tested: bool and test_files: list[str].
Test heuristic matches tests/, test_*.py, and *_test.py."
```

---

## Task 6: Pass 6 — Render JSON + Markdown (`render.py`)

**Branch:** `feat/reconciler-render` (parent: `feat/reconciler-coverage`)

**Files:**
- Create: `footprint/reconciler/render.py`
- Create: `tests/reconciler/test_render.py`

- [ ] **Step 1: Create the branch**

```bash
gt create feat/reconciler-render
```

- [ ] **Step 2: Write the failing test**

Create `tests/reconciler/test_render.py`:

```python
from __future__ import annotations

import json

from footprint.reconciler.render import render_json, render_markdown
from footprint.reconciler.types import BucketedReport, ResolvedRoute


def _resolved(
    method: str = "GET",
    path: str = "/api/auth/check",
    file: str = "src/auth.py",
    line: int = 47,
    apirouter: str = "/auth",
    mount: str = "/api",
    decorator: str = "/check",
    in_schema: bool = True,
    tested: bool = False,
    test_files: list[str] | None = None,
) -> ResolvedRoute:
    return ResolvedRoute(
        file=file,
        line=line,
        method=method,
        full_path=path,
        decorator_path=decorator,
        apirouter_prefix=apirouter,
        mount_prefix=mount,
        include_in_schema=in_schema,
        tested=tested,
        test_files=list(test_files) if test_files else [],
    )


def _summary_kwargs() -> dict[str, str]:
    return {
        "repo": "/abs/repo",
        "openapi": "/abs/inv.json",
        "app_init": "/abs/main.py",
        "scanned_at": "2026-05-05T18:00:00Z",
    }


# --- render_json ---


def test_json_summary_counts() -> None:
    report = BucketedReport(
        mounted=[_resolved(tested=True), _resolved(path="/x")],
        hidden=[_resolved(path="/secret", in_schema=False)],
        unmounted=[_resolved(path="/dead")],
        spec_only=[("POST", "/legacy")],
    )
    out = json.loads(render_json(report, **_summary_kwargs()))
    assert out["summary"]["counts"] == {
        "mounted": 2,
        "hidden": 1,
        "unmounted": 1,
        "spec_only": 1,
        "tested": 1,
        "untested": 3,
    }


def test_json_mounted_entry_omits_include_in_schema() -> None:
    report = BucketedReport(
        mounted=[_resolved(tested=True, test_files=["tests/test_a.py"])],
        hidden=[],
        unmounted=[],
        spec_only=[],
    )
    out = json.loads(render_json(report, **_summary_kwargs()))
    entry = out["endpoints"]["mounted"][0]
    assert "include_in_schema" not in entry
    assert entry["method"] == "GET"
    assert entry["path"] == "/api/auth/check"
    assert entry["tested"] is True
    assert entry["test_files"] == ["tests/test_a.py"]


def test_json_hidden_entry_includes_include_in_schema_false() -> None:
    report = BucketedReport(
        mounted=[],
        hidden=[_resolved(path="/secret", in_schema=False)],
        unmounted=[],
        spec_only=[],
    )
    out = json.loads(render_json(report, **_summary_kwargs()))
    entry = out["endpoints"]["hidden"][0]
    assert entry["include_in_schema"] is False


def test_json_spec_only_format() -> None:
    report = BucketedReport(
        mounted=[],
        hidden=[],
        unmounted=[],
        spec_only=[("POST", "/api/legacy/refresh")],
    )
    out = json.loads(render_json(report, **_summary_kwargs()))
    assert out["endpoints"]["spec_only"] == [
        {"method": "POST", "path": "/api/legacy/refresh"}
    ]


def test_json_summary_metadata() -> None:
    report = BucketedReport(mounted=[], hidden=[], unmounted=[], spec_only=[])
    out = json.loads(render_json(report, **_summary_kwargs()))
    assert out["summary"]["repo"] == "/abs/repo"
    assert out["summary"]["openapi"] == "/abs/inv.json"
    assert out["summary"]["app_init"] == "/abs/main.py"
    assert out["summary"]["scanned_at"] == "2026-05-05T18:00:00Z"


# --- render_markdown ---


def test_markdown_has_sections_for_non_empty_buckets() -> None:
    report = BucketedReport(
        mounted=[_resolved()],
        hidden=[],
        unmounted=[_resolved(path="/dead")],
        spec_only=[],
    )
    md = render_markdown(report, **_summary_kwargs())
    assert "## Mounted (1)" in md
    assert "## Unmounted (1)" in md
    assert "## Hidden" not in md  # empty bucket, no section
    assert "## Spec-only (0)" in md  # always shown


def test_markdown_spec_only_always_renders() -> None:
    report = BucketedReport(mounted=[], hidden=[], unmounted=[], spec_only=[])
    md = render_markdown(report, **_summary_kwargs())
    assert "## Spec-only (0)" in md
    assert "No spec routes are missing from code" in md


def test_markdown_mounted_table_row() -> None:
    report = BucketedReport(
        mounted=[_resolved(tested=True)], hidden=[], unmounted=[], spec_only=[]
    )
    md = render_markdown(report, **_summary_kwargs())
    assert "GET" in md
    assert "/api/auth/check" in md
    assert "src/auth.py" in md
    assert "47" in md
    assert "✓" in md


def test_markdown_unmounted_includes_mount_resolved_column() -> None:
    report = BucketedReport(
        mounted=[],
        hidden=[],
        unmounted=[_resolved(path="/dead", mount="")],
        spec_only=[],
    )
    md = render_markdown(report, **_summary_kwargs())
    assert "## Unmounted (1)" in md
    assert "Mount resolved" in md
    assert "no" in md.lower()


def test_markdown_summary_table() -> None:
    report = BucketedReport(
        mounted=[_resolved(tested=True), _resolved(path="/x")],
        hidden=[_resolved(path="/secret", in_schema=False)],
        unmounted=[],
        spec_only=[],
    )
    md = render_markdown(report, **_summary_kwargs())
    assert "## Summary" in md
    assert "| Mounted   | 2 | 1 |" in md
    assert "| Hidden    | 1 | 0 |" in md
```

- [ ] **Step 3: Run test to verify it fails**

```bash
uv run pytest tests/reconciler/test_render.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'footprint.reconciler.render'`

- [ ] **Step 4: Create `footprint/reconciler/render.py`**

```python
from __future__ import annotations

import json

from footprint.reconciler.types import BucketedReport, ResolvedRoute


def render_json(
    report: BucketedReport,
    *,
    repo: str,
    openapi: str,
    app_init: str,
    scanned_at: str,
) -> str:
    """Serialize the bucketed report as JSON."""
    tested = sum(
        1
        for bucket in (report.mounted, report.hidden, report.unmounted)
        for r in bucket
        if r.tested
    )
    total = len(report.mounted) + len(report.hidden) + len(report.unmounted)
    untested = total - tested

    return json.dumps(
        {
            "summary": {
                "repo": repo,
                "openapi": openapi,
                "app_init": app_init,
                "scanned_at": scanned_at,
                "counts": {
                    "mounted": len(report.mounted),
                    "hidden": len(report.hidden),
                    "unmounted": len(report.unmounted),
                    "spec_only": len(report.spec_only),
                    "tested": tested,
                    "untested": untested,
                },
            },
            "endpoints": {
                "mounted": [_route_dict(r, include_schema_field=False) for r in report.mounted],
                "hidden": [_route_dict(r, include_schema_field=True) for r in report.hidden],
                "unmounted": [_route_dict(r, include_schema_field=False) for r in report.unmounted],
                "spec_only": [{"method": m, "path": p} for (m, p) in report.spec_only],
            },
        },
        indent=2,
    )


def _route_dict(route: ResolvedRoute, *, include_schema_field: bool) -> dict[str, object]:
    entry: dict[str, object] = {
        "method": route.method,
        "path": route.full_path,
        "file": route.file,
        "line": route.line,
        "decorator_path": route.decorator_path,
        "apirouter_prefix": route.apirouter_prefix,
        "mount_prefix": route.mount_prefix,
        "tested": route.tested,
        "test_files": list(route.test_files),
    }
    if include_schema_field:
        entry["include_in_schema"] = route.include_in_schema
    return entry


def render_markdown(
    report: BucketedReport,
    *,
    repo: str,
    openapi: str,
    app_init: str,
    scanned_at: str,
) -> str:
    """Render the bucketed report as a single Markdown document."""
    lines: list[str] = ["# Network Reconciliation Report", ""]
    lines.append(f"Scanned: `{repo}`")
    lines.append(f"OpenAPI: `{openapi}`")
    if app_init:
        lines.append(f"App init: `{app_init}`")
    lines.append(f"Generated: {scanned_at}")
    lines.append("")
    lines.extend(_summary_section(report))

    if report.mounted:
        lines.extend(_mounted_section(report.mounted))
    if report.hidden:
        lines.extend(_hidden_section(report.hidden))
    if report.unmounted:
        lines.extend(_unmounted_section(report.unmounted))
    lines.extend(_spec_only_section(report.spec_only))

    return "\n".join(lines)


def _summary_section(report: BucketedReport) -> list[str]:
    mounted_tested = sum(1 for r in report.mounted if r.tested)
    hidden_tested = sum(1 for r in report.hidden if r.tested)
    lines = [
        "## Summary",
        "",
        "| Bucket    | Count | Tested |",
        "|-----------|-------|--------|",
        f"| Mounted   | {len(report.mounted)} | {mounted_tested} |",
        f"| Hidden    | {len(report.hidden)} | {hidden_tested} |",
        f"| Unmounted | {len(report.unmounted)} | — |",
        f"| Spec-only | {len(report.spec_only)} | — |",
        "",
    ]
    return lines


def _mounted_section(routes: list[ResolvedRoute]) -> list[str]:
    lines = [
        f"## Mounted ({len(routes)})",
        "",
        "| Method | Path | File | Line | Tested |",
        "|--------|------|------|------|--------|",
    ]
    for r in routes:
        check = "✓" if r.tested else ""
        lines.append(f"| {r.method} | {r.full_path} | {r.file} | {r.line} | {check} |")
    lines.append("")
    return lines


def _hidden_section(routes: list[ResolvedRoute]) -> list[str]:
    lines = [
        f"## Hidden ({len(routes)})",
        "",
        "| Method | Path | File | Line |",
        "|--------|------|------|------|",
    ]
    for r in routes:
        lines.append(f"| {r.method} | {r.full_path} | {r.file} | {r.line} |")
    lines.append("")
    return lines


def _unmounted_section(routes: list[ResolvedRoute]) -> list[str]:
    lines = [
        f"## Unmounted ({len(routes)})",
        "",
        "| Method | Path | File | Line | Mount resolved |",
        "|--------|------|------|------|----------------|",
    ]
    for r in routes:
        resolved = "yes" if r.mount_prefix else "no"
        lines.append(
            f"| {r.method} | {r.full_path} | {r.file} | {r.line} | {resolved} |"
        )
    lines.append("")
    return lines


def _spec_only_section(entries: list[tuple[str, str]]) -> list[str]:
    lines = [f"## Spec-only ({len(entries)})", ""]
    if not entries:
        lines.append("*No spec routes are missing from code. ✓*")
        lines.append("")
        return lines
    lines.extend(
        [
            "| Method | Path |",
            "|--------|------|",
        ]
    )
    for method, path in entries:
        lines.append(f"| {method} | {path} |")
    lines.append("")
    return lines
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/reconciler/test_render.py -v
```

Expected: 9 passed.

- [ ] **Step 6: Run full check suite**

```bash
mise run check
```

Expected: All passed.

- [ ] **Step 7: Commit**

```bash
git add footprint/reconciler/render.py tests/reconciler/test_render.py
git commit -m "feat(reconciler): JSON + Markdown rendering (Pass 6)

Adds render.py: emits the canonical JSON shape (summary block + four
endpoint buckets) and a single-document Markdown report with one
section per non-empty bucket plus an always-rendered spec_only section
for the sanity check."
```

---

## Task 7: Pipeline orchestration + e2e fixture

**Branch:** `feat/reconciler-pipeline` (parent: `feat/reconciler-render`)

**Files:**
- Create: `footprint/reconciler/pipeline.py`
- Modify: `footprint/reconciler/__init__.py` (export `run_pipeline`)
- Create: `tests/fixtures/fastapi-recon-repo/app/__init__.py`
- Create: `tests/fixtures/fastapi-recon-repo/app/initialize.py`
- Create: `tests/fixtures/fastapi-recon-repo/app/routes/__init__.py`
- Create: `tests/fixtures/fastapi-recon-repo/app/routes/auth.py`
- Create: `tests/fixtures/fastapi-recon-repo/app/routes/health.py`
- Create: `tests/fixtures/fastapi-recon-repo/app/routes/orphan.py`
- Create: `tests/fixtures/fastapi-recon-repo/api_inventory.json`
- Create: `tests/fixtures/fastapi-recon-repo/tests/__init__.py`
- Create: `tests/fixtures/fastapi-recon-repo/tests/auth_calls.py`
- Create: `tests/fixtures/fastapi-recon-repo/tests/health_calls.py`
- Create: `tests/reconciler/test_pipeline.py`

- [ ] **Step 1: Create the branch**

```bash
gt create feat/reconciler-pipeline
```

- [ ] **Step 2: Build the fixture (skeleton)**

```bash
mkdir -p tests/fixtures/fastapi-recon-repo/app/routes
mkdir -p tests/fixtures/fastapi-recon-repo/tests
touch tests/fixtures/fastapi-recon-repo/app/__init__.py
touch tests/fixtures/fastapi-recon-repo/app/routes/__init__.py
touch tests/fixtures/fastapi-recon-repo/tests/__init__.py
```

- [ ] **Step 3: Write the fixture source files**

`tests/fixtures/fastapi-recon-repo/app/initialize.py`:

```python
from fastapi import FastAPI

from app.routes.auth import router as auth_router
from app.routes.health import router as health_router

# Note: orphan.router is intentionally NOT mounted.

app = FastAPI()
app.include_router(auth_router, prefix="/api/auth")
app.include_router(health_router)
```

`tests/fixtures/fastapi-recon-repo/app/routes/auth.py`:

```python
from fastapi import APIRouter

router = APIRouter(prefix="")


@router.get("/check")
def check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/environment")
def environment() -> dict[str, str]:
    return {"env": "production"}


@router.post("/login")
def login() -> dict[str, str]:
    return {"token": "..."}


@router.get(
    "/multiline",
)
def multiline() -> dict[str, str]:
    return {}


@router.post("/secret", include_in_schema=False)
def secret() -> dict[str, str]:
    return {"hidden": "y"}
```

`tests/fixtures/fastapi-recon-repo/app/routes/health.py`:

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

`tests/fixtures/fastapi-recon-repo/app/routes/orphan.py`:

```python
from fastapi import APIRouter

router = APIRouter(prefix="/orphan")


@router.get("/foo")
def foo() -> dict[str, str]:
    return {}


@router.get("/bar")
def bar() -> dict[str, str]:
    return {}
```

`tests/fixtures/fastapi-recon-repo/api_inventory.json`:

```json
{
  "routes": [
    {"method": "GET", "path": "/api/auth/check"},
    {"method": "GET", "path": "/api/auth/environment"},
    {"method": "POST", "path": "/api/auth/login"},
    {"method": "GET", "path": "/api/auth/multiline"},
    {"method": "GET", "path": "/health"},
    {"method": "POST", "path": "/api/legacy/refresh"}
  ]
}
```

`tests/fixtures/fastapi-recon-repo/tests/auth_calls.py`:

> *(named `auth_calls.py` not `test_auth.py` so pytest doesn't try to collect it; the reconciler's `walk_test_tree` heuristic picks it up because it lives under a `tests/` directory.)*

```python
def exercise_check(client):
    client.get("/api/auth/check")


def exercise_login(client):
    client.post("/api/auth/login")
```

`tests/fixtures/fastapi-recon-repo/tests/health_calls.py`:

```python
def exercise_health(client):
    client.get("/health")
```

- [ ] **Step 4: Write the failing pipeline test**

Create `tests/reconciler/test_pipeline.py`:

```python
from __future__ import annotations

from pathlib import Path

from footprint.reconciler.pipeline import run_pipeline

FIXTURE = Path(__file__).parent.parent / "fixtures" / "fastapi-recon-repo"


def test_e2e_buckets_are_correct() -> None:
    result = run_pipeline(
        repo_root=FIXTURE,
        openapi_path=FIXTURE / "api_inventory.json",
        app_init_path=FIXTURE / "app" / "initialize.py",
        exclude=[],
    )
    mounted_paths = {(r.method, r.full_path) for r in result.report.mounted}
    hidden_paths = {(r.method, r.full_path) for r in result.report.hidden}
    unmounted_paths = {(r.method, r.full_path) for r in result.report.unmounted}
    spec_only = set(result.report.spec_only)

    assert ("GET", "/api/auth/check") in mounted_paths
    assert ("GET", "/api/auth/environment") in mounted_paths
    assert ("POST", "/api/auth/login") in mounted_paths
    assert ("GET", "/api/auth/multiline") in mounted_paths
    assert ("GET", "/health") in mounted_paths
    assert len(mounted_paths) == 5

    assert ("POST", "/api/auth/secret") in hidden_paths
    assert len(hidden_paths) == 1

    assert ("GET", "/orphan/foo") in unmounted_paths
    assert ("GET", "/orphan/bar") in unmounted_paths
    assert len(unmounted_paths) == 2

    assert ("POST", "/api/legacy/refresh") in spec_only
    assert len(spec_only) == 1


def test_e2e_coverage_annotated() -> None:
    result = run_pipeline(
        repo_root=FIXTURE,
        openapi_path=FIXTURE / "api_inventory.json",
        app_init_path=FIXTURE / "app" / "initialize.py",
        exclude=[],
    )
    by_path = {r.full_path: r for r in result.report.mounted}
    assert by_path["/api/auth/check"].tested is True
    assert by_path["/api/auth/login"].tested is True
    assert by_path["/api/auth/multiline"].tested is False
    assert by_path["/health"].tested is True


def test_e2e_returns_summary_metadata() -> None:
    result = run_pipeline(
        repo_root=FIXTURE,
        openapi_path=FIXTURE / "api_inventory.json",
        app_init_path=FIXTURE / "app" / "initialize.py",
        exclude=[],
    )
    assert result.repo == str(FIXTURE.resolve())
    assert result.openapi.endswith("api_inventory.json")
    assert result.app_init is not None
    assert result.app_init.endswith("initialize.py")
    assert result.scanned_at  # non-empty ISO timestamp


def test_e2e_no_app_init_falls_back_to_apirouter_only(tmp_path: Path) -> None:
    """Without --app-init, mount_prefix is "" for every route → all unmounted."""
    inv = tmp_path / "inv.json"
    inv.write_text('{"routes": []}')
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "auth.py").write_text(
        'from fastapi import APIRouter\n'
        'router = APIRouter(prefix="/auth")\n'
        '@router.get("/check")\n'
        'def check(): ...\n'
    )
    result = run_pipeline(
        repo_root=tmp_path,
        openapi_path=inv,
        app_init_path=None,
        exclude=[],
    )
    assert any(r.full_path == "/auth/check" for r in result.report.unmounted)
```

- [ ] **Step 5: Run test to verify it fails**

```bash
uv run pytest tests/reconciler/test_pipeline.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'footprint.reconciler.pipeline'`

- [ ] **Step 6: Create `footprint/reconciler/pipeline.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from footprint.openapi_xref import load_inventory_routes
from footprint.reconciler.bucket import bucket_routes
from footprint.reconciler.coverage import annotate_coverage, walk_test_tree
from footprint.reconciler.extract import extract_from_tree, walk_source_tree
from footprint.reconciler.mounts import (
    auto_discover_init,
    build_mount_map,
    extract_mounts_from_source,
)
from footprint.reconciler.types import BucketedReport


@dataclass
class PipelineResult:
    report: BucketedReport
    repo: str
    openapi: str
    app_init: str | None
    scanned_at: str


def run_pipeline(
    *,
    repo_root: Path,
    openapi_path: Path,
    app_init_path: Path | None,
    exclude: list[str],
) -> PipelineResult:
    """Run all six passes and return a PipelineResult."""
    repo_root = repo_root.resolve()

    # Pass 1: load spec
    inventory = load_inventory_routes(str(openapi_path))

    # Pass 2: AST-extract source
    source_files = [Path(p) for p in walk_source_tree(repo_root, exclude=exclude)]
    routers, raw_routes = extract_from_tree(repo_root, source_files)

    # Pass 3: AST-extract init file
    resolved_init = app_init_path or auto_discover_init(repo_root)
    if resolved_init is not None:
        init_text = resolved_init.read_text(encoding="utf-8", errors="ignore")
        init_rel = (
            resolved_init.relative_to(repo_root).as_posix()
            if resolved_init.is_relative_to(repo_root)
            else resolved_init.as_posix()
        )
        mounts = extract_mounts_from_source(init_text, init_file=init_rel)
        mount_map = build_mount_map(mounts)
    else:
        mount_map = {}

    # Pass 4: bucket
    report = bucket_routes(raw_routes, routers, mount_map, inventory)

    # Pass 5: coverage
    test_files = walk_test_tree(repo_root, exclude=exclude)
    annotate_coverage(report, repo_root, test_files)

    return PipelineResult(
        report=report,
        repo=str(repo_root),
        openapi=str(openapi_path.resolve()),
        app_init=str(resolved_init.resolve()) if resolved_init else None,
        scanned_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
```

- [ ] **Step 7: Update `footprint/reconciler/__init__.py` to export `run_pipeline`**

```python
from __future__ import annotations

from footprint.reconciler.pipeline import PipelineResult, run_pipeline
from footprint.reconciler.types import (
    BucketedReport,
    MountInfo,
    RawRoute,
    ResolvedRoute,
    RouterDef,
)

__all__ = [
    "BucketedReport",
    "MountInfo",
    "PipelineResult",
    "RawRoute",
    "ResolvedRoute",
    "RouterDef",
    "run_pipeline",
]
```

- [ ] **Step 8: Run pipeline tests to verify they pass**

```bash
uv run pytest tests/reconciler/test_pipeline.py -v
```

Expected: 4 passed.

- [ ] **Step 9: Run full check suite**

```bash
mise run check
```

Expected: All passed.

- [ ] **Step 10: Commit**

```bash
git add footprint/reconciler/pipeline.py footprint/reconciler/__init__.py \
        tests/reconciler/test_pipeline.py tests/fixtures/fastapi-recon-repo/
git commit -m "feat(reconciler): pipeline orchestration + e2e fixture

Adds pipeline.py wiring all six passes (load → extract → mounts →
bucket → coverage → render-data) and a full FastAPI fixture at
tests/fixtures/fastapi-recon-repo/ that exercises every bucket
(mounted, hidden, unmounted, spec-only) plus per-route coverage."
```

---

## Task 8: CLI integration (`reconcile` subcommand)

**Branch:** `feat/reconciler-cli` (parent: `feat/reconciler-pipeline`)

**Files:**
- Create: `footprint/reconciler/cli.py`
- Modify: `footprint/cli.py`
- Create: `tests/reconciler/test_cli.py`

- [ ] **Step 1: Create the branch**

```bash
gt create feat/reconciler-cli
```

- [ ] **Step 2: Write the failing test**

Create `tests/reconciler/test_cli.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from footprint.cli import main

FIXTURE = Path(__file__).parent.parent / "fixtures" / "fastapi-recon-repo"


def test_reconcile_outputs_valid_json() -> None:
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "reconcile",
            str(FIXTURE),
            "--openapi",
            str(FIXTURE / "api_inventory.json"),
            "--app-init",
            str(FIXTURE / "app" / "initialize.py"),
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert "summary" in data
    assert "endpoints" in data
    assert data["summary"]["counts"]["mounted"] == 5
    assert data["summary"]["counts"]["hidden"] == 1
    assert data["summary"]["counts"]["unmounted"] == 2
    assert data["summary"]["counts"]["spec_only"] == 1


def test_reconcile_writes_markdown_when_md_flag_given(tmp_path: Path) -> None:
    md_path = tmp_path / "report.md"
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "reconcile",
            str(FIXTURE),
            "--openapi",
            str(FIXTURE / "api_inventory.json"),
            "--app-init",
            str(FIXTURE / "app" / "initialize.py"),
            "--md",
            str(md_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert md_path.exists()
    md = md_path.read_text()
    assert "# Network Reconciliation Report" in md
    assert "## Mounted (5)" in md
    assert "## Hidden (1)" in md
    assert "## Unmounted (2)" in md
    assert "## Spec-only (1)" in md


def test_reconcile_auto_discovers_init_file(tmp_path: Path) -> None:
    """Without --app-init, the CLI should find app/initialize.py automatically."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "reconcile",
            str(FIXTURE),
            "--openapi",
            str(FIXTURE / "api_inventory.json"),
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    # Auto-discover should find app/initialize.py and resolve mounts correctly.
    assert data["summary"]["counts"]["mounted"] == 5


def test_reconcile_missing_openapi_errors() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["reconcile", str(FIXTURE)])
    assert result.exit_code != 0


def test_reconcile_nonexistent_openapi_errors() -> None:
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["reconcile", str(FIXTURE), "--openapi", "/no/such/file.json"],
    )
    assert result.exit_code != 0
```

- [ ] **Step 3: Run test to verify it fails**

```bash
uv run pytest tests/reconciler/test_cli.py -v
```

Expected: FAIL — the `reconcile` command doesn't exist yet.

- [ ] **Step 4: Create `footprint/reconciler/cli.py`**

```python
from __future__ import annotations

from pathlib import Path

import click

from footprint.reconciler.pipeline import run_pipeline
from footprint.reconciler.render import render_json, render_markdown


@click.command()
@click.argument("repo_path", default=".", type=click.Path(exists=True))
@click.option(
    "--openapi",
    "openapi_path",
    required=True,
    type=click.Path(exists=True),
    help="Path to api_inventory.json or openapi.{yaml,json}",
)
@click.option(
    "--app-init",
    "app_init_path",
    default=None,
    type=click.Path(exists=True),
    help="Path to app init file. If omitted, auto-discover.",
)
@click.option(
    "--md",
    "md_path",
    default=None,
    type=click.Path(),
    help="Write Markdown report to this path (in addition to JSON on stdout)",
)
@click.option(
    "--manifest",
    "manifest_path",
    default=None,
    type=click.Path(exists=True),
    help="Manifest file (only the exclude list is honored)",
)
@click.option("--verbose", "-v", is_flag=True, default=False)
def reconcile(
    repo_path: str,
    openapi_path: str,
    app_init_path: str | None,
    md_path: str | None,
    manifest_path: str | None,
    verbose: bool,
) -> None:
    """Reconcile a FastAPI codebase against an OpenAPI/inventory file."""
    repo = Path(repo_path).resolve()
    exclude = _load_exclude(manifest_path)

    if verbose:
        click.echo(f"[reconcile] repo: {repo}", err=True)
        click.echo(f"[reconcile] openapi: {openapi_path}", err=True)
        click.echo(f"[reconcile] app-init: {app_init_path or '(auto-discover)'}", err=True)

    result = run_pipeline(
        repo_root=repo,
        openapi_path=Path(openapi_path),
        app_init_path=Path(app_init_path) if app_init_path else None,
        exclude=exclude,
    )

    if result.app_init is None:
        click.echo(
            "[reconcile] warning: no app init file found — mount prefixes not resolved",
            err=True,
        )

    if verbose:
        c = result.report
        click.echo(
            f"[reconcile] mounted={len(c.mounted)} hidden={len(c.hidden)} "
            f"unmounted={len(c.unmounted)} spec_only={len(c.spec_only)}",
            err=True,
        )

    click.echo(
        render_json(
            result.report,
            repo=result.repo,
            openapi=result.openapi,
            app_init=result.app_init or "",
            scanned_at=result.scanned_at,
        )
    )

    if md_path:
        Path(md_path).write_text(
            render_markdown(
                result.report,
                repo=result.repo,
                openapi=result.openapi,
                app_init=result.app_init or "",
                scanned_at=result.scanned_at,
            ),
            encoding="utf-8",
        )


def _load_exclude(manifest_path: str | None) -> list[str]:
    if not manifest_path:
        return []
    from footprint.manifest import load_manifest  # noqa: PLC0415

    manifest = load_manifest(Path("."), Path(manifest_path))
    return list(manifest.exclude)
```

- [ ] **Step 5: Register the command in `footprint/cli.py`**

The existing `footprint/cli.py` has imports at the top and a `@click.group()` decorator on `def main()` (around line 17). Apply two edits:

**Edit A** — add to the import block (alphabetized; goes between `manifest` and `mount_tracker` imports):

```python
from footprint.reconciler.cli import reconcile as _reconcile_command
```

**Edit B** — immediately after the `def main()` group definition (after the closing of its docstring), add a single line:

```python
main.add_command(_reconcile_command, name="reconcile")
```

The result around lines 16-21 should look like:

```python
@click.group()
def main() -> None:
    """Scan repositories for network traffic patterns and API endpoints."""


main.add_command(_reconcile_command, name="reconcile")
```

- [ ] **Step 6: Run CLI tests to verify they pass**

```bash
uv run pytest tests/reconciler/test_cli.py -v
```

Expected: 5 passed.

- [ ] **Step 7: Smoke-test the CLI manually**

```bash
uv run footprint reconcile tests/fixtures/fastapi-recon-repo/ \
  --openapi tests/fixtures/fastapi-recon-repo/api_inventory.json \
  --app-init tests/fixtures/fastapi-recon-repo/app/initialize.py | head -30
```

Expected: A JSON document beginning with `{` and including a `summary` block.

- [ ] **Step 8: Run full check suite**

```bash
mise run check
```

Expected: All passed.

- [ ] **Step 9: Commit**

```bash
git add footprint/reconciler/cli.py footprint/cli.py tests/reconciler/test_cli.py
git commit -m "feat(reconciler): footprint reconcile subcommand

Adds the click subcommand wiring repo path, --openapi (required),
--app-init (optional, auto-discovered), --md, --manifest, --verbose.
JSON to stdout always; Markdown only when --md PATH is given. Emits
a stderr warning when no app init file is found."
```

---

## Task 9: README + stack-coverage docs

**Branch:** `docs/reconciler-readme` (parent: `feat/reconciler-cli`)

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Create the branch**

```bash
gt create docs/reconciler-readme
```

- [ ] **Step 2: Add a "Reconciliation mode" section to README**

In `README.md`, find the "OpenAPI / inventory cross-reference" section (added in PR `feat/openapi-xref`). Immediately *after* it, add a new section:

````markdown
---

## Reconciliation mode (`footprint reconcile`)

For FastAPI codebases that publish an OpenAPI/inventory file, `footprint reconcile` flips the analysis around: instead of scanning the repo and annotating matches, it loads the inventory as ground truth and buckets every detected route as **mounted**, **hidden**, **unmounted**, or **spec-only**.

```bash
footprint reconcile ./my-repo \
  --openapi ./schemas/api_inventory.json \
  --app-init ./app/initialize.py \
  --md report.md
```

**Buckets:**

| Bucket    | Meaning |
|-----------|---------|
| `mounted` | Decorator in code, route in inventory |
| `hidden` | Decorator has `include_in_schema=False`; route is in `app.routes` but not in OpenAPI by design |
| `unmounted` | Decorator in code, but the composed path is not in the inventory → dead router, never-included file, or wrong prefix |
| `spec_only` | Inventory entry with no matching code (sanity check; should be empty) |

Per-route coverage is computed by walking test files (heuristic: `tests/`, `test_*.py`, `*_test.py`) for `client.get("/api/...")` style calls and intersecting with the route set.

**vs. `footprint scan`:** `scan` is the general-purpose pattern-based tool (works on any stack, finds outbound calls, suggestive output). `reconcile` is FastAPI-specific and requires an OpenAPI/inventory file but produces a sharp, structured reconciliation suitable for security review.

**Limitations:** Two-level prefix composition only — `APIRouter(prefix=...)` plus `app.include_router(target, prefix=...)` from a single init file. Nested router-includes-router across files isn't resolved (those routes appear as `unmounted` with `mount_prefix=""`).

````

- [ ] **Step 3: Update the Stack coverage table**

Find the existing `## Stack coverage` table in `README.md`. Add this row at the bottom of the table (just before the "What this means in practice" section):

```markdown
| Reconciliation against OpenAPI (`footprint reconcile`) | ✓ | — | — | — |
```

- [ ] **Step 4: Update the Contents list**

Find the `## Contents` list. Add `- [Reconciliation mode](#reconciliation-mode-footprint-reconcile)` between the existing entries for "OpenAPI / inventory cross-reference" and "Category taxonomy".

- [ ] **Step 5: Run check suite**

```bash
mise run check
```

Expected: All passed (no Python changes; tests should still all pass).

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs: add Reconciliation mode section to README

Documents footprint reconcile, its four buckets, the per-route coverage
heuristic, and the two-level prefix composition limitation. Updates the
Stack coverage table with a row for reconciliation support and adds a
Contents entry."
```

---

## Task 10: Submit the stack

**Branch:** stays on `docs/reconciler-readme` (the top of the stack)

- [ ] **Step 1: Verify the stack**

```bash
gt log short
```

Expected: A graphite stack showing `feat/reconciler-types` at the bottom, climbing through `feat/reconciler-extract`, `feat/reconciler-mounts`, `feat/reconciler-bucket`, `feat/reconciler-coverage`, `feat/reconciler-render`, `feat/reconciler-pipeline`, `feat/reconciler-cli`, with `docs/reconciler-readme` at the top.

- [ ] **Step 2: Run check suite one more time**

```bash
mise run check
```

Expected: All passed across the full repo.

- [ ] **Step 3: Submit the stack**

```bash
gt submit --stack
```

Expected: Graphite creates 9 PRs, each stacked on top of the previous. The output prints PR URLs.

- [ ] **Step 4: Verify each PR's CI is green**

For each PR URL printed by `gt submit --stack`, open it and confirm the CI checks pass. If any PR fails CI, fix on that branch (`gt checkout <branch>`, fix, commit, `gt submit --stack` again to update).

---

## Notes for the implementing engineer

1. **Each task ends with `mise run check` passing.** Don't skip this — pre-commit hooks run trivy + ruff + mypy, and a failure on a downstream task means rebasing the entire upstream stack.

2. **Don't combine commits across tasks.** Each task = one PR = one commit. Graphite expects this; combining commits will confuse the stack tracking.

3. **If you find yourself adding a "TODO" or skipping a test:** stop and reread the spec. The plan was written assuming every step is concretely doable as written. If reality says otherwise, that's a plan bug — flag it and adjust.

4. **The fixture is load-bearing.** Task 7 sets up `tests/fixtures/fastapi-recon-repo/` such that the e2e test asserts exact bucket counts (5 mounted, 1 hidden, 2 unmounted, 1 spec-only). If you change the fixture's routes, update the assertions.

5. **The shared `openapi_xref.load_inventory_routes` function is the only import from existing code.** If you find yourself reaching into `footprint.scanner` or `footprint.path_extractor`, stop — the design says those modules stay scoped to `scan` mode.

6. **Path normalization in `bucket.py` happens twice** — once when building `claimed` (so spec_only sweep matches normalized) and once when looking up routes against the inventory. Both directions must agree, hence the helper.

7. **Mount prefix is `""` (empty string), not `None`,** when no mount is found. This is a deliberate choice for type simplicity (`str` everywhere). The test for "mount resolved" in the Markdown renderer uses `if r.mount_prefix` which is `False` for the empty string.
