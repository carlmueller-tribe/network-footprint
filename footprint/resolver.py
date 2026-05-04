from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
