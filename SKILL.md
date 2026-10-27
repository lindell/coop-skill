---
name: coop
description: Search products, inspect item details, manage the shopping cart, and view earlier orders on coop.se using the `coop` CLI.
---

# Coop.se Skill

Run `<skill-dir>/coop` (where `<skill-dir>` is the folder containing this `SKILL.md`) to interact with `coop.se`. It can be executed from **any** working directory — credentials are loaded automatically from `<skill-dir>/.env` (or `~/.config/coop/.env`), and session cookies, token cache, and order history cache are stored globally in `~/.cache/coop/`.

All commands output **concise, structured JSON** by default (containing only the core fields needed to make decisions), with `-f` / `--fields <f1,f2,...>` to include extra fields on demand and `--raw` (or `--json`) for the full unprojected API response.

## Commands

- **Initialize session & cache recent orders** (recommended first step — ensures login and caches the last `N` orders so `search`/`info` include how often each item has been bought lately):

  ```bash
  <skill-dir>/coop init [-n <orders>] [--raw]           # Default: last 50 orders
  ```

- **Login** (rarely needed — auto-invoked and auto-recovered by `init`/`add`/`cart`/`orders`/`order`):

  ```bash
  <skill-dir>/coop login
  ```

- **Search for products**:

  ```bash
  <skill-dir>/coop search <query> [-n <limit>] [--skip <offset>] [--store <store_id>] [-f <fields>] [--raw]
  ```

  Returns `id` (EAN), `name`, `brand`, `size`, `price`, `unit`, `promo` (if active), and `bought` (`orders`, `total_qty`, `last_ordered` from cached recent orders).
  Extra `-f` / `--fields`: `comparative_price`, `category`, `origin`, `labels`, `ingredients`, `nutrition`, `storage`, `deposit`, `vat`, `image`, `sustainability`, or `all` (plus any raw API key).

- **Get product details** (aliases: `item`, `get`, `show`):

  ```bash
  <skill-dir>/coop info <product_id> [<product_id> ...] [--store <store_id>] [-f <fields>] [--raw]
  ```

  Returns the core product fields plus `comparative_price`, `category`, `available_online`, `origin`, `labels`, `description`, `ingredients`, and `nutrition`.
  Extra `-f` / `--fields`: `storage`, `deposit`, `vat`, `image`, `sustainability`, or `all`.
  Pass multiple IDs in one call to compare products.

- **Add or update cart items**:

  ```bash
  <skill-dir>/coop add <product_id> [quantity] [-f <fields>]                    # Increment item quantity (default: +1)
  <skill-dir>/coop add <id>[:<qty>] [<id>[:<qty>] ...] [-f <fields>]            # Add multiple items in one call
  <skill-dir>/coop add <id> <qty> [<id> <qty> ...] --set [-f <fields>]          # Set exact quantities (use 0 to remove)
  ```

  Accepts one or more items as `<id> [qty]` or `<id>:<qty>` (default quantity `1`).
  Prints the updated cart summary JSON afterwards, so a separate `<skill-dir>/coop cart` call is not needed.

- **View current cart**:

  ```bash
  <skill-dir>/coop cart [-f <fields>] [--raw]
  ```

  Extra `-f` / `--fields`: `brand`, `size`, `unit`, `replaceable` (or any raw cart/entry key).

- **List earlier orders** (alias: `history`):

  ```bash
  <skill-dir>/coop orders [-n <limit>] [--page <page>] [-f <fields>] [--raw]
  ```

  Returns order `id`, `placed` date, `delivery_date`, `status`, `delivery_mode`, and `total`.
  Extra `-f` / `--fields`: `address`, `window`, `tracking`, `editable`, `cancellable`.

- **View what is in an order**:

  ```bash
  <skill-dir>/coop order [<order_id> ...] [-f <fields>] [--raw]
  ```

  Returns order header (`id`, dates, `status`, `delivery_mode`, `store`, `subtotal`, `delivery_cost`, `discounts`, `total`) and `items` (`id`, `name`, `brand`, `size`, `qty`, `ordered_qty`, `unit_price`, `total_price`, `discount`, `delivered`, `replaces`).
  Extra `-f` / `--fields`: `unit`, `promo`, `url`, `image`, `address`, `payment`.
  Omit `<order_id>` to inspect the most recent order, or pass multiple IDs to inspect several orders at once.

## Typical Workflow

1. Run `<skill-dir>/coop init` once at the start of a session to ensure login and cache recent orders.
2. Search for the desired item with `<skill-dir>/coop search <term>` to find its product ID (EAN) and see which variant has been bought lately (`bought`). Use `-f comparative_price,origin` etc. if needed.
3. Optionally inspect full nutrition or ingredients with `<skill-dir>/coop info <id>` (or `<skill-dir>/coop search <term> -f ingredients,nutrition`).
4. Add item(s) to the cart with `<skill-dir>/coop add <id> [qty]` or `<skill-dir>/coop add <id1>:<qty1> <id2>:<qty2> ...` (check the returned cart JSON to confirm).
5. Use `<skill-dir>/coop cart` to review the full cart at any time.

## Notes

- `<skill-dir>/coop add` without `--set` **increments**; to change an item to a specific amount, use `--set`.
- Use `-f <field1,field2>` to pull in extra fields without dumping the entire raw API payload, or `--raw` when you need the complete unmodified response.
- Code lives in `coop_cli/` (one file per command in `coop_cli/commands/`); see `README.md` for the layout.
