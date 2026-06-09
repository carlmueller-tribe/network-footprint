from __future__ import annotations

from footprint.heuristics import is_comment, is_string_literal, is_test_file


def test_python_comment_detected() -> None:
    assert is_comment("    # import requests", "python") is True


def test_python_non_comment() -> None:
    assert is_comment("import requests", "python") is False


def test_node_single_line_comment() -> None:
    assert is_comment("// import axios from 'axios'", "node") is True


def test_node_block_comment_star() -> None:
    assert is_comment("  * import express", "node") is True


def test_node_block_comment_open() -> None:
    assert is_comment("/* import got */", "node") is True


def test_non_comment_node() -> None:
    assert is_comment("import axios from 'axios'", "node") is False


def test_string_literal_double_quoted() -> None:
    assert is_string_literal('doc = "import requests"', 7) is True


def test_string_literal_single_quoted() -> None:
    assert is_string_literal("msg = 'fetch(url)'", 7) is True


def test_not_string_literal() -> None:
    assert is_string_literal("import requests", 0) is False


def test_test_file_spec() -> None:
    assert is_test_file("src/services/api.spec.ts") is True


def test_test_file_test_suffix() -> None:
    assert is_test_file("src/services/api.test.ts") is True


def test_test_file_python_spec() -> None:
    assert is_test_file("tests/test_api.py") is True


def test_test_file_tests_dir() -> None:
    assert is_test_file("tests/integration/test_routes.py") is True


def test_test_file_underscore_tests_dir() -> None:
    assert is_test_file("src/__tests__/api.ts") is True


def test_non_test_file() -> None:
    assert is_test_file("src/services/api.ts") is False


def test_non_test_python() -> None:
    assert is_test_file("src/routes.py") is False
