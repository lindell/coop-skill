"""Product search and lookup (public endpoints, no login required)."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

from coop_cli.config import (
    APIM_SUBSCRIPTION_KEY,
    DEFAULT_CUSTOMER_GROUPS,
    DEFAULT_STORE_ID,
)
from coop_cli.http_client import build_opener, read_json

_PERSONALIZATION_URL = "https://external.api.coop.se/personalization/search"


def _common_params(store_id: str) -> str:
    """Query string shared by all personalization search endpoints."""
    return urllib.parse.urlencode(
        {
            "api-version": "v2",
            "store": store_id,
            "groups": DEFAULT_CUSTOMER_GROUPS,
            "device": "desktop",
            "direct": "false",
        }
    )


def _post_json(url: str, payload: Any) -> Any:
    """POST a JSON payload to a personalization endpoint and return decoded JSON."""
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Ocp-Apim-Subscription-Key": APIM_SUBSCRIPTION_KEY,
        },
        method="POST",
    )
    return read_json(build_opener(), req)


def search_products(
    query: str,
    *,
    limit: int = 10,
    skip: int = 0,
    store_id: str = DEFAULT_STORE_ID,
) -> dict[str, Any]:
    """Search products on coop.se in a single HTTP POST request."""
    return _post_json(
        f"{_PERSONALIZATION_URL}/products?{_common_params(store_id)}",
        {
            "query": query,
            "resultsOptions": {"skip": skip, "take": limit},
            "relatedResultsOptions": {"skip": 0, "take": 0},
            "customData": {"consent": False},
        },
    )


def get_items_by_id(
    item_ids: list[str],
    *,
    store_id: str = DEFAULT_STORE_ID,
) -> list[dict[str, Any]]:
    """Fetch full product details for one or more item IDs (EAN/code) in 1 request."""
    data = _post_json(
        f"{_PERSONALIZATION_URL}/entities/by-id?{_common_params(store_id)}",
        item_ids,
    )
    return data.get("results", {}).get("items", [])

