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
    assert isinstance(data, list)


def test_format_json_structure() -> None:
    output = format_json(_make_results())
    data = json.loads(output)
    assert len(data) == 2
    assert data[0]["file"] == "src/services/api.ts"
    assert data[0]["categories"] == ["network_call"]
    assert len(data[0]["matches"]) == 1
    assert data[0]["matches"][0]["line"] == 1
    assert data[0]["matches"][0]["pattern"] == "import.*axios"
    assert data[0]["matches"][0]["category"] == "network_call"
    assert data[0]["matches"][0]["stack"] == "node"
    # pattern with backslash round-trips correctly through JSON serialisation
    assert data[1]["matches"][0]["pattern"] == r"(app|router)\.(get|post|put|patch|delete|use)\("


def test_format_json_empty_returns_empty_array() -> None:
    assert format_json([]) == "[]"


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
