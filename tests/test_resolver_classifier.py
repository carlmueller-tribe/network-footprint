from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

from footprint.resolver import (
    ParsedDep,
    resolve_packages,
)


def test_known_package_resolved_from_lookup_no_claude() -> None:
    deps = [ParsedDep(name="axios", ecosystem="node")]
    with patch("footprint.resolver._classify_with_claude") as mock_claude:
        results = resolve_packages(deps)
        mock_claude.assert_not_called()
    r = next(r for r in results if r.package == "axios")
    assert r.network_capable is True
    assert r.import_name == "axios"
    assert r.category == "network_call"
    assert r.source == "lookup"


def test_known_package_pillow_not_network_capable() -> None:
    deps = [ParsedDep(name="pillow", ecosystem="python")]
    results = resolve_packages(deps)
    r = next(r for r in results if r.package == "pillow")
    assert r.network_capable is False
    assert r.import_name == "PIL"


def test_unknown_package_batched_to_claude() -> None:
    deps = [
        ParsedDep(name="stripe", ecosystem="node"),
        ParsedDep(name="twilio", ecosystem="node"),
    ]
    claude_response = json.dumps(
        [
            {
                "package": "stripe",
                "network_capable": True,
                "import_name": "stripe",
                "category": "network_call",
            },
            {
                "package": "twilio",
                "network_capable": True,
                "import_name": "twilio",
                "category": "network_call",
            },
        ]
    )
    with patch(
        "footprint.resolver._classify_with_claude", return_value=claude_response
    ) as mock_claude:
        results = resolve_packages(deps)
        mock_claude.assert_called_once()  # batched — not called twice

    stripe = next(r for r in results if r.package == "stripe")
    assert stripe.network_capable is True
    assert stripe.source == "claude"


def test_unknown_packages_and_known_mixed() -> None:
    deps = [
        ParsedDep(name="requests", ecosystem="python"),  # known
        ParsedDep(name="stripe", ecosystem="node"),  # unknown
    ]
    claude_response = json.dumps(
        [
            {
                "package": "stripe",
                "network_capable": True,
                "import_name": "stripe",
                "category": "network_call",
            },
        ]
    )
    with patch("footprint.resolver._classify_with_claude", return_value=claude_response):
        results = resolve_packages(deps)

    assert any(r.package == "requests" and r.source == "lookup" for r in results)
    assert any(r.package == "stripe" and r.source == "claude" for r in results)


def test_claude_failure_treated_as_non_network() -> None:
    deps = [ParsedDep(name="unknown-pkg", ecosystem="node")]
    with patch("footprint.resolver._classify_with_claude", side_effect=RuntimeError("no auth")):
        results = resolve_packages(deps)
    r = next(r for r in results if r.package == "unknown-pkg")
    assert r.network_capable is False
    assert r.source == "claude_failed"


def test_transitive_flag_preserved() -> None:
    deps = [ParsedDep(name="axios", ecosystem="node", transitive=True)]
    results = resolve_packages(deps)
    r = next(r for r in results if r.package == "axios")
    assert r.transitive is True


def test_claude_subprocess_tried_before_sdk() -> None:
    deps = [ParsedDep(name="stripe", ecosystem="node")]
    claude_json = json.dumps(
        [
            {
                "package": "stripe",
                "network_capable": True,
                "import_name": "stripe",
                "category": "network_call",
            },
        ]
    )
    with (
        patch("shutil.which", return_value="/usr/local/bin/claude"),
        patch("subprocess.run") as mock_run,
        patch("footprint.resolver._classify_with_sdk") as mock_sdk,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout=claude_json, stderr="")
        resolve_packages(deps)
        mock_run.assert_called_once()
        mock_sdk.assert_not_called()


def test_sdk_used_when_claude_cli_absent() -> None:
    deps = [ParsedDep(name="stripe", ecosystem="node")]
    sdk_json = json.dumps(
        [
            {
                "package": "stripe",
                "network_capable": True,
                "import_name": "stripe",
                "category": "network_call",
            },
        ]
    )
    with (
        patch("shutil.which", return_value=None),
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}),
        patch("footprint.resolver._classify_with_sdk", return_value=sdk_json) as mock_sdk,
    ):
        resolve_packages(deps)
        mock_sdk.assert_called_once()


def test_manifest_override_sets_import_name_and_source() -> None:
    deps = [ParsedDep(name="some-internal-pkg", ecosystem="node")]
    with patch("footprint.resolver._classify_with_claude") as mock_claude:
        results = resolve_packages(deps, overrides={"some-internal-pkg": "internalPkg"})
        mock_claude.assert_not_called()
    r = next(r for r in results if r.package == "some-internal-pkg")
    assert r.import_name == "internalPkg"
    assert r.source == "manifest_override"
