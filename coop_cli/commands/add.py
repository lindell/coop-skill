"""`coop add <item> [<item> ...] [--set]` — add one or more items to the cart or set their quantities."""

from __future__ import annotations

import argparse

from coop_cli.api.cart import add_cart_items_delta
from coop_cli.formatting import (
    add_output_flags,
    format_cart_summary,
    parse_extra_fields,
    print_json,
)

# Product IDs / EANs are at least 5 characters; shorter integer tokens are treated as quantities
_MIN_PRODUCT_ID_LEN = 5


def _parse_item_tokens(tokens: list[str]) -> list[tuple[str, int]]:
    """Parse CLI tokens into `(product_id, quantity)` pairs.

    Supports:
    - `<id> [qty]` (e.g. `7310865004703 2`)
    - `<id>:<qty>` or `<id>=<qty>` (e.g. `7310865004703:2 7350016868924:1`)
    - Multiple IDs with optional quantities (e.g. `7310865004703 2 7350016868924 7310865004710 3`)
    """
    items: list[tuple[str, int]] = []
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i].strip()
        if not tok:
            i += 1
            continue

        for sep in (":", "="):
            if sep in tok:
                pid, qty_str = tok.split(sep, 1)
                if not pid:
                    raise ValueError(f"Invalid item specification: {tok!r}")
                try:
                    qty = int(qty_str)
                except ValueError as exc:
                    raise ValueError(
                        f"Invalid quantity in {tok!r}: expected an integer"
                    ) from exc
                items.append((pid, qty))
                i += 1
                break
        else:
            # Check if the next token is a standalone integer quantity (rather than another product ID)
            if i + 1 < n:
                next_tok = tokens[i + 1].strip()
                if (
                    next_tok
                    and ":" not in next_tok
                    and "=" not in next_tok
                    and len(next_tok) < _MIN_PRODUCT_ID_LEN
                ):
                    try:
                        qty = int(next_tok)
                        items.append((tok, qty))
                        i += 2
                        continue
                    except ValueError:
                        pass

            items.append((tok, 1))
            i += 1

    if not items:
        raise ValueError("At least one product ID is required.")
    return items


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "add",
        help="Add one or more items to the cart (or update their quantities).",
    )
    p.add_argument(
        "items",
        nargs="+",
        metavar="item",
        help=(
            "Product(s) to add: `<id> [qty]` or `<id>:<qty>` "
            "(repeat to add multiple items in one call; default qty is 1)"
        ),
    )
    p.add_argument(
        "--set",
        action="store_true",
        help="Set exact cart quantities instead of incrementing existing quantities (use 0 to remove)",
    )
    add_output_flags(
        p,
        fields_help="Comma-separated extra fields to include on cart items (e.g. brand,size,unit,replaceable)",
    )
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    parsed_items = _parse_item_tokens(args.items)
    cart = add_cart_items_delta(
        parsed_items,
        set_exact=args.set,
        cookie_file=args.cookie_file,
        env_file=args.env_file,
    )
    if args.raw:
        print_json(cart)
        return 0

    extra_fields = parse_extra_fields(args.fields)
    summary = format_cart_summary(cart, extra_fields=extra_fields)
    mode = "set" if args.set else "add"
    if len(parsed_items) == 1:
        pid, qty = parsed_items[0]
        summary["action"] = {
            "mode": mode,
            "product_id": str(pid),
            "quantity": qty,
        }
    else:
        summary["action"] = {
            "mode": mode,
            "items": [
                {"product_id": str(pid), "quantity": qty} for pid, qty in parsed_items
            ],
        }
    print_json(summary)
    return 0
