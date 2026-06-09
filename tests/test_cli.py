import json
from pathlib import Path

from click.testing import CliRunner

from footprint.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def test_scan_json_output_is_valid() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["scan", str(FIXTURES / "node-repo"), "--output", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) > 0


def test_scan_flat_output_one_per_line() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["scan", str(FIXTURES / "node-repo"), "--output", "flat"])
    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    assert len(lines) > 0
    assert all(
        line.endswith((".ts", ".js", ".tsx", ".py", ".yml", ".yaml")) or "Dockerfile" in line
        for line in lines
    )


def test_scan_nonexistent_repo_exits_nonzero() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["scan", "/no/such/path"])
    assert result.exit_code != 0


def test_scan_invalid_manifest_exits_nonzero() -> None:
    runner = CliRunner()
    result = runner.invoke(
        main, ["scan", str(FIXTURES / "node-repo"), "--manifest", "/no/such.yaml"]
    )
    assert result.exit_code != 0


def test_scan_flat_empty_no_blank_line() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("empty-repo").mkdir()
        result = runner.invoke(main, ["scan", "empty-repo", "--output", "flat"])
    assert result.exit_code == 0
    assert result.output == ""


def test_scan_python_repo_categories() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["scan", str(FIXTURES / "python-repo")])
    assert result.exit_code == 0
    data = json.loads(result.output)
    routes_file = next((r for r in data if "routes.py" in r["file"]), None)
    assert routes_file is not None
    assert "route_definition" in routes_file["categories"]
    assert "network_call" in routes_file["categories"]
