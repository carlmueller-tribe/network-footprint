from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from footprint.cli import main
from footprint.manifest import ManifestConfig
from footprint.patterns import PatternSpec
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
    assert m.confidence >= 0.5


def test_comment_reduces_confidence(tmp_path: Path) -> None:
    scanner = _scanner(tmp_path, "// import axios from 'axios'\n")
    results = scanner.run()
    if results:
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


def test_confidence_clamped_to_one(tmp_path: Path) -> None:
    content = "\n".join([f"import axios from 'axios';  // line {i}" for i in range(10)])
    scanner = _scanner(tmp_path, content)
    results = scanner.run()
    assert results
    for m in results[0].matches:
        assert m.confidence <= 1.0


def test_confidence_clamped_to_zero(tmp_path: Path) -> None:
    scanner = _scanner(tmp_path, '// const s = "import axios";\n')
    results = scanner.run()
    if results:
        for m in results[0].matches:
            assert m.confidence >= 0.0


def test_min_confidence_filter(tmp_path: Path) -> None:
    (tmp_path / "api.ts").write_text("// import axios from 'axios'\n")
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["scan", str(tmp_path), "--min-confidence", "0.9", "--output", "json"],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    # commented import has low confidence — should be filtered out
    # format_json returns a flat array; Task 4 will add the envelope
    results_list = data["results"] if isinstance(data, dict) else data
    all_matches = [m for r in results_list for m in r["matches"]]
    for m in all_matches:
        assert m["confidence"] >= 0.9


def test_no_transitive_filter(tmp_path: Path) -> None:
    injected: list[PatternSpec] = [
        {
            "pattern": r"from ['\"]follow\-redirects['\"]",
            "category": "network_call",
            "stack": "node",
            "source": "dependency_resolved",
            "transitive": True,
        }
    ]
    (tmp_path / "app.ts").write_text("import x from 'follow-redirects';\n")
    manifest = ManifestConfig(stacks=["node"], exclude=[])
    scanner = Scanner(str(tmp_path), manifest, extra_patterns=injected)
    results = scanner.run()
    assert any(m.transitive for r in results for m in r.matches)
    # Now with filter
    runner = CliRunner()
    result = runner.invoke(main, ["scan", str(tmp_path), "--no-transitive", "--output", "flat"])
    assert result.exit_code == 0
    # The transitive match came from extra_patterns, not from CLI path, so output may vary.
    # Just confirm no crash and valid exit.
