"""
Standalone CLI script — seed or refresh OHLCV market data.

Usage:
  # Refresh specific symbols
  uv run python scripts/refresh_ohlc.py --symbols AAPL MSFT NVDA

  # Refresh a named universe
  uv run python scripts/refresh_ohlc.py --universe mag7

  # Seed a universe from a specific start date (first-time load)
  uv run python scripts/refresh_ohlc.py --universe sp500_top20 --start 2010-01-01

  # Refresh all universe symbols (full initial seed)
  uv run python scripts/refresh_ohlc.py --all-universes --start 2010-01-01

  # List available universes
  uv run python scripts/refresh_ohlc.py --list-universes

Run from the backend/ directory so that the package imports resolve correctly.
"""

from __future__ import annotations

import argparse
import sys
import os

# Ensure backend package root is on sys.path when run as a script
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


def _list_universes() -> None:
    from api.market.universes import UNIVERSES
    print(f"{'Key':<20} {'Name':<35} Symbols")
    print("-" * 75)
    for key, meta in UNIVERSES.items():
        print(f"{key:<20} {meta['name']:<35} {len(meta['symbols'])}")
        print(f"  {', '.join(meta['symbols'])}")
        print()


def _refresh(symbols: list[str], timeframe: str, start: str | None, dry_run: bool) -> None:
    from background.tasks.market_refresh import fetch_and_upsert

    total_upserted = 0
    failed: list[str] = []

    for i, symbol in enumerate(symbols, 1):
        print(f"[{i}/{len(symbols)}] {symbol} ...", end=" ", flush=True)
        if dry_run:
            print("(dry run — skipped)")
            continue
        try:
            result = fetch_and_upsert(symbol=symbol, timeframe=timeframe, start=start)
            rows = result["rows_upserted"]
            total_upserted += rows
            print(f"{rows} rows upserted (from {result['fetch_start']})")
        except Exception as exc:
            print(f"FAILED: {exc}")
            failed.append(symbol)

    print()
    print(f"Done. {total_upserted} rows upserted across {len(symbols) - len(failed)} symbols.")
    if failed:
        print(f"Failed ({len(failed)}): {', '.join(failed)}")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed or refresh OHLCV market data from yfinance into the DB.",
    )

    source = parser.add_mutually_exclusive_group(required=False)
    source.add_argument("--symbols", nargs="+", metavar="TICKER", help="Explicit ticker list")
    source.add_argument("--universe", metavar="KEY", help="Named universe (e.g. mag7, dow30)")
    source.add_argument("--all-universes", action="store_true", help="Refresh all defined universes")
    source.add_argument("--list-universes", action="store_true", help="Print available universes and exit")

    parser.add_argument("--timeframe", default="1D", choices=["1D", "1W", "1M"], help="Bar timeframe (default: 1D)")
    parser.add_argument("--start", metavar="YYYY-MM-DD", help="Force fetch from this date (default: resume from last bar in DB)")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be fetched without writing to DB")

    args = parser.parse_args()

    if args.list_universes:
        _list_universes()
        return

    # Resolve symbol list
    symbols: list[str] = []

    if args.symbols:
        symbols = [s.upper().strip() for s in args.symbols]
    elif args.universe:
        from api.market.universes import get_universe_symbols, UNIVERSES
        try:
            symbols = get_universe_symbols(args.universe)
            print(f"Universe '{args.universe}': {len(symbols)} symbols")
        except KeyError:
            print(f"Error: unknown universe '{args.universe}'. Run --list-universes to see available options.")
            sys.exit(1)
    elif args.all_universes:
        from api.market.universes import UNIVERSES
        seen: set[str] = set()
        for meta in UNIVERSES.values():
            for sym in meta["symbols"]:
                if sym not in seen:
                    seen.add(sym)
                    symbols.append(sym)
        print(f"All universes: {len(symbols)} unique symbols")
    else:
        parser.print_help()
        sys.exit(0)

    if not symbols:
        print("No symbols to refresh.")
        sys.exit(0)

    _refresh(symbols=symbols, timeframe=args.timeframe, start=args.start, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
