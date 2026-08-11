from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Iterable, Mapping, Any

from demand_radar.contracts import CanonicalRecord, RecordType
from demand_radar.errors import EmptyCollectionError


def write_canonical_records(
    path: Path, records: Iterable[CanonicalRecord]
) -> dict[str, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    counts: Counter[str] = Counter()
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            for record in records:
                value = record.to_dict()
                counts[value["record_type"]] += 1
                handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
        if counts[RecordType.NOTE.value] == 0:
            raise EmptyCollectionError(
                "Collection returned zero notes; run marked failed to avoid a false empty report"
            )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return dict(counts)


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
