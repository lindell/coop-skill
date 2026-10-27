"""Low-level HTTP helpers built on urllib (SSL context, cookies, User-Agent)."""

from __future__ import annotations

import http.cookiejar
import json
import os
import ssl
import urllib.request
from pathlib import Path
from typing import Any

from coop_cli.config import USER_AGENT


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Prevent automatic redirect following to keep request count minimal."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _find_ca_bundle() -> str | None:
    """Discover a valid CA certificate bundle path across environments and OS distributions."""
    # 1. Standard environment variables
    for env_var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
        val = os.environ.get(env_var)
        if val and Path(val).is_file():
            return val

    # 2. Optional certifi package if available in the Python environment
    try:
        import certifi

        where = certifi.where()
        if Path(where).is_file():
            return where
    except ImportError:
        pass

    # 3. Standard Linux / Unix distribution locations
    system_candidates = [
        "/etc/ssl/certs/ca-certificates.crt",                  # Debian, Ubuntu, Arch, Alpine
        "/etc/pki/tls/certs/ca-bundle.crt",                    # Fedora, RHEL
        "/etc/ssl/ca-bundle.pem",                              # openSUSE, SUSE
        "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",   # CentOS, RHEL 7+
        "/etc/ssl/cert.pem",                                   # Alpine, macOS, OpenBSD
    ]
    for path_str in system_candidates:
        if Path(path_str).is_file():
            return path_str

    return None


def _create_ssl_context() -> ssl.SSLContext:
    """Create an SSLContext using the freshest CA bundle available on the system."""
    ca_bundle = _find_ca_bundle()
    if ca_bundle:
        return ssl.create_default_context(cafile=ca_bundle)
    return ssl.create_default_context()


def build_opener(
    jar: http.cookiejar.CookieJar | None = None,
    *,
    follow_redirects: bool = True,
) -> urllib.request.OpenerDirector:
    """Build a urllib OpenerDirector with SSL context, cookies, and browser User-Agent."""
    handlers: list[urllib.request.BaseHandler] = [
        urllib.request.HTTPSHandler(context=_create_ssl_context())
    ]
    if jar is not None:
        handlers.append(urllib.request.HTTPCookieProcessor(jar))
    if not follow_redirects:
        handlers.append(_NoRedirectHandler())
    opener = urllib.request.build_opener(*handlers)
    opener.addheaders = [
        ("User-Agent", USER_AGENT),
        ("Accept", "application/json, text/plain, */*"),
    ]
    return opener


def read_json(
    opener: urllib.request.OpenerDirector, req: urllib.request.Request | str
) -> Any:
    """Open `req` with `opener` and decode the response body as JSON."""
    with opener.open(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

