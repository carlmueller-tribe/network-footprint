from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tomllib
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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


def parse_all(repo_root: Path) -> list[ParsedDep]:
    result: list[ParsedDep] = []
    result.extend(parse_package_json(repo_root / "package.json"))
    result.extend(parse_package_lock_json(repo_root / "package-lock.json"))
    result.extend(parse_requirements_txt(repo_root / "requirements.txt"))
    result.extend(parse_pyproject_toml(repo_root / "pyproject.toml"))
    result.extend(parse_pipfile(repo_root / "Pipfile"))
    result.extend(parse_go_mod(repo_root / "go.mod"))
    result.extend(parse_cargo_toml(repo_root / "Cargo.toml"))
    return result


@dataclass
class ResolvedPackage:
    package: str
    import_name: str
    network_capable: bool
    category: str | None
    source: str  # "lookup" | "claude" | "manifest_override" | "claude_failed"
    transitive: bool = False


KNOWN_PACKAGES: dict[str, dict[str, Any]] = {
    # Node
    "axios": {"network_capable": True, "import_name": "axios", "category": "network_call"},
    "node-fetch": {
        "network_capable": True,
        "import_name": "node-fetch",
        "category": "network_call",
    },
    "got": {"network_capable": True, "import_name": "got", "category": "network_call"},
    "superagent": {
        "network_capable": True,
        "import_name": "superagent",
        "category": "network_call",
    },
    "ky": {"network_capable": True, "import_name": "ky", "category": "network_call"},
    "undici": {"network_capable": True, "import_name": "undici", "category": "network_call"},
    "ws": {"network_capable": True, "import_name": "ws", "category": "network_call"},
    "socket.io-client": {
        "network_capable": True,
        "import_name": "socket.io-client",
        "category": "network_call",
    },
    "@apollo/client": {
        "network_capable": True,
        "import_name": "@apollo/client",
        "category": "network_call",
    },
    "graphql-request": {
        "network_capable": True,
        "import_name": "graphql-request",
        "category": "network_call",
    },
    "express": {"network_capable": True, "import_name": "express", "category": "route_definition"},
    "fastify": {"network_capable": True, "import_name": "fastify", "category": "route_definition"},
    "koa": {"network_capable": True, "import_name": "koa", "category": "route_definition"},
    # Python
    "requests": {"network_capable": True, "import_name": "requests", "category": "network_call"},
    "httpx": {"network_capable": True, "import_name": "httpx", "category": "network_call"},
    "aiohttp": {"network_capable": True, "import_name": "aiohttp", "category": "network_call"},
    "boto3": {"network_capable": True, "import_name": "boto3", "category": "network_call"},
    "botocore": {"network_capable": True, "import_name": "botocore", "category": "network_call"},
    "openai": {"network_capable": True, "import_name": "openai", "category": "network_call"},
    "anthropic": {"network_capable": True, "import_name": "anthropic", "category": "network_call"},
    "fastapi": {"network_capable": True, "import_name": "fastapi", "category": "route_definition"},
    "flask": {"network_capable": True, "import_name": "flask", "category": "route_definition"},
    "django": {"network_capable": True, "import_name": "django", "category": "route_definition"},
    "pillow": {"network_capable": False, "import_name": "PIL", "category": None},
    "opencv-python": {"network_capable": False, "import_name": "cv2", "category": None},
    "python-dotenv": {"network_capable": False, "import_name": "dotenv", "category": None},
    "numpy": {"network_capable": False, "import_name": "numpy", "category": None},
    "pandas": {"network_capable": False, "import_name": "pandas", "category": None},
    "pydantic": {"network_capable": False, "import_name": "pydantic", "category": None},
    # Telemetry / observability — background calls, not core function
    "sentry-sdk": {"network_capable": True, "import_name": "sentry_sdk", "category": "telemetry"},
    "datadog": {"network_capable": True, "import_name": "datadog", "category": "telemetry"},
    "ddtrace": {"network_capable": True, "import_name": "ddtrace", "category": "telemetry"},
    "opentelemetry-sdk": {
        "network_capable": True,
        "import_name": "opentelemetry",
        "category": "telemetry",
    },
    "opentelemetry-api": {
        "network_capable": True,
        "import_name": "opentelemetry",
        "category": "telemetry",
    },
    "segment-analytics-python": {
        "network_capable": True,
        "import_name": "segment",
        "category": "telemetry",
    },
    "analytics-python": {
        "network_capable": True,
        "import_name": "analytics",
        "category": "telemetry",
    },
    "posthog": {"network_capable": True, "import_name": "posthog", "category": "telemetry"},
    "mixpanel": {"network_capable": True, "import_name": "mixpanel", "category": "telemetry"},
    "amplitude": {"network_capable": True, "import_name": "amplitude", "category": "telemetry"},
    "newrelic": {"network_capable": True, "import_name": "newrelic", "category": "telemetry"},
    "rollbar": {"network_capable": True, "import_name": "rollbar", "category": "telemetry"},
    "bugsnag": {"network_capable": True, "import_name": "bugsnag", "category": "telemetry"},
    "honeybadger": {
        "network_capable": True,
        "import_name": "honeybadger",
        "category": "telemetry",
    },
    "prometheus-client": {
        "network_capable": True,
        "import_name": "prometheus_client",
        "category": "telemetry",
    },
    # Node telemetry
    "@sentry/node": {
        "network_capable": True,
        "import_name": "@sentry/node",
        "category": "telemetry",
    },
    "@sentry/browser": {
        "network_capable": True,
        "import_name": "@sentry/browser",
        "category": "telemetry",
    },
    "@datadog/datadog-ci": {
        "network_capable": True,
        "import_name": "@datadog/datadog-ci",
        "category": "telemetry",
    },
    "@opentelemetry/sdk-node": {
        "network_capable": True,
        "import_name": "@opentelemetry/sdk-node",
        "category": "telemetry",
    },
    "@segment/analytics-node": {
        "network_capable": True,
        "import_name": "@segment/analytics-node",
        "category": "telemetry",
    },
    "posthog-node": {
        "network_capable": True,
        "import_name": "posthog-node",
        "category": "telemetry",
    },
    "mixpanel-browser": {
        "network_capable": True,
        "import_name": "mixpanel-browser",
        "category": "telemetry",
    },
    "pino": {"network_capable": False, "import_name": "pino", "category": None},
    "winston": {"network_capable": False, "import_name": "winston", "category": None},
}

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


def _classify_with_claude(packages: list[str]) -> str:
    """Call Claude for package classification. Tries claude CLI subprocess first, SDK fallback."""
    prompt = _CLASSIFIER_PROMPT.format(packages="\n".join(packages))
    if shutil.which("claude"):
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        raise RuntimeError(f"claude CLI failed: {result.stderr.strip()}")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        return _classify_with_sdk(packages)
    raise RuntimeError(
        "No Claude authentication available. "
        "Install Claude Code (claude.ai/code) or set ANTHROPIC_API_KEY."
    )


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
        else:
            unknown.append(dep)

    if unknown:
        try:
            raw = _classify_with_claude([d.name for d in unknown])
            classified = _parse_claude_response(raw)
            classified_map: dict[str, dict[str, Any]] = {
                item["package"]: item for item in classified if isinstance(item, dict)
            }
        except Exception as exc:
            warnings.warn(
                f"Claude classifier failed: {exc}. Treating unknown packages as non-network.",
                stacklevel=2,
            )
            classified_map = {}

        for dep in unknown:
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
                        network_capable=False,
                        category=None,
                        source="claude_failed",
                        transitive=dep.transitive,
                    )
                )

    return results


def _make_pattern(
    pat: str,
    cat: str,
    stack: str,
    transitive: bool,
) -> PatternSpec:
    spec: PatternSpec = {
        "pattern": pat,
        "category": cat,
        "stack": stack,
        "source": "dependency_resolved",
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
        if ecosystem == "python":
            patterns.append(_make_pattern(f"import {escaped}", cat, stack, pkg.transitive))
            patterns.append(_make_pattern(f"from {escaped}", cat, stack, pkg.transitive))
        else:  # node
            patterns.append(_make_pattern(f"from ['\"]{escaped}['\"]", cat, stack, pkg.transitive))
            patterns.append(
                _make_pattern(rf"require\(['\"]{escaped}['\"]", cat, stack, pkg.transitive)
            )
    return patterns
