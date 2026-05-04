from __future__ import annotations

from pathlib import Path

import click

from footprint.manifest import load_manifest
from footprint.patterns import PatternSpec
from footprint.report import format_flat, format_json
from footprint.resolver import generate_patterns, parse_all, resolve_packages
from footprint.scanner import Scanner


@click.group()
def main() -> None:
    """Scan repositories for network traffic patterns and API endpoints."""


@main.command()
@click.argument("repo_path", default=".", type=click.Path(exists=True))
@click.option("--output", default="json", type=click.Choice(["json", "flat"]))
@click.option("--manifest", "manifest_path", default=None, type=click.Path(exists=True))
@click.option(
    "--no-resolve",
    is_flag=True,
    default=False,
    help="Skip dependency resolution (use default patterns only)",
)
def scan(
    repo_path: str,
    output: str,
    manifest_path: str | None,
    no_resolve: bool,
) -> None:
    root = Path(repo_path).resolve()
    manifest = load_manifest(root, Path(manifest_path) if manifest_path else None)

    extra_patterns: list[PatternSpec] = []
    remove_patterns: list[str] = []

    if manifest.overrides:
        extra_patterns.extend(manifest.overrides.patterns.add)
        remove_patterns = list(manifest.overrides.patterns.remove)

    if not no_resolve:
        import_overrides: dict[str, str] = {}
        if manifest.overrides:
            import_overrides = {o.package: o.imports_as for o in manifest.overrides.imports}
        try:
            deps = parse_all(root)
            resolved = resolve_packages(deps, overrides=import_overrides)
            network_capable = [r for r in resolved if r.network_capable]
            for ecosystem in ("python", "node"):
                extra_patterns.extend(generate_patterns(network_capable, ecosystem=ecosystem))
        except Exception as exc:  # noqa: BLE001
            click.echo(f"Warning: dependency resolution failed: {exc}", err=True)

    scanner = Scanner(
        str(root), manifest, extra_patterns=extra_patterns, remove_patterns=remove_patterns
    )
    results = scanner.run()

    if output == "json":
        click.echo(format_json(results))
    else:
        flat = format_flat(results)
        if flat:
            click.echo(flat)
