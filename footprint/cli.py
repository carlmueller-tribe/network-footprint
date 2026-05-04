from __future__ import annotations

from pathlib import Path

import click

from footprint.coverage import analyze_coverage
from footprint.manifest import load_manifest
from footprint.patterns import PatternSpec
from footprint.report import format_flat, format_json, format_markdown
from footprint.resolver import generate_patterns, parse_all, resolve_packages
from footprint.scanner import Scanner


@click.group()
def main() -> None:
    """Scan repositories for network traffic patterns and API endpoints."""


@main.command()
@click.argument("repo_path", default=".", type=click.Path(exists=True))
@click.option("--output", default="json", type=click.Choice(["json", "flat", "markdown"]))
@click.option("--manifest", "manifest_path", default=None, type=click.Path(exists=True))
@click.option(
    "--no-resolve",
    is_flag=True,
    default=False,
    help="Skip dependency resolution (use default patterns only)",
)
@click.option(
    "--min-confidence",
    default=0.0,
    type=float,
    help="Only show matches at or above this confidence (0.0–1.0)",
)
@click.option(
    "--no-transitive",
    is_flag=True,
    default=False,
    help="Exclude matches from transitive dependencies",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Print scan details to stderr (does not affect stdout output)",
)
def scan(
    repo_path: str,
    output: str,
    manifest_path: str | None,
    no_resolve: bool,
    min_confidence: float,
    no_transitive: bool,
    verbose: bool,
) -> None:
    root = Path(repo_path).resolve()
    manifest = load_manifest(root, Path(manifest_path) if manifest_path else None)

    if verbose:
        click.echo(f"[footprint] repo: {root}", err=True)
        click.echo(f"[footprint] stacks: {manifest.stacks}", err=True)
        click.echo(f"[footprint] exclude patterns: {len(manifest.exclude)}", err=True)

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
            if verbose:
                click.echo(f"[footprint] deps parsed: {len(deps)}", err=True)
                lookup_n = sum(1 for r in resolved if r.source == "lookup")
                claude_resolved = [r for r in resolved if r.source == "claude"]
                unknown_n = sum(1 for r in resolved if r.source == "unknown_package")
                click.echo(f"[footprint] resolved from lookup: {lookup_n}", err=True)
                if claude_resolved:
                    click.echo(f"[footprint] resolved via Claude: {len(claude_resolved)}", err=True)
                    for cr in claude_resolved:
                        tag = cr.category or "not network-capable"
                        click.echo(f"[footprint]   {cr.package} → {tag}", err=True)
                elif unknown_n:
                    click.echo(
                        f"[footprint] Claude unavailable — {unknown_n} pkg(s) treated as unknown",
                        err=True,
                    )
                else:
                    click.echo(
                        "[footprint] Claude not needed — all packages resolved from lookup",
                        err=True,
                    )
                click.echo(f"[footprint] extra patterns generated: {len(extra_patterns)}", err=True)
        except Exception as exc:  # noqa: BLE001
            click.echo(f"Warning: dependency resolution failed: {exc}", err=True)

    scanner = Scanner(
        str(root), manifest, extra_patterns=extra_patterns, remove_patterns=remove_patterns
    )
    results = scanner.run()

    if verbose:
        total_matches = sum(len(r.matches) for r in results)
        click.echo(f"[footprint] files matched: {len(results)}", err=True)
        click.echo(f"[footprint] total matches: {total_matches}", err=True)

    if no_transitive or min_confidence > 0.0:
        for r in results:
            r.matches = [
                m
                for m in r.matches
                if (not no_transitive or not m.transitive) and m.confidence >= min_confidence
            ]
        results = [r for r in results if r.matches]
        for r in results:
            r.categories = sorted({m.category for m in r.matches})

    analyze_coverage(results)

    if output == "json":
        click.echo(format_json(results, repo=str(root)))
    elif output == "markdown":
        click.echo(format_markdown(results, repo_root=str(root)))
    else:
        flat = format_flat(results)
        if flat:
            click.echo(flat)
