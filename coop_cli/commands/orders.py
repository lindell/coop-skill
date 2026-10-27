"""`coop orders [-n <limit>] [--page <page>]` — list earlier and active orders as structured JSON."""

from __future__ import annotations

import argparse

from coop_cli.api.orders import list_orders
from coop_cli.formatting import (
    add_output_flags,
    format_orders_list,
    parse_extra_fields,
    print_json,
)


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "orders",
        aliases=["history"],
        help="List earlier and active orders on coop.se.",
    )
    p.add_argument(
        "-n",
        "--limit",
        type=int,
        default=20,
        help="Max orders per page (default: 20)",
    )
    p.add_argument(
        "--page",
        type=int,
        default=0,
        help="0-based page index for pagination (default: 0)",
    )
    add_output_flags(
        p,
        fields_help="Comma-separated extra fields to include (e.g. address,window,tracking,editable,cancellable)",
    )
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    data = list_orders(
        limit=args.limit,
        page=args.page,
        cookie_file=args.cookie_file,
        env_file=args.env_file,
    )
    if args.raw:
        print_json(data)
        return 0
    extra_fields = parse_extra_fields(args.fields)
    print_json(format_orders_list(data, extra_fields=extra_fields))
    return 0
