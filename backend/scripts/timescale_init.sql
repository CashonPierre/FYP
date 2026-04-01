-- TimescaleDB initialization for shared market data (Option A)
-- Run against your target database (not the default postgres DB).

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Shared OHLC dataset (daily/intraday).
-- Use timestamptz for future-proofing (intraday support).
CREATE TABLE IF NOT EXISTS ohlc_bars (
  time        timestamptz NOT NULL,
  symbol      text        NOT NULL,
  -- Keep timeframe in the primary key so you can store 1D/1H/etc in one table.
  -- For your current dataset, the ingest script will use timeframe = '1D'.
  timeframe   text        NOT NULL DEFAULT '1D',
  open        double precision NOT NULL,
  high        double precision NOT NULL,
  low         double precision NOT NULL,
  close       double precision NOT NULL,
  volume      bigint,
  PRIMARY KEY (symbol, timeframe, time)
);

-- Convert to hypertable (time-series).
SELECT create_hypertable(
  'ohlc_bars',
  by_range('time'),
  if_not_exists => TRUE
);

-- Helpful index patterns (Timescale may create defaults; keep explicit for clarity).
CREATE INDEX IF NOT EXISTS idx_ohlc_bars_symbol_time_desc
  ON ohlc_bars (symbol, timeframe, time DESC);
