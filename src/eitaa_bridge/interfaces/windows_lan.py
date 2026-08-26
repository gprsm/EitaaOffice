from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from ..errors import BridgeError
from ..infrastructure.config import BridgeConfigLoader
from ..infrastructure.windows_lan import (
    WindowsLanInstanceLock,
    build_windows_firewall_plan,
    validate_windows_lan_runtime,
)
from .http_api import main as http_main


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate, plan, or run Eitaa Bridge on an explicitly configured private LAN."
    )
    parser.add_argument("action", choices=("check", "start", "firewall-plan"))
    parser.add_argument("--config", default="bridge.json")
    parser.add_argument("--env-file")
    parser.add_argument("--ui-root", default="ui/dist")
    parser.add_argument("--lock-file")
    parser.add_argument("--output", type=Path, help="Optional JSON output for firewall-plan.")
    parser.add_argument("--rule-name", default="Eitaa Bridge Trusted LAN")
    return parser


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config_path = Path(args.config).expanduser().resolve()
    ui_root = Path(args.ui_root).expanduser().resolve()
    try:
        config = BridgeConfigLoader.load(config_path, env_file=args.env_file)
        summary = validate_windows_lan_runtime(config, ui_root)
        if args.action == "check":
            _print_json(summary)
            return 0
        if args.action == "firewall-plan":
            payload = build_windows_firewall_plan(
                config,
                rule_name=args.rule_name,
            ).as_dict()
            if args.output is not None:
                output = args.output.expanduser().resolve()
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
            _print_json(payload)
            return 0

        lock_file = (
            Path(args.lock_file).expanduser().resolve()
            if args.lock_file
            else config.source_file.parent / "runtime" / "operations" / "trusted-lan-http.lock"
        )
        http_args = ["--config", str(config_path), "--ui-root", str(ui_root)]
        if args.env_file:
            http_args.extend(("--env-file", str(Path(args.env_file).expanduser().resolve())))
        with WindowsLanInstanceLock(
            lock_file,
            deployment_mode=config.deployment.mode,
        ):
            return http_main(http_args)
    except BridgeError as exc:
        print(f"{exc.component}: {exc.code}: {exc.message}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"windows_lan: operation_failed: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
