from __future__ import annotations

import re

from footprint.scanner import ScanResult

# Patterns to extract URL path literals from source lines
# Matches quoted strings that start with /  e.g. '/api/users', "/health"
_PATH_PATTERN = re.compile(r"""['"](/[^'"?\s]*)['"]""")

# Also match common test client call patterns like:
# client.get("/api/users"), requests.get("http://localhost/api/users")
_URL_PATTERN = re.compile(r"""https?://[^/'"]+(/[^'"?\s]*)""")


def _extract_paths(line: str) -> list[str]:
    """Extract URL path segments from a source line."""
    paths: list[str] = []
    for m in _PATH_PATTERN.finditer(line):
        paths.append(_normalise(m.group(1)))
    for m in _URL_PATTERN.finditer(line):
        paths.append(_normalise(m.group(1)))
    return paths


def _normalise(path: str) -> str:
    """Normalise a path for comparison: lowercase, strip trailing slash."""
    return path.rstrip("/").lower() or "/"


def _paths_overlap(route_paths: list[str], evidence_paths: list[str]) -> bool:
    """
    Return True if any evidence path matches or contains a route path.
    Uses substring matching so /users matches /users/123 and vice-versa.
    """
    for rp in route_paths:
        for ep in evidence_paths:
            if rp in ep or ep in rp:
                return True
    return False


def analyze_coverage(results: list[ScanResult]) -> None:
    """
    Mutate ScanResult.coverage in-place.

    Only sets coverage on results that contain route_definition matches
    in non-test files. Test files and pure network_call files are left
    with coverage="".
    """
    # Collect all URL paths seen in test-file network calls
    evidence_paths: list[str] = []
    for r in results:
        for m in r.matches:
            if m.context == "test" and m.category == "network_call":
                evidence_paths.extend(_extract_paths(m.line_content))

    # Tag route-definition results in non-test files
    for r in results:
        is_route_file = "route_definition" in r.categories
        is_test = any(m.context == "test" for m in r.matches)
        if not is_route_file or is_test:
            continue

        route_paths: list[str] = []
        for m in r.matches:
            if m.category == "route_definition":
                route_paths.extend(_extract_paths(m.line_content))

        if not evidence_paths:
            # No test calls at all in the codebase — can't determine coverage
            r.coverage = "no_test_coverage"
        elif route_paths and _paths_overlap(route_paths, evidence_paths):
            r.coverage = "likely_active"
        else:
            r.coverage = "no_test_coverage"
