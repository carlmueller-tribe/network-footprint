from __future__ import annotations

import json

from footprint.report import format_json
from footprint.scanner import Match, ScanResult


def test_json_includes_source_field() -> None:
    results = [
        ScanResult(
            file="src/api.ts",
            categories=["network_call"],
            matches=[
                Match(
                    pattern=r"from ['\"]stripe['\"]",
                    category="network_call",
                    stack="node",
                    line=1,
                    source="dependency_resolved",
                )
            ],
        )
    ]
    output = json.loads(format_json(results))
    assert output[0]["matches"][0]["source"] == "dependency_resolved"


def test_json_includes_transitive_field_when_true() -> None:
    results = [
        ScanResult(
            file="src/app.ts",
            categories=["network_call"],
            matches=[
                Match(
                    pattern=r"from ['\"]follow-redirects['\"]",
                    category="network_call",
                    stack="node",
                    line=2,
                    source="dependency_resolved",
                    transitive=True,
                )
            ],
        )
    ]
    output = json.loads(format_json(results))
    assert output[0]["matches"][0]["transitive"] is True


def test_json_omits_transitive_when_false() -> None:
    results = [
        ScanResult(
            file="src/api.ts",
            categories=["network_call"],
            matches=[
                Match(
                    pattern="import requests",
                    category="network_call",
                    stack="python",
                    line=1,
                    source="default",
                )
            ],
        )
    ]
    output = json.loads(format_json(results))
    match = output[0]["matches"][0]
    assert "transitive" not in match
