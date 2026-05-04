from __future__ import annotations

from pathlib import Path

from footprint.resolver import (
    parse_all,
    parse_cargo_toml,
    parse_go_mod,
    parse_package_json,
    parse_package_lock_json,
    parse_pipfile,
    parse_pyproject_toml,
    parse_requirements_txt,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "deps"


def test_parse_package_json_direct_deps() -> None:
    deps = parse_package_json(FIXTURE_DIR / "package.json")
    names = [d.name for d in deps]
    assert "axios" in names
    assert "express" in names
    assert "stripe" in names


def test_parse_package_json_excludes_dev_deps() -> None:
    deps = parse_package_json(FIXTURE_DIR / "package.json")
    names = [d.name for d in deps]
    assert "typescript" not in names


def test_parse_package_json_ecosystem() -> None:
    deps = parse_package_json(FIXTURE_DIR / "package.json")
    assert all(d.ecosystem == "node" for d in deps)
    assert all(not d.transitive for d in deps)


def test_parse_package_lock_transitive() -> None:
    deps = parse_package_lock_json(FIXTURE_DIR / "package-lock.json")
    names = [d.name for d in deps]
    assert "follow-redirects" in names
    transitive = [d for d in deps if d.name == "follow-redirects"]
    assert transitive[0].transitive is True


def test_parse_requirements_txt() -> None:
    deps = parse_requirements_txt(FIXTURE_DIR / "requirements.txt")
    names = [d.name for d in deps]
    assert "requests" in names
    assert "httpx" in names
    assert "pillow" in names
    assert "numpy" in names


def test_parse_requirements_txt_skips_comments() -> None:
    deps = parse_requirements_txt(FIXTURE_DIR / "requirements.txt")
    assert not any(d.name.startswith("#") for d in deps)


def test_parse_requirements_txt_strips_version_specifiers() -> None:
    deps = parse_requirements_txt(FIXTURE_DIR / "requirements.txt")
    names = [d.name for d in deps]
    assert "requests" in names
    assert not any("==" in n for n in names)


def test_parse_pyproject_toml() -> None:
    deps = parse_pyproject_toml(FIXTURE_DIR / "pyproject.toml")
    names = [d.name for d in deps]
    assert "fastapi" in names
    assert "anthropic" in names
    assert "python-dotenv" in names


def test_parse_pipfile() -> None:
    deps = parse_pipfile(FIXTURE_DIR / "Pipfile")
    names = [d.name for d in deps]
    assert "flask" in names
    assert "boto3" in names
    assert "requests" in names


def test_parse_pipfile_excludes_dev() -> None:
    deps = parse_pipfile(FIXTURE_DIR / "Pipfile")
    names = [d.name for d in deps]
    assert "pytest" not in names


def test_parse_go_mod() -> None:
    deps = parse_go_mod(FIXTURE_DIR / "go.mod")
    names = [d.name for d in deps]
    assert "github.com/gin-gonic/gin" in names
    assert "github.com/go-resty/resty/v2" in names


def test_parse_go_mod_ecosystem() -> None:
    deps = parse_go_mod(FIXTURE_DIR / "go.mod")
    assert all(d.ecosystem == "go" for d in deps)


def test_parse_cargo_toml() -> None:
    deps = parse_cargo_toml(FIXTURE_DIR / "Cargo.toml")
    names = [d.name for d in deps]
    assert "reqwest" in names
    assert "tokio" in names
    assert "serde" in names


def test_parse_cargo_toml_ecosystem() -> None:
    deps = parse_cargo_toml(FIXTURE_DIR / "Cargo.toml")
    assert all(d.ecosystem == "rust" for d in deps)


def test_parser_tolerates_missing_file() -> None:
    deps = parse_requirements_txt(FIXTURE_DIR / "nonexistent.txt")
    assert deps == []


def test_parse_all_combines_available_files() -> None:
    deps = parse_all(FIXTURE_DIR)
    ecosystems = {d.ecosystem for d in deps}
    assert "node" in ecosystems
    assert "python" in ecosystems


def test_parse_all_empty_dir(tmp_path: Path) -> None:
    deps = parse_all(tmp_path)
    assert deps == []
