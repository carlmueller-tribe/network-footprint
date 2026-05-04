from __future__ import annotations

import json

from footprint.scanner import ScanResult


def format_json(results: list[ScanResult]) -> str:
    data = []
    for r in results:
        matches = []
        for m in r.matches:
            entry: dict[str, object] = {
                "pattern": m.pattern,
                "category": m.category,
                "stack": m.stack,
                "line": m.line,
                "source": m.source,
            }
            if m.transitive:
                entry["transitive"] = True
            matches.append(entry)
        data.append(
            {
                "file": r.file,
                "categories": r.categories,
                "matches": matches,
            }
        )
    return json.dumps(data, indent=2)


def format_flat(results: list[ScanResult]) -> str:
    return "\n".join(r.file for r in results)
