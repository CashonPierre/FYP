"""
Standalone CLI script — seed or refresh company fundamentals.

Usage:
  # Refresh specific symbols (FMP by default)
  uv run python scripts/refresh_fundamentals.py --symbols AAPL MSFT NVDA

  # Refresh a named universe
  uv run python scripts/refresh_fundamentals.py --universe mag7

  # Refresh every symbol in every universe
  uv run python scripts/refresh_fundamentals.py --all-universes

  # Force yfinance (smoke tests only — Yahoo exposes ~5 recent quarters)
  uv run python scripts/refresh_fundamentals.py --symbols AAPL --source yfinance

Set FMP_API_KEY in your .env (or as a shell export) before running with
--source fmp. Run from the backend/ directory so the package imports resolve.
"""

from __future__ import annotations

import argparse
import os
import sys

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
  sys.path.insert(0, _BACKEND_DIR)


def _refresh(
  symbols: list[str], filing_lag_days: int, dry_run: bool, source: str,
) -> None:
  if source == "fmp":
    from background.tasks.fundamentals_refresh_fmp import (
      fetch_fundamentals_fmp as _fetch,
    )
  elif source == "yfinance":
    from background.tasks.fundamentals_refresh import (
      fetch_fundamentals as _fetch,
    )
  else:
    raise ValueError(f"Unknown --source {source!r}; expected fmp | yfinance")

  total = 0
  failed: list[str] = []

  for i, symbol in enumerate(symbols, 1):
    print(f"[{i}/{len(symbols)}] {symbol} ...", end=" ", flush=True)
    if dry_run:
      print("(dry run — skipped)")
      continue
    try:
      result = _fetch(symbol=symbol, filing_lag_days=filing_lag_days)
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
    help="Days to add to period_end when computing available_from (default: 45). "
         "FMP source uses the actual filing date when available; this is a fallback.",
  )
  parser.add_argument(
    "--source", choices=("fmp", "yfinance"),
    default=os.environ.get("FUNDAMENTALS_SOURCE", "fmp"),
    help="Data source (default: fmp; yfinance kept for smoke tests only).",
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

  _refresh(
    symbols,
    filing_lag_days=args.filing_lag_days,
    dry_run=args.dry_run,
    source=args.source,
  )


if __name__ == "__main__":
  main()
