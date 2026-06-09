from pathlib import Path

import yaml

from footprint.manifest import DEFAULT_EXCLUDES, DEFAULT_STACKS, ManifestConfig, load_manifest


def test_fallback_when_no_manifest(tmp_path: Path) -> None:
    config = load_manifest(tmp_path)
    assert config.stacks == DEFAULT_STACKS
    assert config.exclude == DEFAULT_EXCLUDES


def test_load_stacks_and_exclude(tmp_path: Path) -> None:
    (tmp_path / "network-footprint.yaml").write_text(
        yaml.dump({"stacks": ["node"], "exclude": ["node_modules", "dist"]})
    )
    config = load_manifest(tmp_path)
    assert config.stacks == ["node"]
    assert config.exclude == ["node_modules", "dist"]


def test_load_explicit_path(tmp_path: Path) -> None:
    custom = tmp_path / "custom.yaml"
    custom.write_text(yaml.dump({"stacks": ["python"]}))
    config = load_manifest(tmp_path, manifest_path=custom)
    assert config.stacks == ["python"]
    assert config.exclude == DEFAULT_EXCLUDES


def test_empty_file_uses_defaults(tmp_path: Path) -> None:
    (tmp_path / "network-footprint.yaml").write_text("")
    config = load_manifest(tmp_path)
    assert config.stacks == DEFAULT_STACKS
    assert config.exclude == DEFAULT_EXCLUDES


def test_partial_config_fills_missing_with_defaults(tmp_path: Path) -> None:
    (tmp_path / "network-footprint.yaml").write_text(yaml.dump({"stacks": ["devops"]}))
    config = load_manifest(tmp_path)
    assert config.stacks == ["devops"]
    assert config.exclude == DEFAULT_EXCLUDES


def test_manifest_config_is_dataclass() -> None:
    config = ManifestConfig(stacks=["node"], exclude=["node_modules"])
    assert config.stacks == ["node"]
    assert config.exclude == ["node_modules"]


def test_malformed_yaml_falls_back_to_defaults(tmp_path: Path) -> None:
    (tmp_path / "network-footprint.yaml").write_text("stacks: [unclosed bracket")
    config = load_manifest(tmp_path)
    assert config.stacks == DEFAULT_STACKS
    assert config.exclude == DEFAULT_EXCLUDES


def test_non_dict_yaml_root_falls_back_to_defaults(tmp_path: Path) -> None:
    (tmp_path / "network-footprint.yaml").write_text("- node\n- python\n")
    config = load_manifest(tmp_path)
    assert config.stacks == DEFAULT_STACKS
    assert config.exclude == DEFAULT_EXCLUDES


def test_null_stack_value_falls_back_to_default(tmp_path: Path) -> None:
    (tmp_path / "network-footprint.yaml").write_text("stacks: null\n")
    config = load_manifest(tmp_path)
    assert config.stacks == DEFAULT_STACKS


def test_default_reference_is_not_shared(tmp_path: Path) -> None:
    config = load_manifest(tmp_path)
    config.stacks.append("mutated")
    from footprint.manifest import DEFAULT_STACKS as DS

    assert "mutated" not in DS, "load_manifest fallback must not share DEFAULT_STACKS reference"
