#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg2


def normalize_db_url(url: str) -> str:
    # SQLAlchemy URLs often include a driver segment (postgresql+psycopg2://...)
    return url.replace("postgresql+psycopg2://", "postgresql://", 1)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest OHLC CSV into TimescaleDB (ohlc_bars)."
    )
    parser.add_argument(
        "--csv",
        required=True,
        help="Path to CSV with columns: date,open,high,low,close,volume,Name",
    )
    parser.add_argument(
        "--db-url",
        default=os.environ.get("DATABASE_URL", ""),
        help="Postgres URL (or set DATABASE_URL).",
    )
    parser.add_argument(
        "--table",
        default="ohlc_bars",
        help="Target table name (default: ohlc_bars).",
    )
    parser.add_argument(
        "--timeframe",
        default="1D",
        help="Timeframe label to store (default: 1D).",
    )
    args = parser.parse_args()

    if not args.db_url:
        print("Missing --db-url (or env DATABASE_URL)", file=sys.stderr)
        return 2

    csv_path = Path(args.csv).expanduser().resolve()
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        return 2

    db_url = normalize_db_url(args.db_url)

    # We COPY into a temp table first so the script is safe to re-run.
    stage_sql = """
CREATE TEMP TABLE IF NOT EXISTS ohlc_stage (
  time timestamptz NOT NULL,
  open double precision NOT NULL,
  high double precision NOT NULL,
  low double precision NOT NULL,
  close double precision NOT NULL,
  volume bigint,
  symbol text NOT NULL
) ON COMMIT DROP;
TRUNCATE ohlc_stage;
"""

    copy_sql = """
COPY ohlc_stage (time, open, high, low, close, volume, symbol)
FROM STDIN WITH (FORMAT csv, HEADER true)
"""

    upsert_sql = f"""
INSERT INTO {args.table} (time, symbol, timeframe, open, high, low, close, volume)
SELECT time, symbol, %s, open, high, low, close, volume
FROM ohlc_stage
ON CONFLICT (symbol, timeframe, time) DO UPDATE SET
  open = EXCLUDED.open,
  high = EXCLUDED.high,
  low = EXCLUDED.low,
  close = EXCLUDED.close,
  volume = EXCLUDED.volume;
"""

    print(f"Connecting to DB: {db_url.split('@')[-1]}")
    print(f"Ingesting: {csv_path} -> {args.table}")

    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(stage_sql)
            with csv_path.open("r", encoding="utf-8") as f:
                cur.copy_expert(copy_sql, f)
            cur.execute(upsert_sql, (args.timeframe,))
        conn.commit()

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
