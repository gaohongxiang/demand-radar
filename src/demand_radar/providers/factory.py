from __future__ import annotations

from typing import Any, Sequence

from demand_radar.config import AppConfig, ProviderConfig
from demand_radar.errors import ConfigurationError
from demand_radar.providers.collectors.manual_import import ManualImportCollector
from demand_radar.providers.collectors.mediacrawler import MediaCrawlerCollector
from demand_radar.registry import ProviderRegistry


def build_registry(config: AppConfig) -> ProviderRegistry:
    registry = ProviderRegistry()
    for provider_config in config.collectors.values():
        if not provider_config.enabled:
            continue
        registry.register_collector(_build_collector(config, provider_config))

    for provider_config in config.publishers.values():
        if provider_config.enabled:
            raise ConfigurationError(
                f"Publisher adapter {provider_config.adapter!r} is configured but not implemented yet"
            )
    return registry


def _build_collector(config: AppConfig, provider: ProviderConfig):
    if provider.adapter == "manual_import":
        return ManualImportCollector(name=provider.name)
    if provider.adapter == "mediacrawler":
        options = provider.options
        command = _string_sequence(options.get("command", ["uv", "run", "main.py"]), "command")
        return MediaCrawlerCollector(
            name=provider.name,
            home=config.resolve_path(_required(options, "home", provider.name)),
            command=command,
            login_type=str(options.get("login_type", "qrcode")),
            headless=bool(options.get("headless", False)),
            max_concurrency=int(options.get("max_concurrency", 1)),
            timeout_seconds=int(options.get("timeout_seconds", 3600)),
        )
    raise ConfigurationError(
        f"Unknown collector adapter {provider.adapter!r} for {provider.name!r}"
    )


def _required(options: dict[str, Any] | Any, key: str, name: str) -> Any:
    value = options.get(key)
    if value is None or value == "":
        raise ConfigurationError(f"Provider {name!r} must define {key!r}")
    return value


def _string_sequence(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ConfigurationError(f"{label} must be a list of command arguments")
    result = tuple(str(item) for item in value)
    if not result:
        raise ConfigurationError(f"{label} must not be empty")
    return result
