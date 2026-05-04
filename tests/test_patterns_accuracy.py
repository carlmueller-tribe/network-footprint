from __future__ import annotations

from pathlib import Path

from footprint.manifest import ManifestConfig
from footprint.scanner import Scanner

NEGATIVES_DIR = Path(__file__).parent / "fixtures" / "fp-negatives"
POSITIVES_DIR = Path(__file__).parent / "fixtures" / "fp-positives"


def _matched_patterns(path: Path, stacks: list[str]) -> list[str]:
    """Return matched pattern strings for a single file."""
    scanner = Scanner(str(path.parent), ManifestConfig(stacks=stacks, exclude=[]))
    results = scanner.run()
    target = next((r for r in results if r.file == path.name), None)
    return [m.pattern for m in target.matches] if target else []


def test_path_false_positive_not_matched() -> None:
    patterns = _matched_patterns(NEGATIVES_DIR / "path_false_positives.py", ["python"])
    route_pats = [p for p in patterns if "path" in p.lower()]
    assert route_pats == [], f"False positives from path( pattern: {route_pats}"


def test_url_false_positive_not_matched_as_route() -> None:
    patterns = _matched_patterns(NEGATIVES_DIR / "url_false_positives.py", ["python"])
    url_pats = [p for p in patterns if r"\burl\(" in p]
    assert url_pats == [], f"False positives from url( pattern: {url_pats}"


def test_ports_false_positive_not_matched() -> None:
    patterns = _matched_patterns(NEGATIVES_DIR / "ports_false_positives.yml", ["devops"])
    ports_pats = [p for p in patterns if "ports" in p]
    assert ports_pats == [], f"False positives from ports: pattern: {ports_pats}"


def test_fetch_false_positive_not_matched() -> None:
    patterns = _matched_patterns(NEGATIVES_DIR / "fetch_false_positives.ts", ["node"])
    fetch_pats = [p for p in patterns if "fetch" in p.lower()]
    assert fetch_pats == [], f"False positives from fetch pattern: {fetch_pats}"


def test_real_flask_routes_detected() -> None:
    patterns = _matched_patterns(POSITIVES_DIR / "real_routes.py", ["python"])
    assert len(patterns) > 0, "Expected route matches in real_routes.py"


def test_real_axios_network_detected() -> None:
    patterns = _matched_patterns(POSITIVES_DIR / "real_network.ts", ["node"])
    assert len(patterns) > 0, "Expected network matches in real_network.ts"


def test_real_fetch_detected() -> None:
    patterns = _matched_patterns(POSITIVES_DIR / "real_fetch.ts", ["node"])
    fetch_pats = [p for p in patterns if "fetch" in p.lower()]
    assert len(fetch_pats) > 0, "Expected fetch( to match real_fetch.ts"
