from pathlib import Path

from footprint.manifest import ManifestConfig
from footprint.scanner import Scanner

FIXTURES = Path(__file__).parent / "fixtures"


def test_detects_axios_import_as_network_call() -> None:
    manifest = ManifestConfig(stacks=["node"], exclude=["node_modules"])
    results = Scanner(str(FIXTURES / "node-repo"), manifest).run()
    files = [r.file for r in results]
    assert any("api.ts" in f for f in files), f"Expected api.ts in results, got: {files}"


def test_detects_router_methods_as_route_definition() -> None:
    manifest = ManifestConfig(stacks=["node"], exclude=["node_modules"])
    results = Scanner(str(FIXTURES / "node-repo"), manifest).run()
    route_results = [r for r in results if "route_definition" in r.categories]
    assert route_results, "Expected at least one route_definition result"
    route_files = [r.file for r in route_results]
    assert any("users.ts" in f for f in route_files)


def test_utility_file_not_matched() -> None:
    manifest = ManifestConfig(stacks=["node"], exclude=["node_modules"])
    results = Scanner(str(FIXTURES / "node-repo"), manifest).run()
    files = [r.file for r in results]
    assert not any("strings.ts" in f for f in files), (
        f"strings.ts should not be matched but appeared in: {files}"
    )


def test_python_repo_detects_route_and_network() -> None:
    manifest = ManifestConfig(stacks=["python"], exclude=[])
    results = Scanner(str(FIXTURES / "python-repo"), manifest).run()
    assert results, "Expected matches in python fixture repo"
    all_categories = {c for r in results for c in r.categories}
    assert "route_definition" in all_categories
    assert "network_call" in all_categories


def test_python_utility_file_not_matched() -> None:
    manifest = ManifestConfig(stacks=["python"], exclude=[])
    results = Scanner(str(FIXTURES / "python-repo"), manifest).run()
    files = [r.file for r in results]
    assert not any("utils.py" in f for f in files)


def test_devops_files_scanned_regardless_of_stack() -> None:
    manifest = ManifestConfig(stacks=["node"], exclude=[])
    results = Scanner(str(FIXTURES / "devops-repo"), manifest).run()
    assert results, "Expected devops-repo files to be scanned even with node-only stack"
    files = [r.file for r in results]
    assert any("docker-compose" in f for f in files)


def test_stack_filtering_python_only_skips_ts_files() -> None:
    manifest = ManifestConfig(stacks=["python"], exclude=[])
    results = Scanner(str(FIXTURES / "node-repo"), manifest).run()
    ts_results = [r for r in results if r.file.endswith(".ts")]
    assert not ts_results, f"Python-only stack should not scan .ts files, got: {ts_results}"


def test_exclude_pattern_suppresses_files() -> None:
    manifest = ManifestConfig(stacks=["node", "python"], exclude=["src"])
    results = Scanner(str(FIXTURES / "node-repo"), manifest).run()
    assert all("src" not in r.file for r in results), "Files under 'src/' should be excluded"


def test_scan_result_categories_are_deduplicated() -> None:
    manifest = ManifestConfig(stacks=["python"], exclude=[])
    results = Scanner(str(FIXTURES / "python-repo"), manifest).run()
    for r in results:
        assert len(r.categories) == len(set(r.categories)), (
            f"Duplicate categories in {r.file}: {r.categories}"
        )


def test_match_has_required_fields() -> None:
    manifest = ManifestConfig(stacks=["node"], exclude=[])
    results = Scanner(str(FIXTURES / "node-repo"), manifest).run()
    assert results, "Need at least one result to test Match fields"
    match = results[0].matches[0]
    assert isinstance(match.pattern, str)
    assert match.category in ("route_definition", "network_call", "devops", "telemetry")
    assert match.stack in ("node", "python", "devops")
    assert isinstance(match.line, int)
    assert match.line >= 1


def test_scan_result_file_is_relative_path() -> None:
    manifest = ManifestConfig(stacks=["node"], exclude=[])
    results = Scanner(str(FIXTURES / "node-repo"), manifest).run()
    for r in results:
        assert not r.file.startswith("/"), f"Expected relative path, got absolute: {r.file}"


def test_dockerfile_scanned_as_devops() -> None:
    manifest = ManifestConfig(stacks=["python"], exclude=[])
    results = Scanner(str(FIXTURES / "devops-repo"), manifest).run()
    files = [r.file for r in results]
    assert any("Dockerfile" in f for f in files), f"Expected Dockerfile in results, got: {files}"


def test_devops_patterns_do_not_match_ts_files() -> None:
    manifest = ManifestConfig(stacks=["node"], exclude=[])
    results = Scanner(str(FIXTURES / "node-repo"), manifest).run()
    for r in results:
        assert "devops" not in r.categories, (
            f"devops category should not appear in node file {r.file}: {r.categories}"
        )
