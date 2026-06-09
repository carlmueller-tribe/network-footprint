from __future__ import annotations

from footprint.report import format_markdown
from footprint.scanner import Match, ScanResult


def _result(
    file: str, category: str, line: int, snippet: str, transitive: bool = False
) -> ScanResult:
    return ScanResult(
        file=file,
        categories=[category],
        matches=[
            Match(
                pattern="test",
                category=category,
                stack="node",
                line=line,
                source="default",
                transitive=transitive,
                line_content=snippet,
            )
        ],
    )


def test_markdown_contains_file_path() -> None:
    results = [_result("src/api.ts", "network_call", 2, "import axios from 'axios'")]
    md = format_markdown(results)
    assert "src/api.ts" in md


def test_markdown_contains_snippet() -> None:
    results = [_result("src/api.ts", "network_call", 2, "import axios from 'axios'")]
    md = format_markdown(results)
    assert "import axios from 'axios'" in md


def test_markdown_contains_line_number() -> None:
    results = [_result("src/api.ts", "network_call", 42, "fetch(url)")]
    md = format_markdown(results)
    assert "42" in md


def test_markdown_sections_by_category() -> None:
    results = [
        _result("routes.ts", "route_definition", 1, "router.get('/')"),
        _result("client.ts", "network_call", 3, "import axios"),
    ]
    md = format_markdown(results)
    assert "## Route Definitions" in md
    assert "## Network Calls" in md


def test_markdown_empty_results() -> None:
    md = format_markdown([])
    assert "No network-capable files found" in md


def test_markdown_transitive_badge() -> None:
    results = [_result("app.ts", "network_call", 1, "import x", transitive=True)]
    md = format_markdown(results)
    assert "transitive" in md


def test_markdown_pipe_in_snippet_escaped() -> None:
    results = [_result("app.ts", "network_call", 1, "a | b")]
    md = format_markdown(results)
    # The pipe in the snippet must be escaped so the table renders correctly
    assert r"\|" in md


def test_markdown_repo_root_shown() -> None:
    results = [_result("src/api.ts", "network_call", 1, "import axios")]
    md = format_markdown(results, repo_root="/my/repo")
    assert "/my/repo" in md
