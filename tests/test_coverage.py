from __future__ import annotations

import json

from footprint.coverage import _extract_paths, _normalise, analyze_coverage
from footprint.report import format_json
from footprint.scanner import Match, ScanResult

# --- unit tests for helpers ---


def test_extract_paths_single_quoted() -> None:
    paths = _extract_paths("client.get('/api/users')")
    assert "/api/users" in paths


def test_extract_paths_double_quoted() -> None:
    paths = _extract_paths('fetch("/health")')
    assert "/health" in paths


def test_extract_paths_full_url() -> None:
    paths = _extract_paths("requests.get('http://localhost:8000/api/users')")
    assert "/api/users" in paths


def test_extract_paths_no_path() -> None:
    paths = _extract_paths("import requests")
    assert paths == []


def test_normalise_strips_trailing_slash() -> None:
    assert _normalise("/users/") == "/users"


def test_normalise_lowercases() -> None:
    assert _normalise("/API/Users") == "/api/users"


# --- integration tests ---


def _route_result(file: str, paths: list[str], context: str = "") -> ScanResult:
    return ScanResult(
        file=file,
        categories=["route_definition"],
        matches=[
            Match(
                pattern="test-route",
                category="route_definition",
                stack="python",
                line=i + 1,
                line_content=f"@app.get('{p}')",
                context=context,
            )
            for i, p in enumerate(paths)
        ],
    )


def _test_result(file: str, paths: list[str]) -> ScanResult:
    return ScanResult(
        file=file,
        categories=["network_call"],
        matches=[
            Match(
                pattern="test-call",
                category="network_call",
                stack="python",
                line=i + 1,
                line_content=f"requests.get('http://localhost{p}')",
                context="test",
            )
            for i, p in enumerate(paths)
        ],
    )


def test_route_with_test_coverage_tagged_likely_active() -> None:
    results = [
        _route_result("routes.py", ["/health"]),
        _test_result("tests/test_api.py", ["/health"]),
    ]
    analyze_coverage(results)
    route_result = next(r for r in results if r.file == "routes.py")
    assert route_result.coverage == "likely_active"


def test_route_without_test_coverage_tagged_no_coverage() -> None:
    results = [
        _route_result("routes.py", ["/orphaned"]),
        _test_result("tests/test_api.py", ["/health"]),
    ]
    analyze_coverage(results)
    route_result = next(r for r in results if r.file == "routes.py")
    assert route_result.coverage == "no_test_coverage"


def test_multiple_routes_mixed_coverage() -> None:
    results = [
        _route_result("routes.py", ["/health", "/orphaned"]),
        _test_result("tests/test_api.py", ["/health"]),
    ]
    analyze_coverage(results)
    route_result = next(r for r in results if r.file == "routes.py")
    # /health is covered — file is likely_active even if /orphaned isn't
    assert route_result.coverage == "likely_active"


def test_mock_router_in_test_file_counts_as_evidence() -> None:
    """Test files using @router.get() decorator-style route definitions (not HTTP calls)
    should still count as coverage evidence — mirrors real usage like test_openapi_inventory.py."""
    prod_route = _route_result("app/health.py", ["/health"])
    # test file defines a mock router — category is route_definition, context is test
    mock_route_match = Match(
        pattern="test-route",
        category="route_definition",
        stack="python",
        line=44,
        line_content='@public_router.get("/health")',
        context="test",
    )
    test_file = ScanResult(
        file="tests/test_openapi_inventory.py",
        categories=["route_definition"],
        matches=[mock_route_match],
    )
    results = [prod_route, test_file]
    analyze_coverage(results)
    assert prod_route.coverage == "likely_active"


def test_no_test_files_gives_no_test_coverage() -> None:
    results = [_route_result("routes.py", ["/health"])]
    analyze_coverage(results)
    assert results[0].coverage == "no_test_coverage"


def test_test_file_itself_not_tagged() -> None:
    results = [
        _test_result("tests/test_api.py", ["/health"]),
    ]
    analyze_coverage(results)
    assert results[0].coverage == ""


def test_network_call_file_not_tagged() -> None:
    results = [
        ScanResult(
            file="client.py",
            categories=["network_call"],
            matches=[
                Match(
                    pattern="import requests",
                    category="network_call",
                    stack="python",
                    line=1,
                    line_content="import requests",
                )
            ],
        )
    ]
    analyze_coverage(results)
    assert results[0].coverage == ""


def test_json_output_includes_coverage() -> None:
    results = [_route_result("routes.py", ["/health"])]
    results[0].coverage = "likely_active"
    data = json.loads(format_json(results))
    route = next(r for r in data["results"] if r["file"] == "routes.py")
    assert route["coverage"] == "likely_active"


def test_json_omits_coverage_when_empty() -> None:
    results = [_route_result("client.py", [])]
    results[0].coverage = ""
    data = json.loads(format_json(results))
    assert "coverage" not in data["results"][0]
