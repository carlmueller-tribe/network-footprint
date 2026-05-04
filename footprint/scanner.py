from __future__ import annotations

import re
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

from footprint.heuristics import is_comment, is_string_literal, is_test_file
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
    source: str = "default"
    transitive: bool = False
    line_content: str = ""
    in_comment: bool = False
    in_string_literal: bool = False
    context: str = ""  # "test" | ""
    confidence: float = 0.0


@dataclass
class ScanResult:
    file: str
    categories: list[str]
    matches: list[Match]
    coverage: str = ""  # "likely_active" | "no_test_coverage" | ""


class Scanner:
    _BASE_CONFIDENCE: float = 0.7

    def __init__(
        self,
        repo_root: str,
        manifest: ManifestConfig,
        extra_patterns: list[PatternSpec] | None = None,
        remove_patterns: list[str] | None = None,
    ) -> None:
        self._root = Path(repo_root).resolve()
        self._manifest = manifest
        remove_set: set[str] = set(remove_patterns or [])
        base: list[PatternSpec] = [
            p
            for p in ALL_PATTERNS
            if (p["stack"] == "devops" or p["stack"] in manifest.stacks)
            and p["pattern"] not in remove_set
        ]
        injected: list[PatternSpec] = [
            p for p in (extra_patterns or []) if p["pattern"] not in remove_set
        ]
        self._patterns: list[PatternSpec] = base + injected

    def _score_confidence(self, matches: list[Match]) -> None:
        """Score confidence in-place. Called after _scan_file."""
        for i, m in enumerate(matches):
            score = self._BASE_CONFIDENCE
            if m.in_comment:
                score -= 0.4
            if m.in_string_literal:
                score -= 0.3
            if m.context == "test":
                score -= 0.1
            if m.category == "route_definition":
                score += 0.2
            if m.source == "dependency_resolved":
                score += 0.1
            # bonus for additional matches in same file, capped at +0.3
            score += min(i, 3) * 0.1
            m.confidence = max(0.0, min(1.0, score))

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
                self._score_confidence(matches)
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
        rel_path = str(path.relative_to(self._root))
        context = "test" if is_test_file(rel_path) else ""
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
                re_match = re.search(p["pattern"], line)
                if re_match is not None:
                    key = (p["pattern"], lineno)
                    if key not in seen:
                        seen.add(key)
                        matches.append(
                            Match(
                                pattern=p["pattern"],
                                category=p["category"],
                                stack=p["stack"],
                                line=lineno,
                                source=str(p.get("source", "default")),
                                transitive=bool(p.get("transitive", False)),
                                line_content=line,
                                in_comment=is_comment(line, p["stack"]),
                                in_string_literal=is_string_literal(line, re_match.start()),
                                context=context,
                            )
                        )
        return matches
