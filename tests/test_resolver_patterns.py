from __future__ import annotations

from footprint.resolver import ResolvedPackage, generate_patterns


def _make_pkg(
    name: str,
    import_name: str,
    *,
    network_capable: bool = True,
    category: str = "network_call",
    transitive: bool = False,
) -> ResolvedPackage:
    return ResolvedPackage(
        package=name,
        import_name=import_name,
        network_capable=network_capable,
        category=category,
        source="lookup",
        transitive=transitive,
    )


def test_python_package_generates_import_patterns() -> None:
    pkg = _make_pkg("stripe", "stripe")
    patterns = generate_patterns([pkg], ecosystem="python")
    pattern_strs = [p["pattern"] for p in patterns]
    assert any("import stripe" in s for s in pattern_strs)
    assert any(s.startswith("from stripe") for s in pattern_strs)


def test_node_package_generates_import_patterns() -> None:
    import re

    pkg = _make_pkg("axios", "axios")
    patterns = generate_patterns([pkg], ecosystem="node")
    pattern_strs = [p["pattern"] for p in patterns]
    assert any("axios" in s for s in pattern_strs)
    # Verify patterns actually match correct import syntax
    for pat in pattern_strs:
        if "axios" in pat:
            assert re.search(pat, "import axios from 'axios'") or re.search(pat, 'require("axios")')
            # Must NOT match a different package
            assert not re.search(pat, "import foo from 'other-pkg'")


def test_non_network_package_excluded() -> None:
    pkg = _make_pkg("pillow", "PIL", network_capable=False, category="network_call")
    patterns = generate_patterns([pkg], ecosystem="python")
    assert patterns == []


def test_patterns_tagged_dependency_resolved() -> None:
    pkg = _make_pkg("httpx", "httpx")
    patterns = generate_patterns([pkg], ecosystem="python")
    assert all(p.get("source") == "dependency_resolved" for p in patterns)


def test_node_special_chars_escaped() -> None:
    import re

    pkg = _make_pkg("@apollo/client", "@apollo/client")
    patterns = generate_patterns([pkg], ecosystem="node")
    pattern_strs = [p["pattern"] for p in patterns]
    assert any("apollo" in s for s in pattern_strs)
    # Verify the pattern correctly matches the escaped package name
    for pat in pattern_strs:
        if "apollo" in pat:
            assert re.search(pat, "import ApolloClient from '@apollo/client'") or re.search(
                pat, "require('@apollo/client')"
            )


def test_transitive_flag_on_generated_pattern() -> None:
    pkg = _make_pkg("follow-redirects", "follow-redirects", transitive=True)
    patterns = generate_patterns([pkg], ecosystem="node")
    assert all(p.get("transitive") is True for p in patterns)


def test_non_transitive_has_no_transitive_key() -> None:
    pkg = _make_pkg("axios", "axios", transitive=False)
    patterns = generate_patterns([pkg], ecosystem="node")
    assert all("transitive" not in p for p in patterns)
