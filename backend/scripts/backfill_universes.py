"""
One-shot script: fetch OHLC for every symbol in every universe, upsert into DB.

Reads target DB from env (same as the running backend). Override via:
  DATABASE_HOST=... DATABASE_PORT=... DATABASE_USERNAME=... DATABASE_PASSWORD=... \
  python -m scripts.backfill_universes

Incremental: fetch_and_upsert resumes from latest bar already in DB per symbol,
so re-running is safe.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.market.universes import UNIVERSES
from background.tasks.market_refresh import fetch_and_upsert


def main(timeframe: str = "1D") -> None:
  symbols: list[str] = []
  seen: set[str] = set()
  for u in UNIVERSES.values():
    for s in u["symbols"]:
      if s not in seen:
        seen.add(s)
        symbols.append(s)

  total = len(symbols)
  print(f"Backfilling {total} symbols at {timeframe} …", flush=True)

  ok = 0
  empty = 0
  failed: list[tuple[str, str]] = []
  t0 = time.time()

  for i, sym in enumerate(symbols, 1):
    try:
      result = fetch_and_upsert(symbol=sym, timeframe=timeframe)
      rows = result["rows_upserted"]
      if rows == 0:
        empty += 1
      else:
        ok += 1
      elapsed = time.time() - t0
      rate = i / max(elapsed, 1e-6)
      eta = (total - i) / max(rate, 1e-6)
      print(f"[{i:>4}/{total}] {sym:<10} rows={rows:<6} | {rate:.2f}/s ETA {eta/60:.1f}min", flush=True)
    except Exception as e:
      failed.append((sym, str(e)[:120]))
      print(f"[{i:>4}/{total}] {sym:<10} FAILED: {e}", flush=True)

  print("-" * 60, flush=True)
  print(f"done in {(time.time() - t0) / 60:.1f}min", flush=True)
  print(f"  new data: {ok}", flush=True)
  print(f"  up-to-date: {empty}", flush=True)
  print(f"  failed: {len(failed)}", flush=True)
  for sym, err in failed[:20]:
    print(f"    {sym}: {err}", flush=True)


if __name__ == "__main__":
  main()
