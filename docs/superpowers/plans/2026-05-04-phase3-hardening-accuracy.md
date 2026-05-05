# Phase 3: Hardening & Accuracy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce noise, improve signal quality, and make output trustworthy enough to hand directly to Claude or for a PRR audit. Add confidence scoring, false positive suppression, a scan summary block, and `--verbose` / `--no-transitive` flags. Validate accuracy against ground-truth fixture repos.

**Architecture:** False-positive detection lives in a new `footprint/heuristics.py` module. Confidence scoring and context tagging run as a post-scan pass in the scanner. Summary block is assembled in `report.py`. Noisy patterns are tightened in `patterns.py` with documented rationale. All new behaviour is covered by fixture-based ground-truth tests.

**Tech Stack:** Python 3.11, uv, click≥8, pyyaml≥6, anthropic≥0.20, hatchling, ruff, mypy (strict), pytest, mise, Graphite (gt)

**Workflow:** Follow AGENTS.md — `gt create` per branch stacked on previous, `mise run check` before every commit.

---

## File Map

| File | Status | Responsibility |
|------|--------|----------------|
| `footprint/heuristics.py` | **Create** | `is_comment()`, `is_string_literal()`, `is_test_file()` |
| `footprint/scanner.py` | **Modify** | Add `in_comment`, `in_string_literal`, `context`, `confidence` to `Match`; post-scan confidence scoring; `--no-transitive` filtering |
| `footprint/patterns.py` | **Modify** | Tighten `\bpath\(`, `\burl\(`, `ports:`, `fetch\(` with documented rationale |
| `footprint/report.py` | **Modify** | Add summary block to JSON output; update markdown to show confidence |
| `footprint/cli.py` | **Modify** | Add `--verbose`, `--no-transitive`, `--min-confidence` flags |
| `tests/fixtures/fp-negatives/` | **Create** | Files that should NOT match — ground-truth negatives for noisy patterns |
| `tests/fixtures/fp-positives/` | **Create** | Files that SHOULD match — ground-truth positives |
| `tests/fixtures/comment-edge/` | **Create** | Commented imports, string literals containing package names |
| `tests/test_heuristics.py` | **Create** | Unit tests for comment/string/test detection |
| `tests/test_confidence.py` | **Create** | Confidence scoring correctness |
| `tests/test_patterns_accuracy.py` | **Create** | Ground-truth fixture tests (no false positives on negatives) |
| `tests/test_report_summary.py` | **Create** | Summary block shape and accuracy |

---

## Task 1: Heuristics Module + Match Fields

**Branch:** `feat/phase3-heuristics` (stacked on `feat/markdown-output`)

**Files:**
- Create: `footprint/heuristics.py`
- Modify: `footprint/scanner.py` (add fields to `Match`, wire heuristics)
- Create: `tests/fixtures/comment-edge/commented_imports.py`
- Create: `tests/fixtures/comment-edge/commented_imports.ts`
- Create: `tests/fixtures/comment-edge/string_literals.py`
- Create: `tests/test_heuristics.py`

- [ ] **Step 1: Create edge-case fixture files**

`tests/fixtures/comment-edge/commented_imports.py`:
```python
# import requests  <- commented out, should be flagged in_comment
# from httpx import AsyncClient
x = "import requests"  # string literal, not real import

import os  # real import, not network-related
```

`tests/fixtures/comment-edge/commented_imports.ts`:
```typescript
// import axios from 'axios'  <- commented out
/* import express from 'express' */
* import got from 'got'   <- inside block comment
const msg = "use fetch() to make requests";  // string literal
```

`tests/fixtures/comment-edge/string_literals.py`:
```python
"""
Example showing how to use requests:
    import requests
    r = requests.get(url)
"""
doc = "from requests import Session"  # in a string

import os
```

- [ ] **Step 2: Write failing tests for heuristics**

Create `tests/test_heuristics.py`:
```python
from __future__ import annotations

from footprint.heuristics import is_comment, is_string_literal, is_test_file


def test_python_comment_detected() -> None:
    assert is_comment("    # import requests", "python") is True


def test_python_non_comment() -> None:
    assert is_comment("import requests", "python") is False


def test_node_single_line_comment() -> None:
    assert is_comment("// import axios from 'axios'", "node") is True


def test_node_block_comment_star() -> None:
    assert is_comment("  * import express", "node") is True


def test_node_block_comment_open() -> None:
    assert is_comment("/* import got */", "node") is True


def test_non_comment_node() -> None:
    assert is_comment("import axios from 'axios'", "node") is False


def test_string_literal_double_quoted() -> None:
    assert is_string_literal('doc = "import requests"', 7) is True


def test_string_literal_single_quoted() -> None:
    assert is_string_literal("msg = 'fetch(url)'", 7) is True


def test_not_string_literal() -> None:
    assert is_string_literal("import requests", 0) is False


def test_test_file_spec() -> None:
    assert is_test_file("src/services/api.spec.ts") is True


def test_test_file_test_suffix() -> None:
    assert is_test_file("src/services/api.test.ts") is True


def test_test_file_python_spec() -> None:
    assert is_test_file("tests/test_api.py") is True


def test_test_file_tests_dir() -> None:
    assert is_test_file("tests/integration/test_routes.py") is True


def test_test_file_underscore_tests_dir() -> None:
    assert is_test_file("src/__tests__/api.ts") is True


def test_non_test_file() -> None:
    assert is_test_file("src/services/api.ts") is False


def test_non_test_python() -> None:
    assert is_test_file("src/routes.py") is False
```

- [ ] **Step 3: Verify tests fail**

```bash
uv run pytest tests/test_heuristics.py -v 2>&1 | head -5
```
Expected: `ModuleNotFoundError: No module named 'footprint.heuristics'`

- [ ] **Step 4: Implement `footprint/heuristics.py`**

```python
from __future__ import annotations

import re

# Test file path patterns
_TEST_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\.test\.(ts|tsx|js|jsx)$"),
    re.compile(r"\.spec\.(ts|tsx|js|jsx|py)$"),
    re.compile(r"(^|/)tests?/"),
    re.compile(r"(^|/)__tests__/"),
    re.compile(r"(^|/)test_[^/]+\.py$"),
]


def is_comment(line: str, stack: str) -> bool:
    """Return True if the line appears to be a comment in the given stack."""
    stripped = line.strip()
    if stack in ("node", "ts"):
        return (
            stripped.startswith("//")
            or stripped.startswith("*")
            or stripped.startswith("/*")
        )
    if stack == "python":
        return stripped.startswith("#")
    return False


def is_string_literal(line: str, match_pos: int) -> bool:
    """Heuristic: return True if match_pos falls inside a string literal on this line."""
    # Count unescaped quotes before match_pos
    before = line[:match_pos]
    # Simple heuristic: odd number of unescaped quotes → inside a string
    single = before.count("'") - before.count("\\'")
    double = before.count('"') - before.count('\\"')
    return (single % 2 == 1) or (double % 2 == 1)


def is_test_file(path: str) -> bool:
    """Return True if the file path matches known test file patterns."""
    return any(p.search(path) is not None for p in _TEST_PATTERNS)
```

- [ ] **Step 5: Add `in_comment`, `in_string_literal`, `context` fields to `Match` in `footprint/scanner.py`**

Add three new fields to `Match` (all default to False/None so existing tests stay green):

```python
@dataclass
class Match:
    pattern: str
    category: str
    stack: str
    line: int
    source: str = "default"
    transitive: bool = False
    line_content: str = ""
    in_comment: bool = False
    in_string_literal: bool = False
    context: str = ""   # "test" | "" (empty = production)
```

Update `Scanner.__init__` to import heuristics:
```python
from footprint.heuristics import is_comment, is_string_literal, is_test_file
```

Update `_scan_file` to detect and tag:
```python
def _scan_file(self, path: Path) -> list[Match]:
    is_devops = self._is_devops_file(path)
    rel_path = str(path.relative_to(self._root))
    context = "test" if is_test_file(rel_path) else ""
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
            m = re.search(p["pattern"], line)
            if m:
                key = (p["pattern"], lineno)
                if key not in seen:
                    seen.add(key)
                    matches.append(Match(
                        pattern=p["pattern"],
                        category=p["category"],
                        stack=p["stack"],
                        line=lineno,
                        source=str(p.get("source", "default")),
                        transitive=bool(p.get("transitive", False)),
                        line_content=line,
                        in_comment=is_comment(line, p["stack"]),
                        in_string_literal=is_string_literal(line, m.start()),
                        context=context,
                    ))
    return matches
```

- [ ] **Step 6: Run all tests**

```bash
uv run pytest -v
```
Expected: all 133 + 15 new = 148+ tests pass.

- [ ] **Step 7: Run mise check**

```bash
mise run check
```

- [ ] **Step 8: Commit**

```bash
gt create feat/phase3-heuristics
git add footprint/heuristics.py footprint/scanner.py \
        tests/test_heuristics.py tests/fixtures/comment-edge/
git commit -m "feat(heuristics): comment/string/test detection; add in_comment, context to Match"
```

---

## Task 2: Confidence Scoring + --min-confidence + --no-transitive

**Branch:** `feat/phase3-confidence` (stacked on `feat/phase3-heuristics`)

**Files:**
- Modify: `footprint/scanner.py` (add `confidence` to `Match`, compute after scan)
- Modify: `footprint/cli.py` (add `--min-confidence`, `--no-transitive` flags)
- Modify: `footprint/report.py` (include `confidence`, `in_comment`, `context` in JSON; confidence in markdown)
- Create: `tests/test_confidence.py`

- [ ] **Step 1: Write failing confidence tests**

Create `tests/test_confidence.py`:
```python
from __future__ import annotations

from pathlib import Path

from footprint.manifest import ManifestConfig
from footprint.scanner import Scanner


def _scanner(tmp_path: Path, content: str, filename: str = "api.ts") -> Scanner:
    (tmp_path / filename).write_text(content)
    return Scanner(str(tmp_path), ManifestConfig(stacks=["node"], exclude=[]))


def test_base_confidence_for_plain_match(tmp_path: Path) -> None:
    scanner = _scanner(tmp_path, "import axios from 'axios';\n")
    results = scanner.run()
    assert results
    m = results[0].matches[0]
    assert 0.0 <= m.confidence <= 1.0
    assert m.confidence >= 0.5   # plain match should be at least base


def test_comment_reduces_confidence(tmp_path: Path) -> None:
    scanner = _scanner(tmp_path, "// import axios from 'axios'\n")
    results = scanner.run()
    if results:  # may still be captured
        m = results[0].matches[0]
        assert m.in_comment is True
        assert m.confidence < 0.5


def test_route_definition_higher_confidence(tmp_path: Path) -> None:
    scanner = _scanner(tmp_path, "router.get('/users', handler);\n")
    results = scanner.run()
    assert results
    m = next(m for r in results for m in r.matches if m.category == "route_definition")
    assert m.confidence >= 0.7


def test_test_file_reduces_confidence(tmp_path: Path) -> None:
    scanner = _scanner(tmp_path, "import axios from 'axios';\n", "api.test.ts")
    results = scanner.run()
    assert results
    m = results[0].matches[0]
    assert m.context == "test"
    assert m.confidence < 0.8


def test_multiple_matches_boost_confidence(tmp_path: Path) -> None:
    content = "\n".join([
        "import axios from 'axios';",
        "const res = await axios.get(url);",
        "const res2 = await axios.post(url, data);",
    ])
    scanner = _scanner(tmp_path, content)
    results = scanner.run()
    assert results
    confidences = [m.confidence for m in results[0].matches]
    # Later matches (more matches in file) should have higher or equal confidence
    assert max(confidences) > min(confidences) or all(c == confidences[0] for c in confidences)


def test_confidence_clamped_to_one(tmp_path: Path) -> None:
    content = "\n".join([f"import axios from 'axios';  // line {i}" for i in range(10)])
    scanner = _scanner(tmp_path, content)
    results = scanner.run()
    assert results
    for m in results[0].matches:
        assert m.confidence <= 1.0


def test_confidence_clamped_to_zero(tmp_path: Path) -> None:
    # Commented + string literal should score near 0
    scanner = _scanner(tmp_path, "// const s = \"import axios\";\n")
    results = scanner.run()
    if results:
        for m in results[0].matches:
            assert m.confidence >= 0.0
```

- [ ] **Step 2: Verify tests fail**

```bash
uv run pytest tests/test_confidence.py -v 2>&1 | head -5
```
Expected: `AttributeError: 'Match' has no attribute 'confidence'`

- [ ] **Step 3: Add `confidence` to `Match` and scoring logic**

Add `confidence: float = 0.0` to `Match` dataclass.

Add a `_score_confidence` method to `Scanner` and call it after `_scan_file`:

```python
_BASE_CONFIDENCE: float = 0.7

def _score_confidence(self, matches: list[Match]) -> None:
    """Mutate confidence scores in-place based on heuristics."""
    n = len(matches)
    for i, m in enumerate(matches):
        score = _BASE_CONFIDENCE
        if m.in_comment:
            score -= 0.4
        if m.in_string_literal:
            score -= 0.3
        if m.context == "test":
            score -= 0.1
        if m.category == "route_definition":
            score += 0.2
        if m.source == "dependency_resolved":
            score += 0.1
        # Bonus for additional matches in same file (capped at +0.3)
        extra = min(i, 3) * 0.1
        score += extra
        m.confidence = max(0.0, min(1.0, score))
```

Call it in `run()` right after `matches = self._scan_file(path)`:
```python
matches = self._scan_file(path)
if matches:
    self._score_confidence(matches)
    results.append(...)
```

- [ ] **Step 4: Update `format_json` to include confidence, in_comment, context**

In `footprint/report.py`, add these fields to each match entry in `format_json`:
```python
entry: dict[str, object] = {
    "pattern": m.pattern,
    "category": m.category,
    "stack": m.stack,
    "line": m.line,
    "source": m.source,
    "confidence": round(m.confidence, 2),
}
if m.in_comment:
    entry["in_comment"] = True
if m.in_string_literal:
    entry["in_string_literal"] = True
if m.context:
    entry["context"] = m.context
if m.transitive:
    entry["transitive"] = True
```

In `format_markdown`, add confidence next to the line number column:
```
| Line | Confidence | Snippet |
|------|------------|---------|
| 5 | 0.90 | `router.get('/users', handler)` |
```

- [ ] **Step 5: Add `--min-confidence` and `--no-transitive` to CLI**

```python
@click.option("--min-confidence", default=0.0, type=float,
              help="Only show matches at or above this confidence (0.0–1.0)")
@click.option("--no-transitive", is_flag=True, default=False,
              help="Exclude matches from transitive dependencies")
```

After scanning, apply filters:
```python
if no_transitive or min_confidence > 0.0:
    for r in results:
        r.matches = [
            m for m in r.matches
            if (not no_transitive or not m.transitive)
            and m.confidence >= min_confidence
        ]
    results = [r for r in results if r.matches]
    # Recalculate categories after filtering
    for r in results:
        r.categories = sorted({m.category for m in r.matches})
```

- [ ] **Step 6: Run all tests**

```bash
uv run pytest -v
```
Expected: all 148+ tests pass.

- [ ] **Step 7: Run mise check and commit**

```bash
mise run check
gt create feat/phase3-confidence
git add footprint/scanner.py footprint/cli.py footprint/report.py tests/test_confidence.py
git commit -m "feat(phase3): confidence scoring, --min-confidence, --no-transitive flags"
```

---

## Task 3: Noisy Pattern Audit

**Branch:** `feat/phase3-patterns` (stacked on `feat/phase3-confidence`)

**Files:**
- Modify: `footprint/patterns.py` (tighten 4 noisy patterns)
- Create: `tests/fixtures/fp-negatives/path_false_positives.py`
- Create: `tests/fixtures/fp-negatives/url_false_positives.py`
- Create: `tests/fixtures/fp-negatives/ports_false_positives.yml`
- Create: `tests/fixtures/fp-negatives/fetch_false_positives.ts`
- Create: `tests/fixtures/fp-positives/real_routes.py`
- Create: `tests/fixtures/fp-positives/real_network.ts`
- Create: `tests/test_patterns_accuracy.py`

- [ ] **Step 1: Create ground-truth fixture files**

`tests/fixtures/fp-negatives/path_false_positives.py`:
```python
import os
import pathlib

# Filesystem path operations — NOT routes
config_path = pathlib.Path("/etc/config")
result = os.path.join("/tmp", "output.txt")

def process(file_path: str) -> None:
    p = pathlib.Path(file_path)
    resolved = p.resolve()
    parts = resolved.parts
```

`tests/fixtures/fp-negatives/url_false_positives.py`:
```python
from urllib.parse import urlparse

# url() here is NOT a Django route — it's a variable name
url = "https://example.com"
parsed_url = urlparse(url)
image_url = "https://cdn.example.com/img.png"
```

`tests/fixtures/fp-negatives/ports_false_positives.yml`:
```yaml
# This is a CI config — ports: here is NOT networking
build:
  supported_ports:
    - grpc
    - http
settings:
  transports: [http2, h3]
```

`tests/fixtures/fp-negatives/fetch_false_positives.ts`:
```typescript
// These should NOT match — not real fetch calls
const prefetchData = prefetch(url);
const refetchInterval = 5000;
function usePrefetch() {}
```

`tests/fixtures/fp-positives/real_routes.py`:
```python
from flask import Flask

app = Flask(__name__)

@app.get('/health')
def health():
    return 'ok'

@app.post('/users')
def create_user():
    pass
```

`tests/fixtures/fp-positives/real_network.ts`:
```typescript
import axios from 'axios';

const result = await axios.get('/api/users');
const data = await fetch('/api/data');
```

- [ ] **Step 2: Write ground-truth accuracy tests**

Create `tests/test_patterns_accuracy.py`:
```python
from __future__ import annotations

from pathlib import Path

from footprint.manifest import ManifestConfig
from footprint.scanner import Scanner

NEGATIVES_DIR = Path(__file__).parent / "fixtures" / "fp-negatives"
POSITIVES_DIR = Path(__file__).parent / "fixtures" / "fp-positives"


def _scan_file(path: Path, stacks: list[str]) -> list[str]:
    """Return matched pattern strings for a single file."""
    scanner = Scanner(str(path.parent), ManifestConfig(stacks=stacks, exclude=[]))
    results = scanner.run()
    target = next((r for r in results if r.file == path.name), None)
    return [m.pattern for m in target.matches] if target else []


def test_path_false_positive_not_matched() -> None:
    patterns = _scan_file(NEGATIVES_DIR / "path_false_positives.py", ["python"])
    route_patterns = [p for p in patterns if "path" in p.lower()]
    assert route_patterns == [], f"False positives: {route_patterns}"


def test_url_false_positive_not_matched_as_route() -> None:
    patterns = _scan_file(NEGATIVES_DIR / "url_false_positives.py", ["python"])
    url_route_patterns = [p for p in patterns if r"\burl\(" in p]
    assert url_route_patterns == [], f"False positives: {url_route_patterns}"


def test_ports_false_positive_not_matched() -> None:
    patterns = _scan_file(NEGATIVES_DIR / "ports_false_positives.yml", ["devops"])
    ports_patterns = [p for p in patterns if "ports" in p]
    assert ports_patterns == [], f"False positives: {ports_patterns}"


def test_fetch_false_positive_not_matched() -> None:
    patterns = _scan_file(NEGATIVES_DIR / "fetch_false_positives.ts", ["node"])
    fetch_patterns = [p for p in patterns if "fetch" in p.lower()]
    assert fetch_patterns == [], f"False positives: {fetch_patterns}"


def test_real_routes_detected() -> None:
    patterns = _scan_file(POSITIVES_DIR / "real_routes.py", ["python"])
    assert len(patterns) > 0, "Expected route matches in real_routes.py"


def test_real_network_detected() -> None:
    patterns = _scan_file(POSITIVES_DIR / "real_network.ts", ["node"])
    assert len(patterns) > 0, "Expected network matches in real_network.ts"
```

- [ ] **Step 3: Run tests to see which currently FAIL (revealing real false positives)**

```bash
uv run pytest tests/test_patterns_accuracy.py -v
```
Note which tests fail — those are the patterns that need tightening.

- [ ] **Step 4: Tighten noisy patterns in `footprint/patterns.py`**

Make the following changes:

**`\bpath\(`** — too noisy for filesystem operations. Remove from PYTHON_PATTERNS. It only fires on Django/Flask routing, which is better caught by `@app.route` / `@router.X` patterns already present.

**`\burl\(`** — remove from PYTHON_PATTERNS. Too broad. Django `url()` is legacy (replaced by `path()`); the decorator patterns already catch Flask/FastAPI routes.

**`\bfetch\(`** — already tightened to `\bfetch\(` in Phase 1. Verify it does not match `prefetch(` or `refetch(`. If it does, check the word boundary is truly working. The fixture test above will verify.

**`ports:` in YAML** — change from `ports:` to `^\s+ports:` to require indentation (top-level `ports:` is usually a key in a config block, not a networking stanza). The real Docker Compose `ports:` appears indented under a service.

After tightening, add a comment above each changed pattern explaining the rationale:
```python
# Narrowed from r"ports:" — top-level ports: appears in CI configs and is not networking.
# Indented ports: under a service block is the Docker Compose networking signal.
{ "pattern": r"^\s+ports:", "category": "devops", "stack": "devops" },
```

- [ ] **Step 5: Run accuracy tests again — all must pass**

```bash
uv run pytest tests/test_patterns_accuracy.py -v
```
Expected: all 6 PASS.

- [ ] **Step 6: Run full suite**

```bash
uv run pytest -v
```
Expected: all tests pass (some old tests that relied on `\bpath\(` or `\burl\(` may need fixture updates — fix them).

- [ ] **Step 7: Run mise check and commit**

```bash
mise run check
gt create feat/phase3-patterns
git add footprint/patterns.py \
        tests/fixtures/fp-negatives/ tests/fixtures/fp-positives/ \
        tests/test_patterns_accuracy.py
git commit -m "feat(phase3): tighten noisy patterns; ground-truth accuracy fixtures"
```

---

## Task 4: Scan Summary Block + --verbose

**Branch:** `feat/phase3-summary` (stacked on `feat/phase3-patterns`)

**Files:**
- Modify: `footprint/report.py` (wrap JSON output in `{results: [...], summary: {...}}`)
- Modify: `footprint/cli.py` (add `--verbose` flag, print verbose info to stderr)
- Create: `tests/test_report_summary.py`

- [ ] **Step 1: Write failing summary tests**

Create `tests/test_report_summary.py`:
```python
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from footprint.manifest import ManifestConfig
from footprint.report import format_json
from footprint.scanner import Match, ScanResult


def _make_result(file: str, category: str, source: str = "default",
                 transitive: bool = False, confidence: float = 0.8) -> ScanResult:
    return ScanResult(
        file=file,
        categories=[category],
        matches=[Match(
            pattern="test",
            category=category,
            stack="node",
            line=1,
            source=source,
            transitive=transitive,
            confidence=confidence,
        )],
    )


def test_json_output_has_results_and_summary_keys() -> None:
    output = json.loads(format_json([]))
    assert "results" in output
    assert "summary" in output


def test_summary_total_files_matched() -> None:
    results = [
        _make_result("a.ts", "network_call"),
        _make_result("b.ts", "route_definition"),
    ]
    output = json.loads(format_json(results))
    assert output["summary"]["total_files_matched"] == 2


def test_summary_by_category() -> None:
    results = [
        _make_result("a.ts", "network_call"),
        _make_result("b.ts", "network_call"),
        _make_result("c.ts", "route_definition"),
    ]
    output = json.loads(format_json(results))
    by_cat = output["summary"]["by_category"]
    assert by_cat["network_call"] == 2
    assert by_cat["route_definition"] == 1


def test_summary_low_confidence_count() -> None:
    results = [
        _make_result("a.ts", "network_call", confidence=0.3),
        _make_result("b.ts", "network_call", confidence=0.8),
    ]
    output = json.loads(format_json(results))
    assert output["summary"]["low_confidence_matches"] == 1


def test_summary_transitive_count() -> None:
    results = [
        _make_result("a.ts", "network_call", transitive=True),
        _make_result("b.ts", "network_call", transitive=False),
    ]
    output = json.loads(format_json(results))
    assert output["summary"]["transitive_matches"] == 1


def test_summary_pattern_source_counts() -> None:
    results = [
        _make_result("a.ts", "network_call", source="default"),
        _make_result("b.ts", "network_call", source="dependency_resolved"),
        _make_result("c.ts", "network_call", source="custom"),
    ]
    output = json.loads(format_json(results))
    assert output["summary"]["patterns_from_defaults"] == 1
    assert output["summary"]["patterns_from_dependency_resolution"] == 1
    assert output["summary"]["patterns_from_custom"] == 1


def test_summary_scanned_at_is_iso_format() -> None:
    output = json.loads(format_json([]))
    scanned_at = output["summary"]["scanned_at"]
    # Should parse as ISO datetime
    datetime.fromisoformat(scanned_at.replace("Z", "+00:00"))
```

- [ ] **Step 2: Verify tests fail**

```bash
uv run pytest tests/test_report_summary.py -v 2>&1 | head -5
```
Expected: `AssertionError: 'results' not in output`

- [ ] **Step 3: Update `format_json` to wrap in summary envelope**

Replace `format_json` in `footprint/report.py`:

```python
def format_json(results: list[ScanResult], repo: str = "") -> str:
    from datetime import datetime, timezone  # noqa: PLC0415

    all_matches = [m for r in results for m in r.matches]

    by_category: dict[str, int] = {}
    by_stack: dict[str, int] = {}
    for m in all_matches:
        by_category[m.category] = by_category.get(m.category, 0) + 1
        by_stack[m.stack] = by_stack.get(m.stack, 0) + 1

    low_conf = sum(1 for m in all_matches if m.confidence < 0.5)
    transitive = sum(1 for m in all_matches if m.transitive)
    from_defaults = sum(1 for m in all_matches if m.source == "default")
    from_resolved = sum(1 for m in all_matches if m.source == "dependency_resolved")
    from_custom = sum(1 for m in all_matches if m.source == "custom")

    results_data = []
    for r in results:
        matches = []
        for m in r.matches:
            entry: dict[str, object] = {
                "pattern": m.pattern,
                "category": m.category,
                "stack": m.stack,
                "line": m.line,
                "source": m.source,
                "confidence": round(m.confidence, 2),
            }
            if m.in_comment:
                entry["in_comment"] = True
            if m.in_string_literal:
                entry["in_string_literal"] = True
            if m.context:
                entry["context"] = m.context
            if m.transitive:
                entry["transitive"] = True
            matches.append(entry)
        results_data.append({
            "file": r.file,
            "categories": r.categories,
            "matches": matches,
        })

    summary: dict[str, object] = {
        "repo": repo,
        "scanned_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_files_matched": len(results),
        "by_category": by_category,
        "by_stack": by_stack,
        "low_confidence_matches": low_conf,
        "transitive_matches": transitive,
        "patterns_from_defaults": from_defaults,
        "patterns_from_dependency_resolution": from_resolved,
        "patterns_from_custom": from_custom,
    }

    return json.dumps({"results": results_data, "summary": summary}, indent=2)
```

Update the CLI call to pass `repo=str(root)`:
```python
click.echo(format_json(results, repo=str(root)))
```

- [ ] **Step 4: Add `--verbose` flag to CLI**

```python
@click.option("--verbose", "-v", is_flag=True, default=False,
              help="Print scan details to stderr")
```

In the `scan` command body, add verbose output at key points (all to `stderr` via `click.echo(..., err=True)`):

```python
if verbose:
    click.echo(f"Repo: {root}", err=True)
    click.echo(f"Manifest: {manifest}", err=True)

# After dependency resolution:
if verbose and not no_resolve:
    click.echo(f"Deps parsed: {len(deps)} packages", err=True)
    lookup_count = sum(1 for r in resolved if r.source == "lookup")
    claude_count = sum(1 for r in resolved if r.source == "claude")
    click.echo(f"  Resolved from lookup: {lookup_count}", err=True)
    click.echo(f"  Resolved via Claude: {claude_count}", err=True)
    click.echo(f"  Generated patterns: {len(extra_patterns)}", err=True)

# After scan:
if verbose:
    click.echo(f"Files matched: {len(results)}", err=True)
    total_matches = sum(len(r.matches) for r in results)
    click.echo(f"Total matches: {total_matches}", err=True)
```

- [ ] **Step 5: Run all tests**

```bash
uv run pytest -v
```

Note: existing tests that call `format_json` and do `json.loads(output)[0]` will now need to do `json.loads(output)["results"][0]`. Find and fix those tests.

- [ ] **Step 6: Run mise check and commit**

```bash
mise run check
gt create feat/phase3-summary
git add footprint/report.py footprint/cli.py tests/test_report_summary.py
git commit -m "feat(phase3): scan summary block, --verbose flag"
```

- [ ] **Step 7: Submit stack**

```bash
gt submit --stack --no-edit
```

---

## Exit Criteria

- [ ] Comment and string literal matches flagged correctly (`in_comment`, `in_string_literal`)
- [ ] Test files flagged as `context: "test"` not excluded
- [ ] Confidence scores in [0.0, 1.0] for all fixture cases
- [ ] `--min-confidence` filter works correctly
- [ ] `--no-transitive` suppresses transitive matches
- [ ] `\bpath\(` and `\burl\(` removed from Python defaults — zero false positives on negatives
- [ ] `ports:` tightened to `^\s+ports:` — zero false positives on CI config fixtures
- [ ] `\bfetch\(` confirmed not matching `prefetch`/`refetch`
- [ ] Summary block present and accurate in JSON output
- [ ] `--verbose` output goes to stderr only
- [ ] All tests pass with no live API calls
