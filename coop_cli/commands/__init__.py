"""One module per CLI subcommand.

Each module exposes `register(subparsers)`, which adds its subparser and
binds `run(args) -> int` as the handler via `set_defaults(func=run)`.
"""

from coop_cli.commands import add, cart, info, init, login, order, orders, search

# Order here is the order commands appear in `coop --help`.
ALL_COMMANDS = [init, login, search, info, add, cart, orders, order]

