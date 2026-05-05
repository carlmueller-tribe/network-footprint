from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

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
class ManifestConfig:
    stacks: list[str]
    exclude: list[str]


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
    return ManifestConfig(
        stacks=list(raw_stacks) if isinstance(raw_stacks, list) else list(DEFAULT_STACKS),
        exclude=list(raw_exclude) if isinstance(raw_exclude, list) else list(DEFAULT_EXCLUDES),
    )
