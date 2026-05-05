from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from footprint.patterns import PatternSpec

DEFAULT_STACKS: list[str] = ["node", "python", "devops"]

DEFAULT_EXCLUDES: list[str] = [
    "node_modules",
    ".git",
    "dist",
    "build",
    "__pycache__",
    ".venv",
    "venv",
    "*.pyc",
]


@dataclass
class ImportOverride:
    package: str
    imports_as: str


@dataclass
class PatternOverrides:
    add: list[PatternSpec] = field(default_factory=list)
    remove: list[str] = field(default_factory=list)


@dataclass
class ManifestOverrides:
    imports: list[ImportOverride] = field(default_factory=list)
    patterns: PatternOverrides = field(default_factory=PatternOverrides)


@dataclass
class ManifestConfig:
    stacks: list[str]
    exclude: list[str]
    overrides: ManifestOverrides | None = None


def _parse_overrides(raw_overrides: Any) -> ManifestOverrides | None:
    if not isinstance(raw_overrides, dict):
        return None
    result = ManifestOverrides()
    raw_imports = raw_overrides.get("imports")
    if isinstance(raw_imports, list):
        for item in raw_imports:
            if isinstance(item, dict) and "package" in item and "imports_as" in item:
                result.imports.append(
                    ImportOverride(
                        package=str(item["package"]),
                        imports_as=str(item["imports_as"]),
                    )
                )
    raw_patterns = raw_overrides.get("patterns")
    if isinstance(raw_patterns, dict):
        raw_add = raw_patterns.get("add") or []
        raw_remove = raw_patterns.get("remove") or []
        for item in raw_add:
            if isinstance(item, dict) and "pattern" in item:
                p: PatternSpec = {
                    "pattern": str(item["pattern"]),
                    "category": str(item.get("category", "network_call")),
                    "stack": str(item.get("stack", "node")),
                    "source": "custom",
                }
                result.patterns.add.append(p)
        result.patterns.remove = [str(r) for r in raw_remove if r]
    return result


def load_manifest(
    repo_root: Path,
    manifest_path: Path | None = None,
) -> ManifestConfig:
    path = manifest_path or (repo_root / "network-footprint.yaml")
    if not path.exists():
        return ManifestConfig(stacks=list(DEFAULT_STACKS), exclude=list(DEFAULT_EXCLUDES))
    with path.open() as f:
        try:
            raw = yaml.safe_load(f)
        except yaml.YAMLError:
            return ManifestConfig(stacks=list(DEFAULT_STACKS), exclude=list(DEFAULT_EXCLUDES))
    data: dict[str, Any] = raw if isinstance(raw, dict) else {}
    raw_stacks = data.get("stacks")
    raw_exclude = data.get("exclude")
    overrides = _parse_overrides(data.get("overrides"))
    return ManifestConfig(
        stacks=list(raw_stacks) if isinstance(raw_stacks, list) else list(DEFAULT_STACKS),
        exclude=list(raw_exclude) if isinstance(raw_exclude, list) else list(DEFAULT_EXCLUDES),
        overrides=overrides,
    )
