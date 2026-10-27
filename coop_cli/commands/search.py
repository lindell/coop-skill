"""`coop search <query>` — search for products and output structured JSON."""

from __future__ import annotations

import argparse
from typing import Any

from coop_cli.api.orders import load_orders_cache
from coop_cli.api.products import search_products
from coop_cli.config import DEFAULT_STORE_ID
from coop_cli.formatting import (
    add_output_flags,
    format_product_summary,
    parse_extra_fields,
    print_json,
)


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("search", help="Search for products on coop.se.")
    p.add_argument("query", nargs="+", help="Search query term(s)")
    p.add_argument(
        "-n", "--limit", type=int, default=10, help="Max results to return (default: 10)"
    )
    p.add_argument(
        "--skip", type=int, default=0, help="Offset to skip for pagination (default: 0)"
    )
    p.add_argument(
        "--store",
        default=DEFAULT_STORE_ID,
        help=f"Store ID for assortment/pricing (default: {DEFAULT_STORE_ID})",
    )
    add_output_flags(
        p,
        fields_help=(
            "Comma-separated extra fields to include on each item "
            "(e.g. comparative_price,category,origin,labels,ingredients,nutrition,storage,deposit,vat,image,sustainability,all)"
        ),
    )
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    query = " ".join(args.query).strip()
    data = search_products(
        query,
        limit=args.limit,
        skip=args.skip,
        store_id=args.store,
    )
    orders_cache = load_orders_cache()
    cached_items = (orders_cache or {}).get("items") or {}
    cached_order_count = (orders_cache or {}).get("order_count", 0)

    if args.raw:
        print_json(data)
        return 0

    results = data.get("results", {})
    raw_items = results.get("items", [])
    extra_fields = parse_extra_fields(args.fields)

    items_out = [
        format_product_summary(
            item,
            bought_stat=cached_items.get(str(item.get("id", ""))),
            include_bought=orders_cache is not None,
            extra_fields=extra_fields,
        )
        for item in raw_items
    ]

    output: dict[str, Any] = {
        "query": query,
        "total_results": results.get("count", 0),
        "showing": len(items_out),
    }
    if orders_cache is not None:
        output["cached_orders_checked"] = cached_order_count
    output["items"] = items_out

    print_json(output)
    return 0
