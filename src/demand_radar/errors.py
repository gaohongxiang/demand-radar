class DemandRadarError(Exception):
    """Base exception for expected application failures."""


class ConfigurationError(DemandRadarError):
    """Provider or project configuration is invalid."""


class ProviderNotFoundError(DemandRadarError):
    """A requested provider is not registered or enabled."""


class UnsupportedCapabilityError(DemandRadarError):
    """A provider does not implement a requested capability."""


class ProviderUnhealthyError(DemandRadarError):
    """A provider cannot safely be executed."""


class ProviderExecutionError(DemandRadarError):
    """An external provider failed while running."""


class ProviderDataError(DemandRadarError):
    """A provider emitted malformed or unsupported data."""


class EmptyCollectionError(DemandRadarError):
    """A collection run yielded no notes and must not look successful."""
