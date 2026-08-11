from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import yaml

from demand_radar.errors import ConfigurationError


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    role: str
    adapter: str
    enabled: bool
    options: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AppConfig:
    source_path: Path
    project_root: Path
    collectors: Mapping[str, ProviderConfig]
    publishers: Mapping[str, ProviderConfig]
    policy: Mapping[str, Any]

    def resolve_path(self, value: str | Path) -> Path:
        path = Path(value).expanduser()
        if path.is_absolute():
            return path.resolve()
        return (self.project_root / path).resolve()


def load_config(path: str | Path) -> AppConfig:
    source_path = Path(path).expanduser().resolve()
    if not source_path.is_file():
        raise ConfigurationError(f"Config file not found: {source_path}")

    try:
        raw = yaml.safe_load(source_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Invalid YAML in {source_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigurationError("Top-level configuration must be a mapping")
    if int(raw.get("version", 0)) != 1:
        raise ConfigurationError("Only provider configuration version 1 is supported")

    root_value = raw.get("project_root")
    if root_value is None:
        project_root = source_path.parent.parent.resolve()
    else:
        project_root = (source_path.parent / str(root_value)).expanduser().resolve()

    return AppConfig(
        source_path=source_path,
        project_root=project_root,
        collectors=_provider_group(raw.get("collectors"), "collector"),
        publishers=_provider_group(raw.get("publishers"), "publisher"),
        policy=_mapping(raw.get("policy"), "policy"),
    )


def _provider_group(value: Any, role: str) -> dict[str, ProviderConfig]:
    group = _mapping(value, f"{role}s")
    result: dict[str, ProviderConfig] = {}
    for name, raw_options in group.items():
        options = _mapping(raw_options, f"{role} {name}")
        adapter = str(options.get("adapter") or "").strip()
        if not adapter:
            raise ConfigurationError(f"{role} {name!r} must define adapter")
        enabled = bool(options.get("enabled", False))
        adapter_options = {
            str(key): option
            for key, option in options.items()
            if key not in {"adapter", "enabled"}
        }
        result[str(name)] = ProviderConfig(
            name=str(name),
            role=role,
            adapter=adapter,
            enabled=enabled,
            options=adapter_options,
        )
    return result


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigurationError(f"{label} must be a mapping")
    return dict(value)
