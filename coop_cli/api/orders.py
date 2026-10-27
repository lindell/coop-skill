"""Order history and order details against the Hybris ecommerce API (requires login)."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
from pathlib import Path
from typing import Any

from coop_cli.api.cart import _ECOMMERCE_URL, authed_request_json
from coop_cli.config import (
    DEFAULT_COOKIE_FILE,
    DEFAULT_ENV_FILE,
    DEFAULT_ORDERS_CACHE,
)


def list_orders(
    *,
    limit: int = 20,
    page: int = 0,
    cookie_file: Path = DEFAULT_COOKIE_FILE,
    env_file: Path = DEFAULT_ENV_FILE,
) -> dict[str, Any]:
    """Fetch a paginated list of past and active orders for the current user."""
    params = urllib.parse.urlencode(
        {
            "fields": "FULL",
            "currentPage": str(page),
            "pageSize": str(limit),
            "api-version": "v1",
        }
    )
    return authed_request_json(
        lambda user_id: f"{_ECOMMERCE_URL}/{user_id}/orders?{params}",
        cookie_file=cookie_file,
        env_file=env_file,
    )


def get_order(
    order_code: str,
    *,
    cookie_file: Path = DEFAULT_COOKIE_FILE,
    env_file: Path = DEFAULT_ENV_FILE,
) -> dict[str, Any]:
    """Fetch full details (including items/entries) for a single order by code."""
    quoted_code = urllib.parse.quote(str(order_code))
    params = urllib.parse.urlencode({"fields": "FULL", "api-version": "v1"})
    try:
        return authed_request_json(
            lambda user_id: f"{_ECOMMERCE_URL}/{user_id}/orders/{quoted_code}?{params}",
            cookie_file=cookie_file,
            env_file=env_file,
        )
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Failed to fetch order {order_code} (HTTP {exc.code}): {err_body}"
        ) from exc


ORDERS_CACHE_TTL_SECONDS = 86400
DEFAULT_ORDERS_LIMIT = 50


def cache_recent_orders(
    limit: int = DEFAULT_ORDERS_LIMIT,
    *,
    cookie_file: Path = DEFAULT_COOKIE_FILE,
    env_file: Path = DEFAULT_ENV_FILE,
    cache_file: Path = DEFAULT_ORDERS_CACHE,
) -> dict[str, Any]:
    """Fetch recent orders up to the last cached one and save a summary cache.

    No-op if the cache was already updated less than 1 day ago and has at least
    `limit` orders (or all available orders).
    """
    now = int(time.time())
    existing = load_orders_cache(cache_file)
    existing_orders: list[dict[str, Any]] = []
    existing_items: dict[str, dict[str, Any]] = {}

    if isinstance(existing, dict):
        raw_existing_orders = existing.get("orders")
        if isinstance(raw_existing_orders, list):
            existing_orders = [
                o
                for o in raw_existing_orders
                if isinstance(o, dict) and o.get("code")
            ]
        raw_existing_items = existing.get("items")
        if isinstance(raw_existing_items, dict):
            existing_items = {
                str(k): dict(v)
                for k, v in raw_existing_items.items()
                if isinstance(v, dict)
            }
        updated_at = existing.get("updated_at")
        has_enough = len(existing_orders) >= limit or bool(existing.get("complete"))
        if (
            has_enough
            and isinstance(updated_at, (int, float))
            and (now - updated_at) < ORDERS_CACHE_TTL_SECONDS
            and isinstance(raw_existing_orders, list)
            and isinstance(raw_existing_items, dict)
        ):
            return existing

    existing_by_code = {str(o["code"]): o for o in existing_orders}
    newer_codes: list[str] = []
    older_codes: list[str] = []
    seen_codes: set[str] = set()
    page = 0
    page_size = max(20, limit)
    reached_cached = False
    exhausted_pages = False

    while (
        len(newer_codes) + len(existing_orders) + len(older_codes) < limit
        or not reached_cached
    ):
        history = list_orders(
            limit=page_size,
            page=page,
            cookie_file=cookie_file,
            env_file=env_file,
        )
        raw_orders = history.get("orders") or []
        if not raw_orders:
            exhausted_pages = True
            break
        stop_paging = False
        for o in raw_orders:
            if not o or o.get("status") == "MIGRATED" or not o.get("code"):
                continue
            code = str(o["code"])
            if code in seen_codes:
                continue
            seen_codes.add(code)

            if code in existing_by_code:
                reached_cached = True
                if len(newer_codes) + len(existing_orders) + len(older_codes) >= limit:
                    stop_paging = True
                    break
                continue

            if not reached_cached:
                newer_codes.append(code)
                if len(newer_codes) >= limit:
                    stop_paging = True
                    break
            else:
                older_codes.append(code)
                if len(newer_codes) + len(existing_orders) + len(older_codes) >= limit:
                    stop_paging = True
                    break

        if stop_paging:
            break
        pagination = history.get("pagination") or {}
        if page + 1 >= pagination.get("totalPages", 1):
            exhausted_pages = True
            break
        page += 1

    items_stats: dict[str, dict[str, Any]] = existing_items

    def _fetch_and_merge(code: str) -> dict[str, Any]:
        detail = get_order(code, cookie_file=cookie_file, env_file=env_file)
        placed = str(detail.get("created") or detail.get("placed") or "")[:10]
        delivery = str(detail.get("actualDeliveryDate") or "")[:10]
        order_date = placed or delivery
        summary = {
            "code": code,
            "placed": placed,
            "delivery": delivery,
            "status": detail.get("statusDisplay") or detail.get("status") or "",
            "total": (
                detail.get("totalPriceWithTax") or detail.get("totalPrice") or {}
            ).get("value", 0.0),
        }

        seen_in_order: set[str] = set()
        for entry in detail.get("entries") or []:
            prod = entry.get("product") or {}
            p_code = str(prod.get("code") or "")
            if not p_code:
                continue
            qty = int(entry.get("quantity") or 0)
            orig_qty = int(entry.get("originalQuantity") or 0)
            # Count if either delivered or originally ordered
            effective_qty = qty if qty > 0 else orig_qty
            if effective_qty <= 0:
                continue

            stat = items_stats.setdefault(
                p_code,
                {
                    "name": prod.get("name", ""),
                    "brand": prod.get("manufacturer", ""),
                    "orders_count": 0,
                    "total_quantity": 0,
                    "last_ordered": order_date,
                },
            )
            if p_code not in seen_in_order:
                stat["orders_count"] = int(stat.get("orders_count") or 0) + 1
                seen_in_order.add(p_code)
            stat["total_quantity"] = int(stat.get("total_quantity") or 0) + effective_qty
            if order_date and order_date > str(stat.get("last_ordered") or ""):
                stat["last_ordered"] = order_date
            if not stat.get("name") and prod.get("name"):
                stat["name"] = prod["name"]
            if not stat.get("brand") and prod.get("manufacturer"):
                stat["brand"] = prod["manufacturer"]

        return summary

    newer_summaries = [_fetch_and_merge(code) for code in newer_codes]
    older_summaries = [_fetch_and_merge(code) for code in older_codes]
    orders_summary = newer_summaries + existing_orders + older_summaries

    cache_data: dict[str, Any] = {
        "updated_at": int(time.time()),
        "order_count": len(orders_summary),
        "complete": exhausted_pages and len(orders_summary) < limit,
        "orders": orders_summary,
        "items": items_stats,
    }
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(
        json.dumps(cache_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    try:
        os.chmod(cache_file, 0o600)
    except OSError:
        pass
    return cache_data


def load_orders_cache(
    cache_file: Path = DEFAULT_ORDERS_CACHE,
) -> dict[str, Any] | None:
    """Load the saved recent-orders cache from disk, or return None if not present."""
    if not cache_file.is_file():
        return None
    try:
        return json.loads(cache_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


