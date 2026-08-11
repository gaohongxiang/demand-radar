from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from demand_radar.contracts import (
    CanonicalRecord,
    Capability,
    CollectionRequest,
    CollectionResult,
    CollectorProvider,
    HealthReport,
    ProviderDescriptor,
    ProviderRole,
    RawArtifact,
    RecordType,
)
from demand_radar.errors import ProviderDataError, ProviderExecutionError


class MediaCrawlerCollector(CollectorProvider):
    """CLI adapter for an untouched, sibling MediaCrawler checkout."""

    def __init__(
        self,
        *,
        name: str,
        home: Path,
        command: Sequence[str] = ("uv", "run", "main.py"),
        login_type: str = "qrcode",
        headless: bool = False,
        max_concurrency: int = 1,
        timeout_seconds: int = 3600,
    ) -> None:
        self.name = name
        self.home = home.resolve()
        self.command = tuple(str(item) for item in command)
        self.login_type = login_type
        self.headless = headless
        self.max_concurrency = max_concurrency
        self.timeout_seconds = timeout_seconds

    @property
    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            name=self.name,
            role=ProviderRole.COLLECTOR,
            capabilities=frozenset(
                {Capability.COLLECT_NOTES, Capability.COLLECT_COMMENTS}
            ),
            upstream_url="https://github.com/NanmiCoder/MediaCrawler",
        )

    def health(self) -> HealthReport:
        problems: list[str] = []
        if not self.home.is_dir():
            problems.append(f"repository directory not found: {self.home}")
        if not (self.home / ".git").exists():
            problems.append("repository is not an independent Git checkout")
        if not (self.home / "main.py").is_file():
            problems.append("main.py not found")
        if not self.command:
            problems.append("command is empty")
        elif not _command_exists(self.command[0], self.home):
            problems.append(f"executable not found: {self.command[0]}")

        revision = self._git_revision()
        details: dict[str, Any] = {
            "home": str(self.home),
            "command": list(self.command),
            "resolved_executable": _resolve_executable(self.command[0], self.home)
            if self.command
            else None,
            "revision": revision,
        }
        if problems:
            return HealthReport(False, "; ".join(problems), details)
        return HealthReport(True, "ready", details)

    def build_command(self, request: CollectionRequest) -> tuple[str, ...]:
        if not request.keywords:
            raise ProviderExecutionError("MediaCrawler requires at least one keyword")
        resolved_command = list(self.command)
        resolved_command[0] = _resolve_executable(resolved_command[0], self.home) or resolved_command[0]
        return tuple(resolved_command) + (
            "--platform",
            "xhs",
            "--lt",
            self.login_type,
            "--type",
            "search",
            "--keywords",
            ",".join(request.keywords),
            "--get_comment",
            _yes_no(request.include_comments),
            "--get_sub_comment",
            _yes_no(request.include_sub_comments),
            "--save_data_option",
            "jsonl",
            "--crawler_max_notes_count",
            str(request.max_notes),
            "--max_comments_count_singlenotes",
            str(request.max_comments),
            "--max_concurrency_num",
            str(self.max_concurrency),
            "--headless",
            _yes_no(self.headless),
            "--save_data_path",
            str(request.output_dir.resolve()),
        )

    def collect(self, request: CollectionRequest) -> CollectionResult:
        started_at = _now()
        request.output_dir.mkdir(parents=True, exist_ok=True)
        command = self.build_command(request)
        environment = dict(os.environ)
        environment.setdefault("PYTHONUTF8", "1")

        try:
            completed = subprocess.run(
                command,
                cwd=self.home,
                env=environment,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except FileNotFoundError as exc:
            raise ProviderExecutionError(
                f"MediaCrawler executable not found: {command[0]}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise ProviderExecutionError(
                f"MediaCrawler exceeded timeout ({self.timeout_seconds}s)"
            ) from exc

        stdout_path = request.output_dir / "provider.stdout.log"
        stderr_path = request.output_dir / "provider.stderr.log"
        stdout_path.write_text(completed.stdout or "", encoding="utf-8")
        stderr_path.write_text(completed.stderr or "", encoding="utf-8")

        if completed.returncode != 0:
            error_tail = (completed.stderr or completed.stdout or "").strip()[-2000:]
            raise ProviderExecutionError(
                f"MediaCrawler exited with code {completed.returncode}: {error_tail}"
            )

        artifacts = self._discover_artifacts(request.output_dir)
        warnings: list[str] = []
        if request.include_comments and not any(
            artifact.kind == "comments" for artifact in artifacts
        ):
            warnings.append("No comment artifact was emitted")

        return CollectionResult(
            provider=self.name,
            run_id=request.run_id,
            started_at=started_at,
            finished_at=_now(),
            artifacts=artifacts,
            warnings=tuple(warnings),
            metadata={
                "revision": self._git_revision(),
                "command": list(command),
                "stdout_log": str(stdout_path),
                "stderr_log": str(stderr_path),
            },
        )

    def normalize(self, result: CollectionResult) -> Iterable[CanonicalRecord]:
        collected_at = result.finished_at
        for artifact in result.artifacts:
            if artifact.kind not in {"notes", "comments"}:
                continue
            for value in _read_jsonl(artifact.path):
                if artifact.kind == "notes":
                    record = self._normalize_note(value, collected_at)
                else:
                    record = self._normalize_comment(value, collected_at)
                if record is not None:
                    yield record

    def _discover_artifacts(self, output_dir: Path) -> tuple[RawArtifact, ...]:
        jsonl_dir = output_dir / "xhs" / "jsonl"
        patterns = (("notes", "search_contents_*.jsonl"), ("comments", "search_comments_*.jsonl"))
        artifacts: list[RawArtifact] = []
        for kind, pattern in patterns:
            for path in sorted(jsonl_dir.glob(pattern)):
                artifacts.append(
                    RawArtifact(kind=kind, path=path, record_count=_count_jsonl(path))
                )
        return tuple(artifacts)

    def _normalize_note(
        self, value: Mapping[str, Any], collected_at: str
    ) -> CanonicalRecord | None:
        external_id = _text(value.get("note_id"))
        if not external_id:
            return None
        observed_url = _optional_text(value.get("note_url"))
        return CanonicalRecord(
            record_type=RecordType.NOTE,
            platform="xhs",
            provider=self.name,
            external_id=external_id,
            title=_text(value.get("title")),
            text=_text(value.get("desc")),
            author_id=_optional_text(value.get("creator_hash")),
            author_name=_optional_text(value.get("nickname")),
            published_at=_int_or_none(value.get("time")),
            canonical_url=f"https://www.xiaohongshu.com/explore/{external_id}",
            observed_url=observed_url,
            source_keyword=_optional_text(value.get("source_keyword")),
            metrics={
                "likes": _int_or_zero(value.get("liked_count")),
                "collects": _int_or_zero(value.get("collected_count")),
                "comments": _int_or_zero(value.get("comment_count")),
                "shares": _int_or_zero(value.get("share_count")),
            },
            tags=_split_list(value.get("tag_list")),
            media=_media_values(value),
            collected_at=collected_at,
        )

    def _normalize_comment(
        self, value: Mapping[str, Any], collected_at: str
    ) -> CanonicalRecord | None:
        external_id = _text(value.get("comment_id"))
        note_id = _text(value.get("note_id"))
        if not external_id or not note_id:
            return None
        return CanonicalRecord(
            record_type=RecordType.COMMENT,
            platform="xhs",
            provider=self.name,
            external_id=external_id,
            note_external_id=note_id,
            parent_external_id=_optional_text(value.get("parent_comment_id")),
            text=_text(value.get("content")),
            author_id=_optional_text(value.get("creator_hash")),
            author_name=_optional_text(value.get("nickname")),
            published_at=_int_or_none(value.get("create_time")),
            canonical_url=f"https://www.xiaohongshu.com/explore/{note_id}",
            metrics={
                "likes": _int_or_zero(value.get("like_count")),
                "replies": _int_or_zero(value.get("sub_comment_count")),
            },
            media=_split_list(value.get("pictures")),
            collected_at=collected_at,
        )

    def _git_revision(self) -> str | None:
        if not (self.home / ".git").exists():
            return None
        completed = subprocess.run(
            ["git", "-C", str(self.home), "rev-parse", "HEAD"],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        if completed.returncode != 0:
            return None
        return completed.stdout.strip() or None


def _command_exists(command: str, cwd: Path) -> bool:
    return _resolve_executable(command, cwd) is not None


def _resolve_executable(command: str, cwd: Path) -> str | None:
    candidate = Path(command).expanduser()
    if candidate.is_absolute():
        return str(candidate) if candidate.is_file() and os.access(candidate, os.X_OK) else None
    if "/" in command:
        local = (cwd / candidate).resolve()
        return str(local) if local.is_file() and os.access(local, os.X_OK) else None
    from_path = shutil.which(command)
    if from_path:
        return from_path
    # Keep the virtualenv path. Resolving the Python symlink would jump to the
    # system interpreter and hide console tools installed beside this package.
    beside_python = Path(sys.executable).parent / command
    if beside_python.is_file() and os.access(beside_python, os.X_OK):
        return str(beside_python)
    return None


def _read_jsonl(path: Path) -> Iterable[Mapping[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ProviderDataError(
                    f"Invalid JSONL at {path}:{line_number}: {exc}"
                ) from exc
            if not isinstance(value, dict):
                raise ProviderDataError(
                    f"JSONL record must be an object at {path}:{line_number}"
                )
            yield value


def _count_jsonl(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _optional_text(value: Any) -> str | None:
    result = _text(value)
    return result or None


def _int_or_zero(value: Any) -> int:
    return _int_or_none(value) or 0


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    multipliers = {"万": 10_000, "w": 10_000, "W": 10_000, "千": 1_000, "k": 1_000, "K": 1_000}
    suffix = text[-1]
    try:
        if suffix in multipliers:
            return int(float(text[:-1]) * multipliers[suffix])
        return int(float(text))
    except ValueError:
        return None


def _split_list(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return tuple(part.strip() for part in str(value).split(",") if part.strip())


def _media_values(value: Mapping[str, Any]) -> tuple[str, ...]:
    images = list(_split_list(value.get("image_list")))
    videos = list(_split_list(value.get("video_url")))
    return tuple(images + videos)
