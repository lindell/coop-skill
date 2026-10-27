"""Top-level argument parsing and command dispatch."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from coop_cli.commands import ALL_COMMANDS
from coop_cli.config import DEFAULT_COOKIE_FILE, DEFAULT_ENV_FILE


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coop",
        description="Coop.se CLI — login, search products, inspect items, manage cart, and view orders.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=DEFAULT_ENV_FILE,
        help="Path to .env file containing COOP_USERNAME and COOP_PASSWORD",
    )
    parser.add_argument(
        "--cookie-file",
        type=Path,
        default=DEFAULT_COOKIE_FILE,
        help="Path to Netscape/Mozilla format cookies file",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ALL_COMMANDS:
        command.register(subparsers)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

