"""`coop init [-n <orders>]` — ensure login and cache recent orders for search insights."""

from __future__ import annotations

import argparse

from coop_cli.api.orders import DEFAULT_ORDERS_LIMIT, cache_recent_orders
from coop_cli.auth import get_spa_session
from coop_cli.formatting import add_output_flags, print_json


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "init",
        help="Ensure login and cache the last N orders so search shows purchase frequency.",
    )
    p.add_argument(
        "-n",
        "--orders",
        type=int,
        default=DEFAULT_ORDERS_LIMIT,
        help=f"Number of recent orders to fetch and cache (default: {DEFAULT_ORDERS_LIMIT})",
    )
    add_output_flags(p)
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    session = get_spa_session(
        cookie_file=args.cookie_file,
        env_file=args.env_file,
    )
    data = cache_recent_orders(
        limit=args.orders,
        cookie_file=args.cookie_file,
        env_file=args.env_file,
    )
    if args.raw:
        print_json(data)
        return 0

    print_json(
        {
            "status": "ok",
            "user_id": session.get("shoppingUserId"),
            "orders_cached": data.get("order_count", 0),
            "unique_products": len(data.get("items") or {}),
            "orders": data.get("orders", []),
        }
    )
    return 0
