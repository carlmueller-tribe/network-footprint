from __future__ import annotations

from pathlib import Path

import click

from footprint.manifest import load_manifest
from footprint.report import format_flat, format_json
from footprint.scanner import Scanner


@click.group()
def main() -> None:
    """Scan repositories for network traffic patterns and API endpoints."""


@main.command()
@click.argument("repo_path", default=".", type=click.Path(exists=True))
@click.option(
    "--output",
    default="json",
    type=click.Choice(["json", "flat"]),
    show_default=True,
    help="Output format.",
)
@click.option(
    "--manifest",
    "manifest_path",
    default=None,
    type=click.Path(exists=True),
    help="Explicit path to network-footprint.yaml.",
)
def scan(repo_path: str, output: str, manifest_path: str | None) -> None:
    """Scan REPO_PATH for network traffic patterns."""
    root = Path(repo_path)
    mpath = Path(manifest_path) if manifest_path else None
    manifest = load_manifest(root, mpath)
    scanner = Scanner(repo_root=str(root), manifest=manifest)
    results = scanner.run()
    if output == "json":
        click.echo(format_json(results))
    else:
        flat = format_flat(results)
        if flat:
            click.echo(flat)
