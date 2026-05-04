import json

from footprint.report import format_flat, format_json
from footprint.scanner import Match, ScanResult


def _make_results() -> list[ScanResult]:
    return [
        ScanResult(
            file="src/services/api.ts",
            categories=["network_call"],
            matches=[
                Match(
                    pattern="import.*axios",
                    category="network_call",
                    stack="node",
                    line=1,
                )
            ],
        ),
        ScanResult(
            file="src/routes/users.ts",
            categories=["route_definition"],
            matches=[
                Match(
                    pattern=r"(app|router)\.(get|post|put|patch|delete|use)\(",
                    category="route_definition",
                    stack="node",
                    line=5,
                )
            ],
        ),
    ]


def test_format_json_is_valid_json() -> None:
    output = format_json(_make_results())
    data = json.loads(output)
    assert isinstance(data, dict)
    assert "results" in data


def test_format_json_structure() -> None:
    output = format_json(_make_results())
    data = json.loads(output)
    results = data["results"]
    assert len(results) == 2
    assert results[0]["file"] == "src/services/api.ts"
    assert results[0]["categories"] == ["network_call"]
    assert len(results[0]["matches"]) == 1
    assert results[0]["matches"][0]["line"] == 1
    assert results[0]["matches"][0]["pattern"] == "import.*axios"
    assert results[0]["matches"][0]["category"] == "network_call"
    assert results[0]["matches"][0]["stack"] == "node"
    # pattern with backslash round-trips correctly through JSON serialisation
    assert results[1]["matches"][0]["pattern"] == r"(app|router)\.(get|post|put|patch|delete|use)\("


def test_format_json_empty_returns_empty_array() -> None:
    data = json.loads(format_json([]))
    assert data["results"] == []


def test_format_flat_one_file_per_line() -> None:
    output = format_flat(_make_results())
    lines = output.splitlines()
    assert lines == ["src/services/api.ts", "src/routes/users.ts"]


def test_format_flat_empty_returns_empty_string() -> None:
    assert format_flat([]) == ""


def test_format_flat_preserves_order() -> None:
    results = _make_results()
    output = format_flat(results)
    lines = output.splitlines()
    assert lines[0] == results[0].file
    assert lines[1] == results[1].file
