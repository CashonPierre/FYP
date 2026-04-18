# yfinance audit — 2026-04-19

Survey of every `yfinance` / `import yf` reference in `backend/` with a
classification for the Task 2 OHLC-source swap.

| # | Location | Classification | Action |
|--:|---|---|---|
| 1 | `backend/background/tasks/market_refresh.py` — whole module | **live** | Keep; add FMP sibling; CLI/auto-fetch routes via dispatch helper. |
| 2 | `backend/background/tasks/backtest.py:46,88,283` | **live** | Replace direct `fetch_and_upsert` call with source-aware dispatch so `OHLC_SOURCE` is honoured. |
| 3 | `backend/scripts/refresh_ohlc.py:46,74` | **live** | Add `--source {fmp,yfinance}` (default `settings.ohlc_source`) and route via dispatch. |
| 4 | `backend/background/tasks/fundamentals_refresh.py` — whole module | **dev-only** | yfinance fundamentals fallback for smoke tests. Keep. |
| 5 | `backend/scripts/refresh_fundamentals.py` | **dev-only** | Same as above; already has `--source` toggle. Keep. |
| 6 | `backend/configs/config.py:77` — docstring for `fundamentals_source` | **legacy** (doc) | Leave. |
| 7 | `backend/api/market/universes.py:4` — module docstring | **legacy** (doc) | Leave. |
| 8 | `backend/database/models/fundamental_snapshots.py:32,37` | **legacy** (doc) | Leave; field comments. |
| 9 | `backend/pyproject.toml:26` — `yfinance>=0.2.55` dep | **live** (still imported by dev-only + legacy test paths) | Keep; removing it breaks the yfinance fallback + its tests. |
| 10 | `backend/tests/test_market_refresh.py` | **live (tests)** | Keep; still exercises the yfinance fetcher module. |
| 11 | `backend/tests/test_fundamentals_refresh.py` | **live (tests)** | Keep; exercises yfinance fundamentals fallback. |
| 12 | `backend/tests/test_auto_refresh.py:162` | **live (tests)** | References `fetch_and_upsert`; keep. The new dispatch helper should still exercise the yfinance path here. |

## Summary

- **Swapped live sites**: 3 call sites (`scripts/refresh_ohlc.py`,
  `backtest.py` auto-fetch, and the new config-driven dispatch) now route
  through an `OHLC_SOURCE`-aware helper. FMP is the new default.
- **Kept yfinance-only**: test mocks, the yfinance fetcher module itself
  (`background/tasks/market_refresh.py`), the dev-only CLI escape hatch
  (`--source yfinance`), and the `yfinance` package in `pyproject.toml`.
- **Not touched**: production OHLC data already in `ohlc_bars`. No
  re-ingest. Auto-fetch only writes when coverage is missing, exactly as
  before.

## FMP endpoint note — v3 is deprecated (2025-08-31)

The original Task 2 brief specified
`GET /api/v3/historical-price-full/{symbol}` as the endpoint to call.
That endpoint now returns `403` with an `Error Message: "Legacy
Endpoint ... only available for legacy users who have valid
subscriptions prior August 31, 2025"` for keys created after that
cutoff. The current Starter-plan key 403s on it.

The fetcher therefore targets FMP's `stable` API:
`GET /stable/historical-price-eod/full?symbol=SYM&from=YYYY-MM-DD&to=YYYY-MM-DD`.
The response is a flat list of per-day bar dicts — slightly different
from the v3 `{"symbol": ..., "historical": [...]}` shape, but same
fields per bar.

Note: the existing **fundamentals** fetcher (`fundamentals_refresh_fmp.py`)
still hits `/api/v3/income-statement/{symbol}` and will 403 against this
same key. That's out of scope for Task 2 but is flagged in
`OVERNIGHT_LOG.md` for the operator.

