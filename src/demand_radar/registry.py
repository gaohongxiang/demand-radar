from __future__ import annotations

from demand_radar.contracts import (
    Capability,
    CollectorProvider,
    PublisherProvider,
    require_capability,
)
from demand_radar.errors import ConfigurationError, ProviderNotFoundError


class ProviderRegistry:
    def __init__(self) -> None:
        self._collectors: dict[str, CollectorProvider] = {}
        self._publishers: dict[str, PublisherProvider] = {}

    def register_collector(self, provider: CollectorProvider) -> None:
        name = provider.descriptor.name
        if name in self._collectors:
            raise ConfigurationError(f"Collector provider already registered: {name}")
        self._collectors[name] = provider

    def register_publisher(self, provider: PublisherProvider) -> None:
        name = provider.descriptor.name
        if name in self._publishers:
            raise ConfigurationError(f"Publisher provider already registered: {name}")
        self._publishers[name] = provider

    def collector(
        self, name: str, capability: Capability = Capability.COLLECT_NOTES
    ) -> CollectorProvider:
        try:
            provider = self._collectors[name]
        except KeyError as exc:
            raise ProviderNotFoundError(f"Collector provider not enabled: {name}") from exc
        require_capability(provider.descriptor, capability)
        return provider

    def publisher(self, name: str, capability: Capability) -> PublisherProvider:
        try:
            provider = self._publishers[name]
        except KeyError as exc:
            raise ProviderNotFoundError(f"Publisher provider not enabled: {name}") from exc
        require_capability(provider.descriptor, capability)
        return provider

    @property
    def collectors(self) -> tuple[CollectorProvider, ...]:
        return tuple(self._collectors.values())

    @property
    def publishers(self) -> tuple[PublisherProvider, ...]:
        return tuple(self._publishers.values())
