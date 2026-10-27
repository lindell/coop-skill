"""`coop cart` — show the current cart as structured JSON."""

from __future__ import annotations

import argparse

from coop_cli.api.cart import get_cart
from coop_cli.formatting import (
    add_output_flags,
    format_cart_summary,
    parse_extra_fields,
    print_json,
)


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("cart", help="Show the current items in the cart.")
    add_output_flags(
        p,
        fields_help="Comma-separated extra fields to include (e.g. brand,size,unit,replaceable)",
    )
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    cart = get_cart(cookie_file=args.cookie_file, env_file=args.env_file)
    if args.raw:
        print_json(cart)
        return 0
    extra_fields = parse_extra_fields(args.fields)
    print_json(format_cart_summary(cart, extra_fields=extra_fields))
    return 0
