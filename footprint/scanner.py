from __future__ import annotations

import re
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

from footprint.manifest import ManifestConfig
from footprint.patterns import ALL_PATTERNS, PatternSpec

EXTENSIONS: dict[str, list[str]] = {
    "node": [".ts", ".tsx", ".js", ".jsx", ".mjs"],
    "python": [".py"],
    "devops": [".yml", ".yaml", ".tf", ".tfvars", ".conf", ".sh"],
}

DEVOPS_NAME_PREFIXES: tuple[str, ...] = ("Dockerfile",)
DEVOPS_EXACT_NAMES: frozenset[str] = frozenset({"Makefile"})
DEVOPS_GLOB_NAMES: tuple[str, ...] = (
    "docker-compose*.yml",
    "docker-compose*.yaml",
    "nginx.conf",
)


@dataclass
class Match:
    pattern: str
    category: str
    stack: str
    line: int


@dataclass
class ScanResult:
    file: str
    categories: list[str]
    matches: list[Match]


class Scanner:
    def __init__(self, repo_root: str, manifest: ManifestConfig) -> None:
        self._root = Path(repo_root).resolve()
        self._manifest = manifest
        # Always include devops patterns; include stack patterns based on manifest
        self._patterns: list[PatternSpec] = [
            p for p in ALL_PATTERNS if p["stack"] == "devops" or p["stack"] in manifest.stacks
        ]

    def run(self) -> list[ScanResult]:
        results: list[ScanResult] = []
        for path in sorted(self._root.rglob("*")):
            if path.is_dir():
                continue
            rel = path.relative_to(self._root)
            if self._is_excluded(rel):
                continue
            if not self._should_scan(path):
                continue
            matches = self._scan_file(path)
            if matches:
                results.append(
                    ScanResult(
                        file=str(rel),
                        categories=sorted({m.category for m in matches}),
                        matches=matches,
                    )
                )
        return results

    def _is_excluded(self, rel: Path) -> bool:
        for pattern in self._manifest.exclude:
            for part in rel.parts:
                if fnmatch(part, pattern):
                    return True
            if fnmatch(str(rel), pattern):
                return True
        return False

    def _should_scan(self, path: Path) -> bool:
        name = path.name
        if name in DEVOPS_EXACT_NAMES:
            return True
        if any(name.startswith(prefix) for prefix in DEVOPS_NAME_PREFIXES):
            return True
        if any(fnmatch(name, glob) for glob in DEVOPS_GLOB_NAMES):
            return True
        return any(path.suffix in EXTENSIONS.get(stack, []) for stack in self._manifest.stacks)

    def _is_devops_file(self, path: Path) -> bool:
        name = path.name
        if name in DEVOPS_EXACT_NAMES:
            return True
        if any(name.startswith(prefix) for prefix in DEVOPS_NAME_PREFIXES):
            return True
        if any(fnmatch(name, glob) for glob in DEVOPS_GLOB_NAMES):
            return True
        return path.suffix in EXTENSIONS.get("devops", [])

    def _scan_file(self, path: Path) -> list[Match]:
        is_devops = self._is_devops_file(path)
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return []
        matches: list[Match] = []
        seen: set[tuple[str, int]] = set()
        for lineno, line in enumerate(lines, start=1):
            for p in self._patterns:
                if p["stack"] == "devops" and not is_devops:
                    continue
                if re.search(p["pattern"], line):
                    key = (p["pattern"], lineno)
                    if key not in seen:
                        seen.add(key)
                        matches.append(
                            Match(
                                pattern=p["pattern"],
                                category=p["category"],
                                stack=p["stack"],
                                line=lineno,
                            )
                        )
        return matches
