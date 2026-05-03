# Network Footprint Scanner — Phase 2: Dependency Resolution

## Goal
Enrich the scanner's pattern set by parsing the repo's actual dependency manifests, resolving each network-capable package to its canonical import name, and injecting those as additional patterns before the scan runs. Unknown packages are classified via Claude.

---

## New Module: `resolver.py`

Handles everything dependency-related: parsing manifests, classifying packages, resolving import names.

---

## Deliverables

### 1. Dependency Manifest Parsers

Support the following files, auto-detected from repo root:

| File | Ecosystem |
|------|-----------|
| `package.json` | Node (direct deps) |
| `package-lock.json` | Node (transitive deps, optional) |
| `requirements.txt` | Python |
| `pyproject.toml` | Python |
| `Pipfile` | Python |
| `go.mod` | Go |
| `Cargo.toml` | Rust |

Each parser returns a flat list of package names. Parsers should be tolerant of missing files — only parse what exists.

**Transitive dependencies:** Parse `package-lock.json` if present but flag those results separately in output as `transitive: true`. Don't block on missing lockfile.

---

### 2. Hardcoded Lookup Table

A baseline dictionary of well-known packages mapping to:
- `network_capable: bool`
- `import_name: str` — the canonical import name if different from package name
- `category: str` — `network_call` or `route_definition`

```python
KNOWN_PACKAGES = {
    # Node
    "axios":              { "network_capable": True, "import_name": "axios", "category": "network_call" },
    "node-fetch":         { "network_capable": True, "import_name": "node-fetch", "category": "network_call" },
    "got":                { "network_capable": True, "import_name": "got", "category": "network_call" },
    "socket.io-client":   { "network_capable": True, "import_name": "socket.io-client", "category": "network_call" },
    "ws":                 { "network_capable": True, "import_name": "ws", "category": "network_call" },
    "express":            { "network_capable": True, "import_name": "express", "category": "route_definition" },
    "fastify":            { "network_capable": True, "import_name": "fastify", "category": "route_definition" },
    "@apollo/client":     { "network_capable": True, "import_name": "@apollo/client", "category": "network_call" },
    # Python
    "requests":           { "network_capable": True, "import_name": "requests", "category": "network_call" },
    "httpx":              { "network_capable": True, "import_name": "httpx", "category": "network_call" },
    "aiohttp":            { "network_capable": True, "import_name": "aiohttp", "category": "network_call" },
    "boto3":              { "network_capable": True, "import_name": "boto3", "category": "network_call" },
    "openai":             { "network_capable": True, "import_name": "openai", "category": "network_call" },
    "anthropic":          { "network_capable": True, "import_name": "anthropic", "category": "network_call" },
    "pillow":             { "network_capable": False, "import_name": "PIL", "category": None },
    "opencv-python":      { "network_capable": False, "import_name": "cv2", "category": None },
    "python-dotenv":      { "network_capable": False, "import_name": "dotenv", "category": None },
    "fastapi":            { "network_capable": True, "import_name": "fastapi", "category": "route_definition" },
    "flask":              { "network_capable": True, "import_name": "flask", "category": "route_definition" },
    "django":             { "network_capable": True, "import_name": "django", "category": "route_definition" },
}
```

---

### 3. Claude Classifier

For any package **not** in the lookup table, call Claude to classify it.

**Prompt:**
```
You are a code analysis assistant. Given a list of package names, classify each one.

For each package return:
- network_capable: true if the package makes or handles HTTP/TCP/WebSocket or other network calls
- import_name: the canonical Python or JS import name (which may differ from the package name)
- category: "network_call" if it makes outbound calls, "route_definition" if it defines server routes, null if neither

Respond only with a JSON array, no preamble:
[
  { "package": "stripe", "network_capable": true, "import_name": "stripe", "category": "network_call" },
  ...
]

Packages to classify:
{packages}
```

**Implementation notes:**
- Batch all unknown packages into a single Claude call — don't call per package
- Cache results in memory for the duration of the scan
- If Claude call fails, log a warning and treat package as `network_capable: false` (conservative — don't generate false patterns)
- Use `claude-sonnet-4-20250514`, `max_tokens: 1000`

---

### 4. Pattern Generation

After resolution, generate regex patterns from the resolved import names and inject them into the scanner's pattern set before the scan runs.

**Pattern generation rules:**

For Python packages:
```python
# import {import_name}
f"import {import_name}"
# from {import_name}
f"from {import_name}"
```

For Node packages:
```python
# import ... from '{import_name}'
f"from ['\"]{{re.escape(import_name)}}['\"]"
# require('{import_name}')
f"require\(['\"]{{re.escape(import_name)}}['\"]"
```

Generated patterns are tagged `source: "dependency_resolved"` to distinguish them from default patterns in output.

---

### 5. Manifest Overrides

Extend `network-footprint.yaml` to support import name overrides for edge cases Claude or the lookup table gets wrong:

```yaml
overrides:
  imports:
    - package: pillow
      imports_as: PIL
    - package: opencv-python
      imports_as: cv2
  patterns:
    add:
      - pattern: "myInternalClient\\("
        category: network_call
        stack: node
    remove:
      - "\\burl\\("   # too noisy in this repo
```

Override resolution order:
1. Manifest `overrides.imports` (highest priority)
2. Hardcoded lookup table
3. Claude classifier (fallback)

---

### 6. Updated `Scanner` Flow

```
1. Load manifest
2. Parse dependency manifests → raw package list
3. Resolve packages → { package, import_name, network_capable, category }
4. Generate patterns from resolved imports
5. Merge with default pattern packs
6. Apply manifest pattern overrides (add/remove)
7. Run scan (same as Phase 1)
8. Tag each match with source: "default" | "dependency_resolved" | "custom"
```

---

### 7. Updated Output

Add `source` field to each match:

```json
[
  {
    "file": "src/services/payment.ts",
    "categories": ["network_call"],
    "matches": [
      {
        "pattern": "from ['\"]stripe['\"]",
        "category": "network_call",
        "stack": "node",
        "line": 1,
        "source": "dependency_resolved"
      }
    ]
  }
]
```

---

## Exit Criteria
- [ ] All supported manifest files parsed correctly when present
- [ ] Known packages resolved from lookup table without Claude call
- [ ] Unknown packages batched into a single Claude call
- [ ] Claude fallback fails gracefully — scan still completes
- [ ] Manifest import overrides take precedence over lookup table and Claude
- [ ] Manifest pattern add/remove overrides applied correctly
- [ ] Generated patterns match actual import statements in test fixtures
- [ ] `source` field present on all matches in output
- [ ] Transitive deps flagged separately in output
