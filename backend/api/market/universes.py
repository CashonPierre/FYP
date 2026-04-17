"""
Pre-defined symbol universes for multi-asset backtesting.

Each universe is a named list of ticker symbols supported by yfinance.
Universes are resolved to symbol lists at runtime — no DB table needed.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Universe definitions
# ---------------------------------------------------------------------------

UNIVERSES: dict[str, dict] = {
    "mag7": {
        "name": "Magnificent 7",
        "description": "The seven largest US mega-cap tech stocks",
        "symbols": ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA"],
    },
    "dow30": {
        "name": "Dow Jones Industrial Average",
        "description": "The 30 blue-chip stocks in the Dow Jones Industrial Average",
        "symbols": [
            "AAPL", "AMGN", "AXP", "BA", "CAT", "CRM", "CSCO", "CVX",
            "DIS", "DOW", "GS", "HD", "HON", "IBM", "JNJ", "JPM",
            "KO", "MCD", "MMM", "MRK", "MSFT", "NKE", "PG", "SHW",
            "TRV", "UNH", "V", "VZ", "WMT", "AMZN",
        ],
    },
    "nasdaq_top20": {
        "name": "NASDAQ Top 20",
        "description": "Top 20 NASDAQ-listed companies by market cap",
        "symbols": [
            "AAPL", "MSFT", "NVDA", "AMZN", "META", "TSLA", "GOOGL",
            "GOOG", "AVGO", "COST", "NFLX", "ADBE", "AMD", "QCOM",
            "INTC", "CSCO", "TXN", "AMAT", "INTU", "MU",
        ],
    },
    "sp500_top20": {
        "name": "S&P 500 Top 20",
        "description": "Top 20 S&P 500 companies by market cap",
        "symbols": [
            "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG",
            "BRK-B", "TSLA", "AVGO", "JPM", "LLY", "UNH", "V",
            "XOM", "MA", "JNJ", "PG", "HD", "COST",
        ],
    },
    "crypto": {
        "name": "Crypto Top 5",
        "description": "Top 5 cryptocurrencies by market cap (via Yahoo Finance)",
        "symbols": ["BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD"],
    },
    "etf_core": {
        "name": "Core ETFs",
        "description": "Widely-used broad market and sector ETFs",
        "symbols": [
            "SPY",   # S&P 500
            "QQQ",   # NASDAQ 100
            "IWM",   # Russell 2000 (small cap)
            "DIA",   # Dow Jones
            "GLD",   # Gold
            "TLT",   # 20+ Year Treasury
            "VNQ",   # Real Estate
            "XLE",   # Energy
            "XLF",   # Financials
            "XLK",   # Technology
        ],
    },
}


def get_universe_symbols(key: str) -> list[str]:
    """Return symbol list for a universe key. Raises KeyError if not found."""
    return UNIVERSES[key]["symbols"]


def list_universes() -> dict[str, dict]:
    """Return all universes with metadata (excludes full symbol lists for brevity)."""
    return {
        k: {
            "name": v["name"],
            "description": v["description"],
            "count": len(v["symbols"]),
            "symbols": v["symbols"],
        }
        for k, v in UNIVERSES.items()
    }
