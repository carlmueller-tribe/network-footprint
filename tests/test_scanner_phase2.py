from __future__ import annotations

from pathlib import Path

from footprint.manifest import ManifestConfig
from footprint.patterns import PatternSpec
from footprint.scanner import Scanner


def test_injected_pattern_produces_match(tmp_path: Path) -> None:
    (tmp_path / "app.ts").write_text("import stripe from 'stripe';\n")
    injected: list[PatternSpec] = [
        {
            "pattern": r"from ['\"]stripe['\"]",
            "category": "network_call",
            "stack": "node",
            "source": "dependency_resolved",
        }
    ]
    manifest = ManifestConfig(stacks=["node"], exclude=[])
    scanner = Scanner(str(tmp_path), manifest, extra_patterns=injected)
    results = scanner.run()
    assert len(results) == 1
    match = results[0].matches[0]
    assert match.source == "dependency_resolved"


def test_default_pattern_tagged_default(tmp_path: Path) -> None:
    (tmp_path / "api.ts").write_text("import axios from 'axios';\n")
    manifest = ManifestConfig(stacks=["node"], exclude=[])
    scanner = Scanner(str(tmp_path), manifest)
    results = scanner.run()
    assert len(results) == 1
    for m in results[0].matches:
        assert m.source == "default"


def test_transitive_match_flagged(tmp_path: Path) -> None:
    (tmp_path / "app.ts").write_text("import x from 'follow-redirects';\n")
    injected: list[PatternSpec] = [
        {
            "pattern": r"from ['\"]follow\-redirects['\"]",
            "category": "network_call",
            "stack": "node",
            "source": "dependency_resolved",
            "transitive": True,
        }
    ]
    manifest = ManifestConfig(stacks=["node"], exclude=[])
    scanner = Scanner(str(tmp_path), manifest, extra_patterns=injected)
    results = scanner.run()
    assert len(results) == 1
    assert results[0].matches[0].transitive is True


def test_remove_override_suppresses_pattern(tmp_path: Path) -> None:
    (tmp_path / "urls.py").write_text("result = url('home', views.home)\n")
    manifest = ManifestConfig(stacks=["python"], exclude=[])
    scanner = Scanner(str(tmp_path), manifest, remove_patterns=[r"\burl\("])
    results = scanner.run()
    assert results == [] or not any(m.pattern == r"\burl\(" for r in results for m in r.matches)


def test_custom_pattern_tagged_custom(tmp_path: Path) -> None:
    (tmp_path / "client.ts").write_text("myInternalClient('https://api.example.com');\n")
    injected: list[PatternSpec] = [
        {
            "pattern": r"myInternalClient\(",
            "category": "network_call",
            "stack": "node",
            "source": "custom",
        }
    ]
    manifest = ManifestConfig(stacks=["node"], exclude=[])
    scanner = Scanner(str(tmp_path), manifest, extra_patterns=injected)
    results = scanner.run()
    assert len(results) == 1
    assert results[0].matches[0].source == "custom"
