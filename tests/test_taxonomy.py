from __future__ import annotations

from pathlib import Path

from footprint.heuristics import reclassify_by_url
from footprint.manifest import ManifestConfig
from footprint.scanner import Scanner

# --- reclassify_by_url unit tests ---


def test_relative_url_reclassified_to_route() -> None:
    assert reclassify_by_url("fetch('/api/users')", "network_call") == "route_definition"


def test_external_url_stays_network_call() -> None:
    result = reclassify_by_url("fetch('https://api.stripe.com/charge')", "network_call")
    assert result == "network_call"


def test_no_url_unchanged() -> None:
    assert reclassify_by_url("import axios from 'axios'", "network_call") == "network_call"


def test_route_definition_unchanged() -> None:
    result = reclassify_by_url("router.get('/users', handler)", "route_definition")
    assert result == "route_definition"


def test_telemetry_unchanged() -> None:
    assert reclassify_by_url("import sentry_sdk", "telemetry") == "telemetry"


# --- scanner integration tests ---


def test_fetch_with_relative_url_is_route_definition(tmp_path: Path) -> None:
    (tmp_path / "app.ts").write_text("const r = await fetch('/api/users');\n")
    scanner = Scanner(str(tmp_path), ManifestConfig(stacks=["node"], exclude=[]))
    results = scanner.run()
    assert results
    categories = {m.category for r in results for m in r.matches}
    assert "route_definition" in categories


def test_fetch_with_external_url_is_network_call(tmp_path: Path) -> None:
    (tmp_path / "app.ts").write_text(
        "const r = await fetch('https://api.stripe.com/v1/charges');\n"
    )
    scanner = Scanner(str(tmp_path), ManifestConfig(stacks=["node"], exclude=[]))
    results = scanner.run()
    assert results
    categories = {m.category for r in results for m in r.matches}
    assert "network_call" in categories
    assert "route_definition" not in categories


def test_sentry_import_is_telemetry(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("import sentry_sdk\nsentry_sdk.init(dsn='...')\n")
    scanner = Scanner(str(tmp_path), ManifestConfig(stacks=["python"], exclude=[]))
    results = scanner.run()
    assert results
    categories = {m.category for r in results for m in r.matches}
    assert "telemetry" in categories


def test_sentry_node_import_is_telemetry(tmp_path: Path) -> None:
    (tmp_path / "app.ts").write_text("import * as Sentry from '@sentry/node';\n")
    scanner = Scanner(str(tmp_path), ManifestConfig(stacks=["node"], exclude=[]))
    results = scanner.run()
    assert results
    categories = {m.category for r in results for m in r.matches}
    assert "telemetry" in categories


def test_anthropic_import_stays_network_call(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("from anthropic import Anthropic\n")
    scanner = Scanner(str(tmp_path), ManifestConfig(stacks=["python"], exclude=[]))
    results = scanner.run()
    assert results
    categories = {m.category for r in results for m in r.matches}
    assert "network_call" in categories
    assert "telemetry" not in categories
