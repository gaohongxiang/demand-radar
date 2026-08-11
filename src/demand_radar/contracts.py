from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from demand_radar.errors import UnsupportedCapabilityError


class ProviderRole(StrEnum):
    COLLECTOR = "collector"
    PUBLISHER = "publisher"


class Capability(StrEnum):
    COLLECT_NOTES = "collect_notes"
    COLLECT_COMMENTS = "collect_comments"
    PUBLISH_NOTE = "publish_note"
    PUBLISH_VIDEO = "publish_video"
    POST_COMMENT = "post_comment"
    REPLY_COMMENT = "reply_comment"


class RecordType(StrEnum):
    NOTE = "note"
    COMMENT = "comment"


@dataclass(frozen=True)
class ProviderDescriptor:
    name: str
    role: ProviderRole
    capabilities: frozenset[Capability]
    upstream_url: str | None = None


@dataclass(frozen=True)
class HealthReport:
    ok: bool
    message: str
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RawArtifact:
    kind: str
    path: Path
    record_count: int


@dataclass(frozen=True)
class CollectionRequest:
    run_id: str
    keywords: tuple[str, ...]
    output_dir: Path
    max_notes: int = 20
    max_comments: int = 10
    include_comments: bool = True
    include_sub_comments: bool = False
    options: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CollectionResult:
    provider: str
    run_id: str
    started_at: str
    finished_at: str
    artifacts: tuple[RawArtifact, ...]
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CanonicalRecord:
    record_type: RecordType
    platform: str
    provider: str
    external_id: str
    collected_at: str
    text: str = ""
    title: str = ""
    note_external_id: str | None = None
    parent_external_id: str | None = None
    author_id: str | None = None
    author_name: str | None = None
    published_at: int | None = None
    canonical_url: str | None = None
    observed_url: str | None = None
    source_keyword: str | None = None
    metrics: Mapping[str, int] = field(default_factory=dict)
    tags: tuple[str, ...] = ()
    media: tuple[str, ...] = ()
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "record_type": self.record_type.value,
            "platform": self.platform,
            "provider": self.provider,
            "external_id": self.external_id,
            "note_external_id": self.note_external_id,
            "parent_external_id": self.parent_external_id,
            "title": self.title,
            "text": self.text,
            "author_id": self.author_id,
            "author_name": self.author_name,
            "published_at": self.published_at,
            "canonical_url": self.canonical_url,
            "observed_url": self.observed_url,
            "source_keyword": self.source_keyword,
            "metrics": dict(self.metrics),
            "tags": list(self.tags),
            "media": list(self.media),
            "collected_at": self.collected_at,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> CanonicalRecord:
        return cls(
            schema_version=int(value.get("schema_version", 1)),
            record_type=RecordType(str(value["record_type"])),
            platform=str(value["platform"]),
            provider=str(value["provider"]),
            external_id=str(value["external_id"]),
            note_external_id=_optional_string(value.get("note_external_id")),
            parent_external_id=_optional_string(value.get("parent_external_id")),
            title=str(value.get("title") or ""),
            text=str(value.get("text") or ""),
            author_id=_optional_string(value.get("author_id")),
            author_name=_optional_string(value.get("author_name")),
            published_at=_optional_int(value.get("published_at")),
            canonical_url=_optional_string(value.get("canonical_url")),
            observed_url=_optional_string(value.get("observed_url")),
            source_keyword=_optional_string(value.get("source_keyword")),
            metrics={str(k): int(v or 0) for k, v in dict(value.get("metrics") or {}).items()},
            tags=tuple(str(item) for item in value.get("tags") or ()),
            media=tuple(str(item) for item in value.get("media") or ()),
            collected_at=str(value["collected_at"]),
        )


def _optional_string(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


class CollectorProvider(ABC):
    @property
    @abstractmethod
    def descriptor(self) -> ProviderDescriptor:
        raise NotImplementedError

    @abstractmethod
    def health(self) -> HealthReport:
        raise NotImplementedError

    @abstractmethod
    def collect(self, request: CollectionRequest) -> CollectionResult:
        raise NotImplementedError

    @abstractmethod
    def normalize(self, result: CollectionResult) -> Iterable[CanonicalRecord]:
        raise NotImplementedError


@dataclass(frozen=True)
class PublishNoteRequest:
    title: str
    content: str
    image_paths: tuple[Path, ...] = ()
    video_path: Path | None = None
    tags: tuple[str, ...] = ()
    idempotency_key: str | None = None


@dataclass(frozen=True)
class CommentRequest:
    note_external_id: str
    content: str
    idempotency_key: str | None = None


@dataclass(frozen=True)
class ReplyRequest:
    note_external_id: str
    comment_external_id: str
    content: str
    idempotency_key: str | None = None


@dataclass(frozen=True)
class PublishResult:
    provider: str
    action: Capability
    success: bool
    external_id: str | None = None
    url: str | None = None
    message: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


class PublisherProvider(ABC):
    @property
    @abstractmethod
    def descriptor(self) -> ProviderDescriptor:
        raise NotImplementedError

    @abstractmethod
    def health(self) -> HealthReport:
        raise NotImplementedError

    def publish_note(self, request: PublishNoteRequest) -> PublishResult:
        self._unsupported(Capability.PUBLISH_NOTE)

    def post_comment(self, request: CommentRequest) -> PublishResult:
        self._unsupported(Capability.POST_COMMENT)

    def reply_comment(self, request: ReplyRequest) -> PublishResult:
        self._unsupported(Capability.REPLY_COMMENT)

    def _unsupported(self, capability: Capability) -> None:
        raise UnsupportedCapabilityError(
            f"Provider {self.descriptor.name!r} does not support {capability.value!r}"
        )


def require_capability(descriptor: ProviderDescriptor, capability: Capability) -> None:
    if capability not in descriptor.capabilities:
        raise UnsupportedCapabilityError(
            f"Provider {descriptor.name!r} does not support {capability.value!r}"
        )


def clean_keywords(values: Sequence[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = raw.strip()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)
