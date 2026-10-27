"""JSON formatting and concise summary projectors shared by CLI commands."""

from __future__ import annotations

import argparse
import json
from typing import Any


def print_json(data: Any) -> None:
    """Pretty-print data as JSON."""
    print(json.dumps(data, indent=2, ensure_ascii=False))


def add_output_flags(
    parser: argparse.ArgumentParser,
    *,
    fields_help: str | None = None,
) -> None:
    """Add `--fields` (if applicable) and `--raw` (alias `--json`) to a subcommand parser."""
    if fields_help:
        parser.add_argument(
            "-f",
            "--fields",
            help=fields_help,
        )
    parser.add_argument(
        "--raw",
        "--json",
        dest="raw",
        action="store_true",
        help="Output the full, unprojected raw API response",
    )


def parse_extra_fields(fields_arg: str | None) -> list[str]:
    """Parse a comma-separated `--fields` argument into a clean list of field names."""
    if not fields_arg:
        return []
    return [f.strip() for f in fields_arg.split(",") if f.strip()]


def _short_date(iso_str: str | None) -> str | None:
    """Format an ISO timestamp as YYYY-MM-DD (or None if missing)."""
    if not iso_str:
        return None
    return str(iso_str)[:10]


def category_path(item: dict[str, Any]) -> list[str]:
    """Walk navCategories -> superCategories to build a root-first category path."""
    categories: list[str] = []
    nav = item.get("navCategories") or []
    curr = nav[0] if nav else None
    while curr:
        if curr.get("name"):
            categories.insert(0, curr["name"])
        supers = curr.get("superCategories") or []
        curr = supers[0] if supers else None
    return categories


def _extract_product_field(item: dict[str, Any], field: str) -> Any:
    """Extract a named extra field (or raw fallback key) from a Coop product dict."""
    if field in ("comparative_price", "comparativePrice"):
        val = (item.get("comparativePriceData") or {}).get("b2cPrice")
        text = item.get("comparativePriceText")
        return f"{val:.2f} {text}".strip() if val is not None else None
    if field in ("category", "categories"):
        return " > ".join(category_path(item)) or None
    if field == "origin":
        if item.get("fromSweden"):
            return "Från Sverige"
        codes = item.get("countryOfOriginCodes") or []
        origins = [c.get("value") for c in codes if c.get("value")]
        return ", ".join(origins) if origins else None
    if field in ("labels", "tags"):
        return [
            t.get("description")
            for t in (item.get("accreditedTags") or [])
            if t.get("description")
        ]
    if field == "ingredients":
        return item.get("listOfIngredients")
    if field == "description":
        return item.get("description")
    if field == "nutrition":
        nutrients = item.get("nutrientLinks") or []
        return {
            f"{n.get('description', '')} ({n.get('unit', '')})".strip(): ", ".join(
                n.get("amount") or []
            )
            for n in nutrients
            if n.get("description")
        }
    if field in ("available_online", "availableOnline"):
        return item.get("availableOnline", True)
    if field == "deposit":
        return (item.get("depositData") or {}).get("b2cPrice")
    if field == "vat":
        return (item.get("vat") or {}).get("value")
    if field in ("image", "image_url", "imageUrl"):
        return item.get("imageUrl")
    if field == "storage":
        return (item.get("consumerInstructions") or {}).get("storageInstructions")
    if field == "sustainability":
        info = item.get("sustainabilityInfo") or []
        if not info:
            return None
        scores = info[0].get("productScore") or []
        return {
            s.get("paramId") or s.get("param"): {
                "score": s.get("score"),
                "category": s.get("sustainabilityCategory"),
            }
            for s in scores
            if s.get("score") is not None
        }
    return item.get(field)


def format_product_summary(
    item: dict[str, Any],
    *,
    bought_stat: dict[str, Any] | None = None,
    include_bought: bool = False,
    extra_fields: list[str] | None = None,
    detailed: bool = False,
) -> dict[str, Any]:
    """Build a concise JSON-serializable dict for a product from search or info."""
    piece = (item.get("piecePriceData") or {}).get("b2cPrice")
    sales = (item.get("salesPriceData") or {}).get("b2cPrice")
    price = piece if piece is not None else sales
    unit = item.get("salesUnit", "st")
    unit_short = "kr/kg" if unit in ("Vikt", "kg") else "kr"

    out: dict[str, Any] = {
        "id": str(item.get("id", "")),
        "name": item.get("name", ""),
        "brand": item.get("manufacturerName") or None,
        "size": item.get("packageSizeInformation") or None,
        "price": price,
        "unit": unit_short,
    }

    promos = item.get("onlinePromotions") or []
    if promos:
        p = promos[0]
        out["promo"] = {
            "description": p.get("message") or p.get("type"),
            "price": (p.get("priceData") or {}).get("b2cPrice"),
            "min_qty": p.get("numberOfProductRequired"),
            "member_only": bool(p.get("medMeraRequired")),
        }

    if include_bought:
        if bought_stat and bought_stat.get("orders_count", 0) > 0:
            out["bought"] = {
                "orders": bought_stat["orders_count"],
                "total_qty": bought_stat.get(
                    "total_quantity", bought_stat["orders_count"]
                ),
                "last_ordered": bought_stat.get("last_ordered"),
            }
        else:
            out["bought"] = None

    default_detail_fields = (
        [
            "comparative_price",
            "category",
            "available_online",
            "origin",
            "labels",
            "description",
            "ingredients",
            "nutrition",
        ]
        if detailed
        else []
    )

    fields_to_add = list(default_detail_fields)
    for f in extra_fields or []:
        if f == "all":
            for k in (
                "comparative_price",
                "category",
                "available_online",
                "origin",
                "labels",
                "description",
                "ingredients",
                "nutrition",
                "storage",
                "deposit",
                "vat",
                "image",
                "sustainability",
            ):
                if k not in fields_to_add:
                    fields_to_add.append(k)
        elif f not in fields_to_add:
            fields_to_add.append(f)

    for f in fields_to_add:
        val = _extract_product_field(item, f)
        if val is not None and val != [] and val != {}:
            out[f] = val
        elif f in (extra_fields or []):
            out[f] = val

    return out


def format_cart_summary(
    cart: dict[str, Any],
    *,
    extra_fields: list[str] | None = None,
) -> dict[str, Any]:
    """Build a concise JSON-serializable summary of the shopping cart."""
    entries = cart.get("entries") or []
    store = cart.get("coopStore") or {}
    items_out: list[dict[str, Any]] = []

    for entry in entries:
        prod = entry.get("product") or {}
        item_dict: dict[str, Any] = {
            "id": prod.get("code", ""),
            "name": prod.get("name", ""),
            "qty": entry.get("quantity", 0),
            "unit_price": (entry.get("pickBasePrice") or {}).get("value", 0.0),
            "total_price": (entry.get("totalPrice") or {}).get("value", 0.0),
        }
        for f in extra_fields or []:
            if f == "brand":
                item_dict["brand"] = prod.get("manufacturer")
            elif f == "size":
                item_dict["size"] = prod.get("packageSizeInformation")
            elif f == "unit":
                item_dict["unit"] = (entry.get("unit") or {}).get("code")
            elif f == "replaceable":
                item_dict["replaceable"] = entry.get("replace")
            elif f in entry:
                item_dict[f] = entry[f]
            elif f in prod:
                item_dict[f] = prod[f]
        items_out.append(item_dict)

    out: dict[str, Any] = {
        "cart_id": cart.get("guid"),
        "store": {
            "id": store.get("code"),
            "name": store.get("name"),
        },
        "total_items": len(entries),
        "total_qty": cart.get("totalQuantity", 0),
        "subtotal": (cart.get("subTotal") or {}).get("value", 0.0),
        "items": items_out,
    }
    for f in extra_fields or []:
        if f in cart and f not in out:
            out[f] = cart[f]
    return out


def format_orders_list(
    data: dict[str, Any],
    *,
    extra_fields: list[str] | None = None,
) -> dict[str, Any]:
    """Build a concise JSON-serializable list of past/active orders."""
    raw_orders = [
        o for o in (data.get("orders") or []) if o and o.get("status") != "MIGRATED"
    ]
    pagination = data.get("pagination") or {}
    orders_out: list[dict[str, Any]] = []

    for o in raw_orders:
        item: dict[str, Any] = {
            "id": o.get("code", ""),
            "placed": _short_date(o.get("placed")),
            "delivery_date": _short_date(o.get("actualDeliveryDate")),
            "status": o.get("statusDisplay") or o.get("status") or "",
            "delivery_mode": (o.get("deliveryMode") or {}).get("code", ""),
            "total": (o.get("total") or {}).get("value", 0.0),
        }
        for f in extra_fields or []:
            if f in ("address", "delivery_address", "deliveryAddress"):
                addr = o.get("deliveryAddress") or {}
                item["address"] = {
                    "street": addr.get("line1"),
                    "postal_code": addr.get("postalCode"),
                    "town": addr.get("town"),
                }
            elif f in ("window", "delivery_window", "deliveryWindow"):
                win = o.get("deliveryWindow") or {}
                item["delivery_window"] = {
                    "start": win.get("startTime"),
                    "end": win.get("endTime"),
                }
            elif f in ("tracking", "tracking_id", "trackingID"):
                item["tracking"] = o.get("trackingID")
            elif f in o:
                item[f] = o[f]
        orders_out.append(item)

    return {
        "total_orders": pagination.get("totalResults", len(orders_out)),
        "page": pagination.get("currentPage", 0),
        "total_pages": pagination.get("totalPages", 1),
        "orders": orders_out,
    }


def format_order_details(
    order: dict[str, Any],
    *,
    extra_fields: list[str] | None = None,
) -> dict[str, Any]:
    """Build a concise JSON-serializable summary of a single order and its entries."""
    mode_obj = order.get("deliveryMode") or {}
    entries = order.get("entries") or []
    entry_by_num = {
        e.get("entryNumber"): e for e in entries if e.get("entryNumber") is not None
    }

    items_out: list[dict[str, Any]] = []
    for entry in entries:
        prod = entry.get("product") or {}
        qty = entry.get("quantity", 0)
        orig_qty = entry.get("originalQuantity", qty)
        unit_p = (entry.get("pickBasePrice") or entry.get("basePrice") or {}).get(
            "value", 0.0
        )
        tot_p = (entry.get("totalPrice") or {}).get("value", 0.0)

        item_dict: dict[str, Any] = {
            "id": prod.get("code", ""),
            "name": prod.get("name", ""),
            "brand": prod.get("manufacturer") or None,
            "size": prod.get("packageSizeInformation") or None,
            "qty": qty,
            "ordered_qty": orig_qty,
            "unit_price": unit_p,
            "total_price": tot_p,
        }

        disc_val = (entry.get("discount") or {}).get("value")
        if disc_val:
            item_dict["discount"] = disc_val
        if qty == 0 and orig_qty:
            item_dict["delivered"] = False
        replaces_num = entry.get("replacesEntryNumber")
        if replaces_num is not None:
            orig_entry = entry_by_num.get(replaces_num)
            orig_prod = (orig_entry or {}).get("product") or {}
            item_dict["replaces"] = {
                "id": orig_prod.get("code"),
                "name": orig_prod.get("name"),
            }

        for f in extra_fields or []:
            if f == "unit":
                item_dict["unit"] = (entry.get("unit") or {}).get("code")
            elif f == "promo":
                promos = entry.get("appliedPromotions") or []
                item_dict["promo"] = (
                    (promos[0].get("promotion") or {}).get("description")
                    if promos
                    else None
                )
            elif f in ("url", "image"):
                item_dict[f] = (
                    prod.get("url")
                    if f == "url"
                    else ((prod.get("images") or [{}])[0].get("url"))
                )
            elif f in entry:
                item_dict[f] = entry[f]
            elif f in prod:
                item_dict[f] = prod[f]

        items_out.append(item_dict)

    out: dict[str, Any] = {
        "id": order.get("code", ""),
        "placed": _short_date(order.get("created") or order.get("placed")),
        "delivery_date": _short_date(order.get("actualDeliveryDate")),
        "status": order.get("statusDisplay") or order.get("status") or "unknown",
        "delivery_mode": mode_obj.get("name") or mode_obj.get("code") or "Unknown",
        "store": order.get("store") or None,
        "total_items": len(entries),
        "total_qty": order.get("totalQuantity", 0),
        "subtotal": (order.get("subTotal") or {}).get("value", 0.0),
        "delivery_cost": (order.get("deliveryCost") or {}).get("value", 0.0),
        "discounts": (order.get("totalDiscounts") or {}).get("value", 0.0),
        "deposit": (order.get("totalDepositSum") or {}).get("value", 0.0),
        "total": (order.get("totalPriceWithTax") or order.get("totalPrice") or {}).get(
            "value", 0.0
        ),
        "items": items_out,
    }
    for f in extra_fields or []:
        if f in ("address", "delivery_address", "deliveryAddress"):
            out["delivery_address"] = order.get("deliveryAddress")
        elif f in ("payment", "paymentMode"):
            out["payment"] = order.get("paymentDisplayName") or order.get("paymentMode")
        elif f in order and f not in out:
            out[f] = order[f]
    return out
