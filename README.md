# coop-skill

Minimal CLI and agent skill for interacting with `coop.se` over direct HTTP requests (no browser required).

## Requirements

- Python 3.10+ (standard library only — no dependencies to install)
- Bash (for the `coop` launcher)

## Setup

Create a `.env` file in the project root (or in `~/.config/coop/.env`) with your credentials:

```env
COOP_USERNAME=your-email@example.com
COOP_PASSWORD=your-password
```

That's it — no install step. Run the `coop` executable from any working directory by its path
(`/path/to/coop-skill/coop` or `./coop`), or symlink it onto your `PATH` (the launcher resolves symlinks):

```bash
ln -s "$PWD/coop" ~/.local/bin/coop
```

## Usage

All commands output concise, structured JSON by default, with `-f` / `--fields <f1,f2,...>` to request additional fields and `--raw` (or `--json`) for the full unprojected API response:

```bash
coop init [-n 50]                             # Ensure login & cache last N orders for search stats
coop login                                    # Log in and save session cookies
coop search <query> [-n 10] [-f <fields>]     # Search for products (includes recent purchase counts)
coop info <id> [<id> ...] [-f <fields>]       # Get detailed product info by ID/EAN (aliases: item, get, show)
coop add <id> [qty] [<id> [qty] ...] [-f <fields>] # Add one or more items to cart (also accepts <id>:<qty>)
coop add <id> <qty> [<id> <qty> ...] --set    # Set exact item quantities in cart (0 to remove)
coop cart [-f <fields>]                       # View current cart
coop orders [-n 20] [--page 0] [-f <fields>]  # List earlier orders (alias: history)
coop order [<order_id> ...] [-f <fields>]     # View items in an order (defaults to latest order)
```

Options:

- `-f` / `--fields <f1,f2,...>` adds extra fields to the JSON output:
  - `search` / `info`: `comparative_price`, `category`, `origin`, `labels`, `description`, `ingredients`, `nutrition`, `storage`, `deposit`, `vat`, `image`, `sustainability`, `all` (or any raw product key).
  - `cart` / `add`: `brand`, `size`, `unit`, `replaceable` (or any raw cart/entry key).
  - `orders`: `address`, `window`, `tracking`, `editable`, `cancellable`.
  - `order`: `unit`, `promo`, `url`, `image`, `address`, `payment`.
- `--raw` (alias `--json`) on `init`, `search`, `info`, `add`, `cart`, `orders`, or `order` prints the full, unprojected API/cache response.
- `init` accepts `-n`/`--orders <n>` (number of recent orders to cache, default `50`).
- `search` also accepts `--skip <n>` (pagination) and `--store <id>`; `info` accepts `--store <id>`.
- `orders` accepts `-n`/`--limit <n>` and `--page <p>` (0-based page index).
- Global options (before the command): `--env-file <path>`, `--cookie-file <path>`.

Login and session recovery happen automatically when `init`/`add`/`cart`/`orders`/`order` need it (including clearing and refreshing expired or invalid cookies/tokens), so `coop login` is rarely required.

## State and configuration files

Runtime caches are stored globally under `~/.cache/coop/` (or `$XDG_CACHE_HOME/coop/`):

| Path                                 | Purpose                                                       |
| ------------------------------------ | ------------------------------------------------------------- |
| `.env` or `~/.config/coop/.env`      | `COOP_USERNAME` / `COOP_PASSWORD`                             |
| `~/.cache/coop/cookies.txt`          | Session cookies from login (mode `600`)                       |
| `~/.cache/coop/session_cache.json`   | Cached SPA bearer token, valid ~15 min (mode `600`)           |
| `~/.cache/coop/orders_cache.json`    | Cached item purchase counts from `coop init` (mode `600`)     |

## Code layout

`coop` is a tiny bash launcher that runs `python3 -m coop_cli`. All code lives in `coop_cli/`:

```text
coop_cli/
├── __main__.py        # `python -m coop_cli` entry point
├── cli.py             # Global options (--env-file, --cookie-file) + dispatch
├── config.py          # Constants, default file paths, .env/credential loading
├── http_client.py     # urllib opener (SSL, cookies, User-Agent), JSON helper
├── auth.py            # OIDC login, cookie jar, SPA bearer-token session cache
├── formatting.py      # Shared output helpers (prices, cart/order tables, JSON)
├── api/
│   ├── products.py    # Product search & lookup (public, no login)
│   ├── cart.py        # Cart read/update (requires login)
│   └── orders.py      # Order history & single-order details (requires login)
└── commands/          # One file per subcommand: register() + run()
    ├── init.py
    ├── login.py
    ├── search.py
    ├── info.py
    ├── add.py
    ├── cart.py
    ├── orders.py
    └── order.py
```

Request flow: `commands/*` → `api/*` → `auth.py` (cart/orders) → `http_client.py`.

To add a command: create `commands/<name>.py` with `register(subparsers)` and `run(args)`, then add it to `ALL_COMMANDS` in `commands/__init__.py`.
