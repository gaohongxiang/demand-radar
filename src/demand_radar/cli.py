from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence

from demand_radar.config import AppConfig, load_config
from demand_radar.errors import DemandRadarError
from demand_radar.pipeline.collect import run_collection
from demand_radar.providers.factory import build_registry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="demand-radar")
    parser.add_argument(
        "--config",
        default=os.environ.get("DEMAND_RADAR_CONFIG", "config/providers.yaml"),
        help="Provider YAML config (default: config/providers.yaml)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("providers", help="List configured providers and health")

    collect = subparsers.add_parser("collect", help="Run one collector provider")
    collect.add_argument("--provider", required=True)
    collect.add_argument("--keyword", action="append", default=[])
    collect.add_argument("--input", action="append", default=[])
    collect.add_argument("--max-notes", type=int, default=20)
    collect.add_argument("--max-comments", type=int, default=10)
    collect.add_argument("--no-comments", action="store_true")
    collect.add_argument("--sub-comments", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "providers":
            return _show_providers(config)
        if args.command == "collect":
            return _collect(config, args)
        parser.error(f"Unknown command: {args.command}")
    except DemandRadarError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


def _show_providers(config: AppConfig) -> int:
    registry = build_registry(config)
    rows: list[dict[str, object]] = []
    enabled_collectors = {item.descriptor.name: item for item in registry.collectors}
    for provider_config in config.collectors.values():
        row: dict[str, object] = {
            "name": provider_config.name,
            "role": "collector",
            "adapter": provider_config.adapter,
            "enabled": provider_config.enabled,
        }
        provider = enabled_collectors.get(provider_config.name)
        if provider is not None:
            health = provider.health()
            row["healthy"] = health.ok
            row["message"] = health.message
            row["details"] = dict(health.details)
        rows.append(row)

    for provider_config in config.publishers.values():
        rows.append(
            {
                "name": provider_config.name,
                "role": "publisher",
                "adapter": provider_config.adapter,
                "enabled": provider_config.enabled,
                "capabilities": list(provider_config.options.get("capabilities") or ()),
                "message": "disabled" if not provider_config.enabled else "enabled",
            }
        )
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


def _collect(config: AppConfig, args: argparse.Namespace) -> int:
    registry = build_registry(config)
    provider = registry.collector(args.provider)
    options = {
        "input_paths": [str(Path(item).expanduser().resolve()) for item in args.input]
    }
    manifest = run_collection(
        provider=provider,
        project_root=config.project_root,
        keywords=args.keyword,
        max_notes=args.max_notes,
        max_comments=args.max_comments,
        include_comments=not args.no_comments,
        include_sub_comments=args.sub_comments,
        options=options,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
