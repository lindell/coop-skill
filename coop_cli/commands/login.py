"""`coop login` — log in to coop.se and save session cookies."""

from __future__ import annotations

import argparse
import sys

from coop_cli.auth import format_cookie_header, login_coop
from coop_cli.config import get_credentials


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "login", help="Log in to coop.se and save session cookies."
    )
    p.add_argument(
        "--print-header",
        action="store_true",
        help="Print the raw Cookie header for www.coop.se to stdout",
    )
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    username, password = get_credentials(args.env_file)
    if not username or not password:
        print(
            "Error: COOP_USERNAME and COOP_PASSWORD must be set in environment or .env",
            file=sys.stderr,
        )
        return 1

    jar = login_coop(username, password, cookie_file=args.cookie_file)
    if args.print_header:
        print(format_cookie_header(jar, "www.coop.se"))
    else:
        coop_cookies = [
            c.name for c in jar if "www.coop.se" in c.domain and c.path == "/"
        ]
        print(
            f"Successfully logged in to coop.se ({len(coop_cookies)} cookies set: {', '.join(coop_cookies)})."
        )
        print(f"Cookies saved to: {args.cookie_file}")
    return 0

