from __future__ import annotations

import re

_TEST_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\.test\.(ts|tsx|js|jsx)$"),
    re.compile(r"\.spec\.(ts|tsx|js|jsx|py)$"),
    re.compile(r"(^|/)tests?/"),
    re.compile(r"(^|/)__tests__/"),
    re.compile(r"(^|/)test_[^/]+\.py$"),
]


def is_comment(line: str, stack: str) -> bool:
    """Return True if the line appears to be a comment."""
    stripped = line.strip()
    if stack in ("node", "ts"):
        return stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*")
    if stack == "python":
        return stripped.startswith("#")
    return False


def is_string_literal(line: str, match_pos: int) -> bool:
    """Heuristic: return True if match_pos falls inside a string literal."""
    before = line[:match_pos]
    single = before.count("'") - before.count("\\'")
    double = before.count('"') - before.count('\\"')
    return (single % 2 == 1) or (double % 2 == 1)


def is_test_file(path: str) -> bool:
    """Return True if the file path matches known test file patterns."""
    return any(p.search(path) is not None for p in _TEST_PATTERNS)
