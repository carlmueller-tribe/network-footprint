from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from footprint.known_packages import KNOWN_PACKAGES, lookup_prefix
from footprint.patterns import PatternSpec


@dataclass
class ParsedDep:
    name: str
    ecosystem: str  # "node" | "python" | "go" | "rust"
    transitive: bool = False


def parse_package_json(path: Path) -> list[ParsedDep]:
    if not path.exists():
        return []
    try:
        data: dict[str, Any] = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    deps: dict[str, Any] = data.get("dependencies") or {}
    return [ParsedDep(name=name, ecosystem="node") for name in deps]


def parse_package_lock_json(path: Path) -> list[ParsedDep]:
    if not path.exists():
        return []
    try:
        data: dict[str, Any] = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    packages: dict[str, Any] = data.get("packages") or {}
    result: list[ParsedDep] = []
    for key in packages:
        if not key or key == "":
            continue
        name = key.removeprefix("node_modules/")
        if name:
            result.append(ParsedDep(name=name, ecosystem="node", transitive=True))
    return result


def parse_requirements_txt(path: Path) -> list[ParsedDep]:
    if not path.exists():
        return []
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return []
    result: list[ParsedDep] = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        name = re.split(r"[=<>!~;\[]", line)[0].strip()
        if name:
            result.append(ParsedDep(name=name, ecosystem="python"))
    return result


def parse_pyproject_toml(path: Path) -> list[ParsedDep]:
    if not path.exists():
        return []
    try:
        data: dict[str, Any] = tomllib.loads(path.read_text())
    except Exception:
        return []
    deps: list[Any] = data.get("project", {}).get("dependencies") or []
    result: list[ParsedDep] = []
    for dep in deps:
        if not isinstance(dep, str):
            continue
        name = re.split(r"[=<>!~;\[]", dep)[0].strip()
        if name:
            result.append(ParsedDep(name=name, ecosystem="python"))
    return result


def parse_pipfile(path: Path) -> list[ParsedDep]:
    if not path.exists():
        return []
    try:
        data: dict[str, Any] = tomllib.loads(path.read_text())
    except Exception:
        return []
    packages: dict[str, Any] = data.get("packages") or {}
    return [ParsedDep(name=name, ecosystem="python") for name in packages]


def parse_go_mod(path: Path) -> list[ParsedDep]:
    if not path.exists():
        return []
    try:
        text = path.read_text()
    except OSError:
        return []
    result: list[ParsedDep] = []
    in_require = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("require ("):
            in_require = True
            continue
        if in_require and stripped == ")":
            in_require = False
            continue
        if in_require or stripped.startswith("require "):
            parts = stripped.removeprefix("require ").split()
            if parts:
                result.append(ParsedDep(name=parts[0], ecosystem="go"))
    return result


def parse_cargo_toml(path: Path) -> list[ParsedDep]:
    if not path.exists():
        return []
    try:
        data: dict[str, Any] = tomllib.loads(path.read_text())
    except Exception:
        return []
    deps: dict[str, Any] = data.get("dependencies") or {}
    return [ParsedDep(name=name, ecosystem="rust") for name in deps]


_SKIP_DIRS = frozenset(
    {
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".git",
        "dist",
        "build",
        ".next",
        ".nuxt",
        "coverage",
        ".mypy_cache",
        ".ruff_cache",
    }
)


def _find_manifests(repo_root: Path, filename: str) -> list[Path]:
    """Find all manifest files with the given name under repo_root, skipping build/dep dirs.

    Uses os.walk with in-place dir pruning so node_modules/.venv trees are never traversed.
    """
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        if filename in filenames:
            found.append(Path(dirpath) / filename)
    return found


def parse_all(repo_root: Path) -> list[ParsedDep]:
    """Parse all dependency manifests found anywhere under repo_root.

    Searches subdirectories so monorepos (e.g. frontend/ + backend/) are covered.
    Deduplicates by (name, ecosystem) to avoid double-counting shared packages.
    """
    seen: set[tuple[str, str]] = set()
    result: list[ParsedDep] = []

    def add(deps: list[ParsedDep]) -> None:
        for dep in deps:
            key = (dep.name.lower(), dep.ecosystem)
            if key not in seen:
                seen.add(key)
                result.append(dep)

    for p in _find_manifests(repo_root, "package.json"):
        add(parse_package_json(p))
    for p in _find_manifests(repo_root, "package-lock.json"):
        add(parse_package_lock_json(p))
    for p in _find_manifests(repo_root, "requirements.txt"):
        add(parse_requirements_txt(p))
    for p in _find_manifests(repo_root, "pyproject.toml"):
        add(parse_pyproject_toml(p))
    for p in _find_manifests(repo_root, "Pipfile"):
        add(parse_pipfile(p))
    for p in _find_manifests(repo_root, "go.mod"):
        add(parse_go_mod(p))
    for p in _find_manifests(repo_root, "Cargo.toml"):
        add(parse_cargo_toml(p))

    return result


@dataclass
class ResolvedPackage:
    package: str
    import_name: str
    network_capable: bool
    category: str | None
    source: str  # "lookup" | "claude" | "manifest_override" | "unknown_package"
    transitive: bool = False


_CLASSIFIER_PROMPT = """\
You are a code analysis assistant. Given a list of package names, classify each one.

For each package return:
- network_capable: true if the package makes or handles any outbound network connections
- import_name: the canonical Python or JS import name (may differ from package name)
- category: one of:
    "network_call"     — explicit developer-initiated calls to an external third-party service
                         (e.g. payment APIs, AI inference, cloud SDKs, external REST clients)
    "route_definition" — defines or calls internal app routes (server frameworks, internal
                         HTTP clients)
    "telemetry"        — background/implicit calls to monitoring, analytics, or observability
                         services that are a side-effect of SDK init, not core app function
                         (e.g. error tracking, metrics, distributed tracing, analytics events)
    null               — not network-related

Respond ONLY with a JSON array, no preamble, no markdown fences:
[
  {{"package": "stripe", "network_capable": true, "import_name": "stripe",
    "category": "network_call"}},
  {{"package": "sentry-sdk", "network_capable": true, "import_name": "sentry_sdk",
    "category": "telemetry"}},
  {{"package": "numpy", "network_capable": false, "import_name": "numpy", "category": null}},
  ...
]

Packages to classify:
{packages}
"""


_BATCH_SIZE = 25
_BATCH_TIMEOUT = 30  # seconds per batch — 25 packages should complete well within this


def _classify_with_claude(packages: list[str]) -> str:
    """Classify one batch of packages via Claude CLI or SDK."""
    prompt = _CLASSIFIER_PROMPT.format(packages="\n".join(packages))
    if shutil.which("claude"):
        print("[footprint]   → calling Claude CLI...", file=sys.stderr)
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=_BATCH_TIMEOUT,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        raise RuntimeError(f"claude CLI failed: {result.stderr.strip()}")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        print("[footprint]   → calling Claude SDK...", file=sys.stderr)
        return _classify_with_sdk(packages)
    raise RuntimeError(
        "No Claude authentication available. "
        "Install Claude Code (claude.ai/code) or set ANTHROPIC_API_KEY."
    )


def _classify_packages(packages: list[str]) -> dict[str, dict[str, Any]]:
    """Classify packages in batches, merging results. Returns map of package -> classification."""
    total = len(packages)
    batches = [packages[i : i + _BATCH_SIZE] for i in range(0, total, _BATCH_SIZE)]
    preview = ", ".join(packages[:5]) + ("..." if total > 5 else "")
    n_batches = len(batches)
    batch_info = f" ({n_batches} batch{'es' if n_batches > 1 else ''})" if n_batches > 1 else ""
    print(
        f"[footprint] asking Claude to classify {total} unknown package(s){batch_info}: {preview}",
        file=sys.stderr,
    )
    classified_map: dict[str, dict[str, Any]] = {}
    for i, batch in enumerate(batches, 1):
        if n_batches > 1:
            print(f"[footprint]   batch {i}/{n_batches}: {', '.join(batch)}", file=sys.stderr)
        raw = _classify_with_claude(batch)
        for item in _parse_claude_response(raw):
            if isinstance(item, dict) and "package" in item:
                classified_map[item["package"]] = item
                tag = item.get("category") or (
                    "network_call" if item.get("network_capable") else "not network-capable"
                )  # noqa: E501
                print(f"[footprint]   {item['package']} → {tag}", file=sys.stderr)
    return classified_map


def _classify_with_sdk(packages: list[str]) -> str:
    """Call Claude via anthropic SDK using ANTHROPIC_API_KEY."""
    import anthropic  # noqa: PLC0415

    prompt = _CLASSIFIER_PROMPT.format(packages="\n".join(packages))
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    content = msg.content[0]
    if content.type != "text":
        raise RuntimeError("Unexpected response type from Claude SDK")
    print(
        f"[footprint] Claude SDK: {msg.usage.input_tokens} in / {msg.usage.output_tokens} out",  # noqa: E501
        file=sys.stderr,
    )
    return str(content.text)


def _parse_claude_response(raw: str) -> list[dict[str, Any]]:
    """Extract JSON array from Claude response, handling markdown fences."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        end_fence = next((i for i, ln in enumerate(lines[1:], 1) if ln.strip() == "```"), None)
        text = "\n".join(lines[1:end_fence] if end_fence else lines[1:])
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        return list(json.loads(text[start : end + 1]))
    except json.JSONDecodeError:
        return []


def resolve_packages(
    deps: list[ParsedDep],
    overrides: dict[str, str] | None = None,
) -> list[ResolvedPackage]:
    """Resolve deps to ResolvedPackage list. overrides maps package name -> import_name."""
    overrides = overrides or {}
    results: list[ResolvedPackage] = []
    unknown: list[ParsedDep] = []

    for dep in deps:
        name_lower = dep.name.lower()
        if dep.name in overrides:
            entry = KNOWN_PACKAGES.get(name_lower, {})
            results.append(
                ResolvedPackage(
                    package=dep.name,
                    import_name=overrides[dep.name],
                    network_capable=bool(entry.get("network_capable", False)),
                    category=entry.get("category"),
                    source="manifest_override",
                    transitive=dep.transitive,
                )
            )
        elif name_lower in KNOWN_PACKAGES:
            entry = KNOWN_PACKAGES[name_lower]
            results.append(
                ResolvedPackage(
                    package=dep.name,
                    import_name=str(entry["import_name"]),
                    network_capable=bool(entry["network_capable"]),
                    category=entry.get("category"),
                    source="lookup",
                    transitive=dep.transitive,
                )
            )
        elif (prefix_entry := lookup_prefix(dep.name)) is not None:
            results.append(
                ResolvedPackage(
                    package=dep.name,
                    import_name=str(prefix_entry["import_name"]),
                    network_capable=bool(prefix_entry["network_capable"]),
                    category=prefix_entry.get("category"),
                    source="lookup",
                    transitive=dep.transitive,
                )
            )
        else:
            unknown.append(dep)

    # Only classify direct deps via Claude. Transitive deps not in the lookup table are
    # silently skipped — lockfiles contain hundreds of sub-dependencies that would
    # overwhelm Claude and generate useless patterns.
    direct_unknown = [d for d in unknown if not d.transitive]

    if direct_unknown:
        try:
            classified_map: dict[str, dict[str, Any]] = _classify_packages(
                [d.name for d in direct_unknown]
            )
        except Exception as exc:
            warnings.warn(
                f"Claude classifier failed: {exc}. Treating unknown packages as non-network.",
                stacklevel=2,
            )
            classified_map = {}

        for dep in direct_unknown:
            item = classified_map.get(dep.name)
            if item:
                results.append(
                    ResolvedPackage(
                        package=dep.name,
                        import_name=str(item.get("import_name", dep.name)),
                        network_capable=bool(item.get("network_capable", False)),
                        category=item.get("category"),
                        source="claude",
                        transitive=dep.transitive,
                    )
                )
            else:
                results.append(
                    ResolvedPackage(
                        package=dep.name,
                        import_name=dep.name,
                        network_capable=True,  # conservative: assume capable, let human verify
                        category="network_call",
                        source="unknown_package",
                        transitive=dep.transitive,
                    )
                )

    return results


def _make_pattern(
    pat: str,
    cat: str,
    stack: str,
    transitive: bool,
    source: str = "dependency_resolved",
) -> PatternSpec:
    spec: PatternSpec = {
        "pattern": pat,
        "category": cat,
        "stack": stack,
        "source": source,
    }
    if transitive:
        spec["transitive"] = True
    return spec


def generate_patterns(
    resolved: list[ResolvedPackage],
    ecosystem: str,
) -> list[PatternSpec]:
    """Generate regex patterns from network-capable resolved packages."""
    patterns: list[PatternSpec] = []
    for pkg in resolved:
        if not pkg.network_capable:
            continue
        escaped = re.escape(pkg.import_name)
        cat = pkg.category or "network_call"
        stack = ecosystem if ecosystem in ("node", "python", "devops") else "node"
        base_source = (
            "dependency_resolved" if pkg.source != "unknown_package" else "unknown_package"
        )
        if ecosystem == "python":
            patterns.append(
                _make_pattern(f"import {escaped}", cat, stack, pkg.transitive, base_source)
            )
            patterns.append(
                _make_pattern(f"from {escaped}", cat, stack, pkg.transitive, base_source)
            )
        else:  # node
            patterns.append(
                _make_pattern(f"from ['\"]{escaped}['\"]", cat, stack, pkg.transitive, base_source)
            )
            patterns.append(
                _make_pattern(
                    rf"require\(['\"]{escaped}['\"]", cat, stack, pkg.transitive, base_source
                )
            )
    return patterns
