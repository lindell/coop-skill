"""`coop order [<order_id> ...]` — show what is in one or more orders (defaults to latest order)."""

from __future__ import annotations

import argparse
import sys

from coop_cli.api.orders import get_order, list_orders
from coop_cli.formatting import (
    add_output_flags,
    format_order_details,
    parse_extra_fields,
    print_json,
)


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "order",
        help="Show items and details for an order by ID (defaults to most recent order).",
    )
    p.add_argument(
        "order_ids",
        nargs="*",
        help="Order ID(s) / code(s) to inspect (omit to inspect the latest order)",
    )
    add_output_flags(
        p,
        fields_help="Comma-separated extra fields to include (e.g. unit,promo,url,image,address,payment)",
    )
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    order_ids: list[str] = list(args.order_ids)
    if not order_ids:
        history = list_orders(
            limit=1,
            page=0,
            cookie_file=args.cookie_file,
            env_file=args.env_file,
        )
        orders = [
            o
            for o in (history.get("orders") or [])
            if o and o.get("status") != "MIGRATED" and o.get("code")
        ]
        if not orders:
            print("No orders found.", file=sys.stderr)
            return 1
        order_ids = [str(orders[0]["code"])]

    results = [
        get_order(
            oid,
            cookie_file=args.cookie_file,
            env_file=args.env_file,
        )
        for oid in order_ids
    ]

    if args.raw:
        print_json(results[0] if len(results) == 1 else results)
        return 0

    extra_fields = parse_extra_fields(args.fields)
    formatted = [format_order_details(o, extra_fields=extra_fields) for o in results]
    print_json(formatted[0] if len(formatted) == 1 else formatted)
    return 0
