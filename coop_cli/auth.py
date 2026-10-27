"""Authentication: OIDC login, cookie persistence, and SPA Bearer token session."""

from __future__ import annotations

import http.cookiejar
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from coop_cli.config import (
    DEFAULT_COOKIE_FILE,
    DEFAULT_ENV_FILE,
    DEFAULT_SESSION_CACHE,
    get_credentials,
)
from coop_cli.http_client import build_opener, read_json


def parse_hidden_form(html: str) -> tuple[str, dict[str, str]]:
    """Extract the form action URL and hidden input fields from an HTML form."""
    action_match = re.search(r"action=[\"']([^\"']+)[\"']", html)
    if not action_match:
        raise RuntimeError("Could not find form action in HTML response.")
    inputs = dict(
        re.findall(
            r"<input[^>]+name=[\"']([^\"']+)[\"'][^>]+value=[\"']([^\"']*)[\"']",
            html,
        )
    )
    return action_match.group(1), inputs


def login_coop(
    username: str,
    password: str,
    cookie_file: Path | None = DEFAULT_COOKIE_FILE,
    session_cache_file: Path | None = DEFAULT_SESSION_CACHE,
) -> http.cookiejar.MozillaCookieJar:
    """Perform the 5-step OIDC login against coop.se and return the cookie jar."""
    jar = http.cookiejar.MozillaCookieJar(
        str(cookie_file) if cookie_file else None
    )
    opener = build_opener(jar, follow_redirects=False)

    # Request 1: Fetch OIDC parameters and correlation/nonce cookies from www.coop.se
    with opener.open("https://www.coop.se/logga-in/") as resp1:
        html1 = resp1.read().decode("utf-8")
    authorize_url, oidc_params = parse_hidden_form(html1)

    # Request 2: Fetch antiforgery cookies (XSRF-TOKEN) from login.coop.se
    with opener.open("https://login.coop.se/local/xsrf") as _:
        pass
    xsrf_token = next(
        (
            c.value
            for c in jar
            if c.name == "XSRF-TOKEN" and "login.coop.se" in c.domain
        ),
        None,
    )
    if not xsrf_token:
        raise RuntimeError("Failed to obtain XSRF-TOKEN from login.coop.se.")

    # Request 3: Authenticate with email & password on login.coop.se
    login_payload = json.dumps(
        {
            "email": username,
            "password": password,
            "accountType": "Private",
            "rememberMe": True,
            "clientId": oidc_params.get("client_id", "coopse_prod"),
        }
    ).encode("utf-8")
    auth_req = urllib.request.Request(
        "https://login.coop.se/local/signin/application-schema/email-password",
        data=login_payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "RequestVerificationToken": xsrf_token,
        },
        method="POST",
    )
    try:
        with opener.open(auth_req) as _:
            pass
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Authentication failed (HTTP {exc.code}): {err_body}"
        ) from exc

    # Request 4: Submit OIDC authorize request to get code & id_token
    authorize_data = urllib.parse.urlencode(oidc_params).encode("utf-8")
    with opener.open(authorize_url, data=authorize_data) as resp4:
        html4 = resp4.read().decode("utf-8")
    signin_oidc_url, callback_params = parse_hidden_form(html4)

    # Request 5: Exchange OIDC code/id_token on www.coop.se/signin-oidc for .AspNetCore.Cookies
    callback_data = urllib.parse.urlencode(callback_params).encode("utf-8")
    try:
        with opener.open(signin_oidc_url, data=callback_data) as _:
            pass
    except urllib.error.HTTPError as exc:
        if exc.code not in (301, 302, 303, 307, 308):
            raise

    has_coop_cookie = any(
        c.name == ".AspNetCore.Cookies" and "coop.se" in c.domain for c in jar
    )
    if not has_coop_cookie:
        raise RuntimeError(
            "Login completed but .AspNetCore.Cookies was not set on www.coop.se."
        )

    if cookie_file:
        cookie_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        jar.save(ignore_discard=True, ignore_expires=True)
        os.chmod(cookie_file, 0o600)

    if session_cache_file:
        session_cache_file.unlink(missing_ok=True)

    return jar


def clear_auth_state(
    cookie_file: Path | None = DEFAULT_COOKIE_FILE,
    cache_file: Path | None = DEFAULT_SESSION_CACHE,
) -> None:
    """Remove cached session token and cookies so the next call performs a clean login."""
    for path in (cache_file, cookie_file):
        if path is not None:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass


def load_cookie_jar(
    cookie_file: Path,
    env_file: Path,
    *,
    auto_login: bool = True,
) -> http.cookiejar.MozillaCookieJar:
    """Load saved cookies or automatically log in if missing or corrupted."""
    if cookie_file.is_file():
        jar = http.cookiejar.MozillaCookieJar(str(cookie_file))
        try:
            jar.load(ignore_discard=True, ignore_expires=True)
            if any(c.name == ".AspNetCore.Cookies" for c in jar):
                return jar
        except (http.cookiejar.LoadError, OSError):
            pass
        clear_auth_state(cookie_file=cookie_file, cache_file=None)

    if not auto_login:
        raise RuntimeError(
            f"No valid session cookies found in {cookie_file}. Run `coop login` first."
        )

    username, password = get_credentials(env_file)
    if not username or not password:
        raise RuntimeError(
            "Not logged in and COOP_USERNAME/COOP_PASSWORD are not set. Run `coop login`."
        )
    return login_coop(username, password, cookie_file=cookie_file)


def _fetch_spa_token(opener: urllib.request.OpenerDirector) -> dict[str, Any]:
    """Request a SPA Bearer token + shoppingUserId using the session cookies."""
    url = f"https://www.coop.se/api/spa/token?_={int(time.time() * 1000)}"
    return read_json(opener, url)


def _relogin_opener(
    cookie_file: Path,
    env_file: Path,
    cache_file: Path | None = DEFAULT_SESSION_CACHE,
) -> urllib.request.OpenerDirector | None:
    """Clear stale auth state, log in again with stored credentials, and return a fresh opener."""
    clear_auth_state(cookie_file=cookie_file, cache_file=cache_file)
    username, password = get_credentials(env_file)
    if not username or not password:
        return None
    jar = login_coop(
        username,
        password,
        cookie_file=cookie_file,
        session_cache_file=cache_file,
    )
    return build_opener(jar)


def get_spa_session(
    cookie_file: Path = DEFAULT_COOKIE_FILE,
    env_file: Path = DEFAULT_ENV_FILE,
    cache_file: Path = DEFAULT_SESSION_CACHE,
    *,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Return cached or freshly fetched SPA Bearer token and shoppingUserId.

    Automatically recovers from expired or corrupted cookies/tokens by clearing
    cached state and logging in again.
    """
    if force_refresh:
        clear_auth_state(cookie_file=cookie_file, cache_file=cache_file)
    elif cache_file.is_file():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            if (
                isinstance(cached, dict)
                and cached.get("token")
                and cached.get("shoppingUserId")
                and cached.get("expires_epoch", 0) > time.time() + 60
            ):
                return cached
        except (json.JSONDecodeError, OSError):
            pass
        clear_auth_state(cookie_file=None, cache_file=cache_file)

    jar = load_cookie_jar(cookie_file, env_file, auto_login=True)
    opener = build_opener(jar)

    data: dict[str, Any] = {}
    try:
        fetched = _fetch_spa_token(opener)
        if isinstance(fetched, dict):
            data = fetched
    except (urllib.error.URLError, json.JSONDecodeError, ValueError, RuntimeError):
        data = {}

    if not data.get("token") or not data.get("shoppingUserId"):
        # Cookies may have expired or become invalid; clear auth state and re-login once
        fresh_opener = _relogin_opener(cookie_file, env_file, cache_file)
        if fresh_opener is not None:
            fetched = _fetch_spa_token(fresh_opener)
            if isinstance(fetched, dict):
                data = fetched

    if not data.get("token") or not data.get("shoppingUserId"):
        raise RuntimeError("Failed to obtain SPA Bearer token from /api/spa/token.")

    # Cache for 15 minutes (or until token expiry)
    data["expires_epoch"] = time.time() + 900
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        cache_file.write_text(json.dumps(data), encoding="utf-8")
        os.chmod(cache_file, 0o600)
    except OSError:
        pass
    return data


def format_cookie_header(
    jar: http.cookiejar.CookieJar, domain: str = "www.coop.se"
) -> str:
    """Format cookies for a given domain as a single HTTP Cookie header string."""
    pairs = [
        f"{c.name}={c.value}"
        for c in jar
        if domain in c.domain and c.path == "/"
    ]
    return "; ".join(pairs)

