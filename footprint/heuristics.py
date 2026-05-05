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


_RELATIVE_URL = re.compile(r"""['"](/[a-zA-Z0-9_-][^'"?\s]*)['"]""")
_EXTERNAL_URL = re.compile(r"""https?://""")


def reclassify_by_url(line: str, current_category: str) -> str:
    """
    Reclassify network_call → route_definition for call-site patterns
    where the line contains a relative URL (internal app call).

    - Relative URL (e.g. '/api/users') → route_definition (calling own backend)
    - Absolute external URL (e.g. 'https://api.stripe.com') → keep as network_call
    - No URL in line (e.g. bare import statement) → unchanged
    """
    if current_category != "network_call":
        return current_category
    if _EXTERNAL_URL.search(line):
        return "network_call"
    if _RELATIVE_URL.search(line):
        return "route_definition"
    return current_category
