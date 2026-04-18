"""
Standalone CLI script — seed or refresh company fundamentals.

Usage:
  # Refresh specific symbols
  uv run python scripts/refresh_fundamentals.py --symbols AAPL MSFT NVDA

  # Refresh a named universe
  uv run python scripts/refresh_fundamentals.py --universe mag7

  # Refresh every symbol in every universe
  uv run python scripts/refresh_fundamentals.py --all-universes

Run from the backend/ directory so the package imports resolve correctly.
"""

from __future__ import annotations

import argparse
import os
import sys

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
  sys.path.insert(0, _BACKEND_DIR)


def _refresh(symbols: list[str], filing_lag_days: int, dry_run: bool) -> None:
  from background.tasks.fundamentals_refresh import fetch_fundamentals

  total = 0
  failed: list[str] = []

  for i, symbol in enumerate(symbols, 1):
    print(f"[{i}/{len(symbols)}] {symbol} ...", end=" ", flush=True)
    if dry_run:
      print("(dry run — skipped)")
      continue
    try:
      result = fetch_fundamentals(
        symbol=symbol, filing_lag_days=filing_lag_days,
      )
      periods = result["periods_upserted"]
      total += periods
      print(f"{periods} periods upserted")
    except Exception as exc:
      print(f"FAILED: {exc}")
      failed.append(symbol)

  print()
  print(f"Done. {total} period-rows upserted across {len(symbols) - len(failed)} symbols.")
  if failed:
    print(f"Failed ({len(failed)}): {', '.join(failed)}")
    sys.exit(1)


def main() -> None:
  parser = argparse.ArgumentParser(
    description="Seed or refresh company fundamentals from yfinance.",
  )
  source = parser.add_mutually_exclusive_group(required=True)
  source.add_argument("--symbols", nargs="+", metavar="TICKER")
  source.add_argument("--universe", metavar="KEY")
  source.add_argument("--all-universes", action="store_true")

  parser.add_argument(
    "--filing-lag-days", type=int, default=45,
    help="Days to add to period_end when computing available_from (default: 45)",
  )
  parser.add_argument("--dry-run", action="store_true")

  args = parser.parse_args()

  if args.symbols:
    symbols = [s.upper().strip() for s in args.symbols]
  elif args.universe:
    from api.market.universes import get_universe_symbols
    try:
      symbols = get_universe_symbols(args.universe)
    except KeyError:
      print(f"Error: unknown universe '{args.universe}'.")
      sys.exit(1)
    print(f"Universe '{args.universe}': {len(symbols)} symbols")
  else:
    from api.market.universes import UNIVERSES
    seen: set[str] = set()
    symbols = []
    for meta in UNIVERSES.values():
      for s in meta["symbols"]:
        if s not in seen:
          seen.add(s)
          symbols.append(s)
    print(f"All universes: {len(symbols)} unique symbols")

  _refresh(symbols, filing_lag_days=args.filing_lag_days, dry_run=args.dry_run)


if __name__ == "__main__":
  main()
