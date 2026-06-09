from __future__ import annotations

import json

from footprint.scanner import ScanResult


def format_json(results: list[ScanResult]) -> str:
    data = [
        {
            "file": r.file,
            "categories": r.categories,
            "matches": [
                {
                    "pattern": m.pattern,
                    "category": m.category,
                    "stack": m.stack,
                    "line": m.line,
                }
                for m in r.matches
            ],
        }
        for r in results
    ]
    return json.dumps(data, indent=2)


def format_flat(results: list[ScanResult]) -> str:
    return "\n".join(r.file for r in results)
