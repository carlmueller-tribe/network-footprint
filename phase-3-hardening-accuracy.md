# Network Footprint Scanner — Phase 3: Hardening & Accuracy

## Goal
Reduce noise, improve signal quality, and make the output trustworthy enough to hand directly to Claude or Kirkland without manual filtering. Add confidence scoring, false positive suppression, and a test suite validated against real repos.

---

## Deliverables

### 1. False Positive Suppression

The main sources of noise from Phases 1 & 2:

**Comments**
Lines where the match occurs inside a comment should be suppressed or downgraded.

```python
def is_comment(line: str, stack: str) -> bool:
    stripped = line.strip()
    if stack in ("node", "ts"):
        return stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*")
    if stack == "python":
        return stripped.startswith("#")
    return False
```

Tag comment matches as `in_comment: true` rather than removing them entirely — still useful context, but flagged.

**String literals**
Matches inside string literals (e.g. documentation strings, error messages referencing a URL) should be flagged similarly.

```python
# Heuristic: line contains a match but is majority-quoted content
def likely_string_literal(line: str, match_pos: int) -> bool: ...
```

**Test files**
Files matching test patterns should be flagged `context: "test"` rather than excluded — test files hitting real endpoints is relevant information.

Default test patterns:
```python
TEST_PATTERNS = [
    r"\.test\.(ts|tsx|js|jsx)$",
    r"\.spec\.(ts|tsx|js|jsx|py)$",
    r"tests?/",
    r"__tests__/",
    r"test_.*\.py$",
]
```

Configurable via manifest:
```yaml
test_patterns:
  - "**/*.test.ts"
  - "tests/**"
```

---

### 2. Confidence Scoring

Each match gets a `confidence` score from 0.0–1.0 based on heuristics:

| Signal | Effect |
|--------|--------|
| Match is in a comment | -0.4 |
| Match is in a string literal | -0.3 |
| Match is in a test file | -0.1 |
| Match is a route definition (high signal) | +0.2 |
| Match is from dependency_resolved source | +0.1 |
| Multiple matches in same file | +0.1 per additional match (capped at +0.3) |

Base confidence: `0.7`

Clamp final score to `[0.0, 1.0]`.

**CLI filter flag:**
```bash
footprint scan ./repo --min-confidence 0.5
```

Default: include all matches (no filter), but show confidence in output.

---

### 3. Noisy Pattern Audit

Review the default pattern packs from Phase 1 for patterns that generate excessive false positives in practice. Specific candidates to tighten:

- `\bpath\(` — very common in non-routing Python code (filesystem operations). Add negative lookahead or require Django/Flask import in same file.
- `\burl\(` — similarly overloaded. Consider removing from defaults and only activating when Django is a resolved dependency.
- `ports:` in YAML — appears in many non-network devops contexts. Narrow to `^\s+ports:` with a numeric value on the next line.
- `fetch\(` — consider requiring it to be at statement start or preceded by `await`.

Update `patterns.py` with tightened regexes and document the rationale for each change.

---

### 4. Test Suite

**Structure:**
```
tests/
├── fixtures/
│   ├── node-repo/          # minimal fake Node repo with known network files
│   ├── python-repo/        # minimal fake Python repo
│   ├── mixed-repo/         # polyglot repo
│   └── devops-repo/        # infra-only repo
├── test_scanner.py
├── test_manifest.py
├── test_resolver.py
├── test_patterns.py
└── test_report.py
```

**Fixture repos** contain:
- Files that SHOULD be detected (ground truth positives)
- Files that should NOT be detected (ground truth negatives)
- Edge cases: commented-out imports, string literals containing package names, test files

**Test coverage requirements:**
- All default patterns have at least one positive fixture and one negative fixture
- Exclude patterns correctly suppress files
- Manifest overrides (add/remove patterns, import name overrides) work correctly
- Claude classifier is mocked in tests — no live API calls
- Confidence scoring produces expected values for fixture matches
- CLI produces valid JSON and flat output for fixture repos

---

### 5. Transitive Dependency Handling

Phase 2 surfaces transitive deps but doesn't deeply analyze them. Phase 3 adds:

- A `--no-transitive` flag to suppress transitive dep patterns entirely
- Transitive matches are included by default but labeled `transitive: true` in output
- Summary section in output listing which transitive packages generated matches (useful for the Kirkland report)

---

### 6. Scan Summary Block

Append a summary object to JSON output:

```json
{
  "results": [ ... ],
  "summary": {
    "repo": "/path/to/repo",
    "scanned_at": "2026-05-03T08:00:00Z",
    "total_files_scanned": 412,
    "total_files_matched": 38,
    "by_category": {
      "route_definition": 12,
      "network_call": 22,
      "devops": 8
    },
    "by_stack": {
      "node": 18,
      "python": 14,
      "devops": 8
    },
    "low_confidence_matches": 5,
    "transitive_matches": 3,
    "patterns_from_dependency_resolution": 14,
    "patterns_from_defaults": 42,
    "patterns_from_custom": 2
  }
}
```

---

### 7. `--verbose` CLI Flag

```bash
footprint scan ./repo --verbose
```

Prints to stderr (not stdout, so it doesn't pollute piped output):
- Which manifest files were found and parsed
- Which packages were resolved from lookup table vs Claude
- Pattern count per stack
- Files excluded and why
- Scan duration

---

## Exit Criteria
- [ ] Comment and string literal matches flagged correctly in fixture tests
- [ ] Test files flagged as `context: "test"` not excluded
- [ ] Confidence scores match expected values for all fixture cases
- [ ] `--min-confidence` filter works correctly
- [ ] Noisy patterns (`path(`, `url(`, `ports:`, `fetch(`) produce zero false positives on fixture negatives
- [ ] Test suite passes with mocked Claude — no live API dependency in CI
- [ ] Summary block present and accurate in JSON output
- [ ] `--verbose` output goes to stderr only
- [ ] 90%+ precision on fixture ground truth (low false positives)
- [ ] 95%+ recall on fixture ground truth (low false negatives)
