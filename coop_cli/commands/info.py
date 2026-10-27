"""`coop info <id> [<id> ...]` — show detailed product information as structured JSON."""

from __future__ import annotations

import argparse
import sys

from coop_cli.api.orders import load_orders_cache
from coop_cli.api.products import get_items_by_id
from coop_cli.config import DEFAULT_STORE_ID
from coop_cli.formatting import (
    add_output_flags,
    format_product_summary,
    parse_extra_fields,
    print_json,
)


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "info",
        aliases=["item", "get", "show"],
        help="Get detailed information about one or more items by ID/EAN.",
    )
    p.add_argument("ids", nargs="+", help="Product ID(s) / EAN code(s)")
    p.add_argument(
        "--store",
        default=DEFAULT_STORE_ID,
        help=f"Store ID for assortment/pricing (default: {DEFAULT_STORE_ID})",
    )
    add_output_flags(
        p,
        fields_help=(
            "Comma-separated extra fields to include "
            "(e.g. storage,deposit,vat,image,sustainability,all)"
        ),
    )
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    items = get_items_by_id(args.ids, store_id=args.store)
    if args.raw:
        print_json(items)
        return 0

    if not items:
        print(f"No item found for ID(s): {', '.join(args.ids)}", file=sys.stderr)
        return 1

    orders_cache = load_orders_cache()
    cached_items = (orders_cache or {}).get("items") or {}
    extra_fields = parse_extra_fields(args.fields)

    formatted = [
        format_product_summary(
            item,
            bought_stat=cached_items.get(str(item.get("id", ""))),
            include_bought=orders_cache is not None,
            extra_fields=extra_fields,
            detailed=True,
        )
        for item in items
    ]
    print_json(formatted[0] if len(formatted) == 1 else formatted)
    return 0
