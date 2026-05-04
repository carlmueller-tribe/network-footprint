from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from footprint.resolver import ParsedDep, ResolvedPackage, generate_patterns, resolve_packages


def test_claude_failed_package_gets_unknown_package_source() -> None:
    deps = [ParsedDep(name="some-obscure-pkg", ecosystem="node")]
    with patch("footprint.resolver._classify_with_claude", side_effect=RuntimeError("no auth")):
        results = resolve_packages(deps)
    r = next(r for r in results if r.package == "some-obscure-pkg")
    assert r.source == "unknown_package"
    assert r.network_capable is True


def test_unrecognised_package_generates_patterns() -> None:
    pkg = ResolvedPackage(
        package="mystery-sdk",
        import_name="mystery-sdk",
        network_capable=True,
        category="network_call",
        source="unknown_package",
    )
    patterns = generate_patterns([pkg], ecosystem="node")
    assert len(patterns) > 0
    assert all(p.get("source") == "unknown_package" for p in patterns)


def test_unknown_package_pattern_tagged_correctly() -> None:
    pkg = ResolvedPackage(
        package="mystery-sdk",
        import_name="mystery-sdk",
        network_capable=True,
        category="network_call",
        source="unknown_package",
    )
    patterns = generate_patterns([pkg], ecosystem="python")
    assert any("mystery" in p["pattern"] for p in patterns)
    assert all(p["source"] == "unknown_package" for p in patterns)


def test_known_package_still_gets_dependency_resolved_source() -> None:
    pkg = ResolvedPackage(
        package="axios",
        import_name="axios",
        network_capable=True,
        category="network_call",
        source="lookup",
    )
    patterns = generate_patterns([pkg], ecosystem="node")
    assert all(p.get("source") == "dependency_resolved" for p in patterns)


def test_confidence_penalty_for_unknown_package(tmp_path: Path) -> None:
    from footprint.manifest import ManifestConfig
    from footprint.patterns import PatternSpec
    from footprint.scanner import Scanner

    (tmp_path / "app.ts").write_text("import mystery from 'mystery-sdk';\n")
    injected: list[PatternSpec] = [
        {
            "pattern": r"from ['\"]mystery\-sdk['\"]",
            "category": "network_call",
            "stack": "node",
            "source": "unknown_package",
        }
    ]
    scanner = Scanner(
        str(tmp_path),
        ManifestConfig(stacks=["node"], exclude=[]),
        extra_patterns=injected,
    )
    results = scanner.run()
    if results:
        unknown_matches = [m for r in results for m in r.matches if m.source == "unknown_package"]
        for m in unknown_matches:
            assert m.confidence < 0.6  # penalised below base
