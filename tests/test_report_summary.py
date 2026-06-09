from __future__ import annotations

import json
from datetime import datetime

from footprint.report import format_json
from footprint.scanner import Match, ScanResult


def _make_result(
    file: str,
    category: str,
    source: str = "default",
    transitive: bool = False,
    confidence: float = 0.8,
) -> ScanResult:
    return ScanResult(
        file=file,
        categories=[category],
        matches=[
            Match(
                pattern="test",
                category=category,
                stack="node",
                line=1,
                source=source,
                transitive=transitive,
                confidence=confidence,
            )
        ],
    )


def test_json_output_has_results_and_summary_keys() -> None:
    output = json.loads(format_json([]))
    assert "results" in output
    assert "summary" in output


def test_summary_total_files_matched() -> None:
    results = [_make_result("a.ts", "network_call"), _make_result("b.ts", "route_definition")]
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
        _make_result("b.ts", "network_call"),
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


def test_summary_scanned_at_parseable() -> None:
    output = json.loads(format_json([]))
    scanned_at = output["summary"]["scanned_at"]
    datetime.fromisoformat(scanned_at.replace("Z", "+00:00"))
