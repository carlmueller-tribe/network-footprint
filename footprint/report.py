from __future__ import annotations

import json
from datetime import UTC

from footprint.scanner import ScanResult


def format_json(results: list[ScanResult], repo: str = "") -> str:
    from datetime import datetime  # noqa: PLC0415

    all_matches = [m for r in results for m in r.matches]

    by_category: dict[str, int] = {}
    by_stack: dict[str, int] = {}
    for m in all_matches:
        by_category[m.category] = by_category.get(m.category, 0) + 1
        by_stack[m.stack] = by_stack.get(m.stack, 0) + 1

    low_conf = sum(1 for m in all_matches if m.confidence < 0.5)
    transitive = sum(1 for m in all_matches if m.transitive)
    from_defaults = sum(1 for m in all_matches if m.source == "default")
    from_resolved = sum(1 for m in all_matches if m.source == "dependency_resolved")
    from_custom = sum(1 for m in all_matches if m.source == "custom")

    results_data = []
    for r in results:
        matches = []
        for m in r.matches:
            entry: dict[str, object] = {
                "pattern": m.pattern,
                "category": m.category,
                "stack": m.stack,
                "line": m.line,
                "source": m.source,
                "confidence": round(m.confidence, 2),
            }
            if m.in_comment:
                entry["in_comment"] = True
            if m.in_string_literal:
                entry["in_string_literal"] = True
            if m.context:
                entry["context"] = m.context
            if m.transitive:
                entry["transitive"] = True
            matches.append(entry)
        result_entry: dict[str, object] = {
            "file": r.file,
            "categories": r.categories,
            "matches": matches,
        }
        if r.coverage:
            result_entry["coverage"] = r.coverage
        results_data.append(result_entry)

    summary: dict[str, object] = {
        "repo": repo,
        "scanned_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_files_matched": len(results),
        "by_category": by_category,
        "by_stack": by_stack,
        "low_confidence_matches": low_conf,
        "transitive_matches": transitive,
        "patterns_from_defaults": from_defaults,
        "patterns_from_dependency_resolution": from_resolved,
        "patterns_from_custom": from_custom,
    }

    return json.dumps({"results": results_data, "summary": summary}, indent=2)


def format_flat(results: list[ScanResult]) -> str:
    return "\n".join(r.file for r in results)


def format_markdown(results: list[ScanResult], repo_root: str = "") -> str:
    from datetime import datetime, timezone

    lines: list[str] = []
    lines.append("# Network Footprint Report")
    lines.append("")
    if repo_root:
        lines.append(f"Scanned: `{repo_root}`  ")
    lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")  # noqa: UP017
    lines.append("")

    lines.append(
        "> **Confidence** — likelihood the match is a real network call or route, "
        "not noise (comment, string literal, test artifact, or unverified dependency).  "
    )
    lines.append(
        "> `0.9–1.0` certain · `0.7–0.8` likely · `0.5–0.6` uncertain · `< 0.5` probable noise"
    )
    lines.append("")

    # Group results by category
    category_order = ["route_definition", "network_call", "telemetry", "devops"]
    category_labels = {
        "route_definition": "Route Definitions",
        "network_call": "Network Calls",
        "telemetry": "Telemetry & Observability",
        "devops": "DevOps",
    }

    # Collect all categories present (preserve order, add unknowns at end)
    all_cats: list[str] = []
    seen_cats: set[str] = set()
    for cat in category_order:
        all_cats.append(cat)
        seen_cats.add(cat)
    for r in results:
        for c in r.categories:
            if c not in seen_cats:
                all_cats.append(c)
                seen_cats.add(c)

    for cat in all_cats:
        # Files that have at least one match in this category
        cat_results = [
            (r, [m for m in r.matches if m.category == cat]) for r in results if cat in r.categories
        ]
        if not cat_results:
            continue

        label = category_labels.get(cat, cat.replace("_", " ").title())
        lines.append(f"## {label}")
        lines.append("")

        for result, matches in cat_results:
            lines.append(f"### `{result.file}`")
            lines.append("")
            if result.coverage == "likely_active":
                lines.append("**Coverage:** ✓ appears in test calls")
                lines.append("")
            elif result.coverage == "no_test_coverage":
                lines.append("**Coverage:** ⚠ no test coverage found")
                lines.append("")
            lines.append("| Line | Confidence | Snippet |")
            lines.append("|------|------------|---------|")
            for m in matches:
                snippet = m.line_content.strip()
                # Escape pipe chars in snippet so table doesn't break
                snippet = snippet.replace("|", "\\|")
                badge = " *(transitive)*" if m.transitive else ""
                lines.append(f"| {m.line} | {m.confidence:.2f} | `{snippet}`{badge} |")
            lines.append("")

        lines.append("---")
        lines.append("")

    if not results:
        lines.append("*No network-capable files found.*")
        lines.append("")

    lines.append("*Generated by [network-footprint](https://github.com/TribeAI/network-footprint)*")
    return "\n".join(lines)
