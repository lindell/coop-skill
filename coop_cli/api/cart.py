"""Cart operations against the Hybris ecommerce API (requires login)."""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from coop_cli.auth import get_spa_session
from coop_cli.config import (
    APIM_SUBSCRIPTION_KEY,
    DEFAULT_COOKIE_FILE,
    DEFAULT_ENV_FILE,
)
from coop_cli.http_client import build_opener, read_json

_ECOMMERCE_URL = "https://external.api.coop.se/ecommerce/coop/users"


def _session_auth(
    cookie_file: Path,
    env_file: Path,
    *,
    force_refresh: bool = False,
) -> tuple[str, dict[str, str]]:
    """Return (url-quoted shoppingUserId, auth headers) for the current session."""
    session = get_spa_session(
        cookie_file=cookie_file,
        env_file=env_file,
        force_refresh=force_refresh,
    )
    user_id = urllib.parse.quote(session["shoppingUserId"])
    headers = {
        "Authorization": f"Bearer {session['token']}",
        "Ocp-Apim-Subscription-Key": APIM_SUBSCRIPTION_KEY,
        "Accept": "application/json",
    }
    return user_id, headers


def authed_request_json(
    url_builder: Callable[[str], str],
    *,
    method: str = "GET",
    data: bytes | None = None,
    cookie_file: Path = DEFAULT_COOKIE_FILE,
    env_file: Path = DEFAULT_ENV_FILE,
) -> dict[str, Any]:
    """Perform an authenticated Hybris request; auto-recover and retry once on 401/403."""
    for attempt in range(2):
        user_id, headers = _session_auth(
            cookie_file,
            env_file,
            force_refresh=(attempt > 0),
        )
        req = urllib.request.Request(
            url_builder(user_id),
            data=data,
            headers=headers,
            method=method,
        )
        try:
            return read_json(build_opener(), req)
        except urllib.error.HTTPError as exc:
            if attempt == 0 and exc.code in (401, 403):
                continue
            raise
    raise RuntimeError("Authenticated request failed after session refresh.")


def get_cart(
    cookie_file: Path = DEFAULT_COOKIE_FILE,
    env_file: Path = DEFAULT_ENV_FILE,
) -> dict[str, Any]:
    """Fetch the current user's active cart from Hybris API."""
    return authed_request_json(
        lambda user_id: f"{_ECOMMERCE_URL}/{user_id}/carts/current?fields=FULL&api-version=v1",
        cookie_file=cookie_file,
        env_file=env_file,
    )


def update_cart_item(
    product_code: str,
    quantity: int = 1,
    *,
    replaceable: bool = True,
    variant_code: str | None = None,
    cookie_file: Path = DEFAULT_COOKIE_FILE,
    env_file: Path = DEFAULT_ENV_FILE,
) -> dict[str, Any]:
    """Set the quantity of a product in the current user's cart (or add if not in cart)."""
    query: dict[str, str] = {
        "qty": str(quantity),
        "code": str(product_code),
        "replaceable": "true" if replaceable else "false",
        "fields": "FULL",
        "api-version": "v1",
    }
    if variant_code:
        query["varianceCode"] = variant_code

    params = urllib.parse.urlencode(query)
    try:
        return authed_request_json(
            lambda user_id: f"{_ECOMMERCE_URL}/{user_id}/cartdata/current/products?{params}",
            method="POST",
            data=b"",
            cookie_file=cookie_file,
            env_file=env_file,
        )
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Failed to update cart item {product_code} (HTTP {exc.code}): {err_body}"
        ) from exc


def add_cart_items_delta(
    items: list[tuple[str, int]],
    *,
    set_exact: bool = False,
    replaceable: bool = True,
    cookie_file: Path = DEFAULT_COOKIE_FILE,
    env_file: Path = DEFAULT_ENV_FILE,
) -> dict[str, Any]:
    """Add or set multiple `(product_code, qty)` items in the cart and return the final cart."""
    if not items:
        return get_cart(cookie_file=cookie_file, env_file=env_file)

    existing_by_code: dict[str, int] = {}
    if not set_exact:
        cart = get_cart(cookie_file=cookie_file, env_file=env_file)
        for entry in cart.get("entries", []):
            code = entry.get("product", {}).get("code")
            if code is not None:
                existing_by_code[str(code)] = int(entry.get("quantity", 0))

    # Track running quantities so duplicate product_codes in the same call accumulate properly
    target_by_code: dict[str, int] = {}
    for product_code, qty in items:
        code = str(product_code)
        if set_exact:
            target_by_code[code] = max(0, qty)
        else:
            base = target_by_code.get(code, existing_by_code.get(code, 0))
            target_by_code[code] = max(0, base + qty)

    last_cart: dict[str, Any] = {}
    for code, new_qty in target_by_code.items():
        last_cart = update_cart_item(
            code,
            new_qty,
            replaceable=replaceable,
            cookie_file=cookie_file,
            env_file=env_file,
        )
    return last_cart


def add_cart_item_delta(
    product_code: str,
    add_qty: int = 1,
    *,
    set_exact: bool = False,
    replaceable: bool = True,
    cookie_file: Path = DEFAULT_COOKIE_FILE,
    env_file: Path = DEFAULT_ENV_FILE,
) -> dict[str, Any]:
    """Add `add_qty` of `product_code` to cart (or set exact quantity when `set_exact=True`)."""
    return add_cart_items_delta(
        [(str(product_code), add_qty)],
        set_exact=set_exact,
        replaceable=replaceable,
        cookie_file=cookie_file,
        env_file=env_file,
    )

