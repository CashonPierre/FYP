"""
Pre-defined symbol universes for multi-asset backtesting.

Each universe is a named list of ticker symbols supported by yfinance.
Universes are resolved to symbol lists at runtime — no DB table needed.

Full-index lists (sp500, nasdaq100) were snapshotted from Wikipedia; they
will drift over time as constituents change. Re-run tools/refresh_indices.py
to update them.
"""

from __future__ import annotations


_SP500 = [
    "A", "AAPL", "ABBV", "ABNB", "ABT", "ACGL", "ACN", "ADBE", "ADI", "ADM",
    "ADP", "ADSK", "AEE", "AEP", "AES", "AFL", "AIG", "AIZ", "AJG", "AKAM",
    "ALB", "ALGN", "ALL", "ALLE", "AMAT", "AMCR", "AMD", "AME", "AMGN", "AMP",
    "AMT", "AMZN", "ANET", "AON", "AOS", "APA", "APD", "APH", "APO", "APP",
    "APTV", "ARE", "ARES", "ATO", "AVB", "AVGO", "AVY", "AWK", "AXON", "AXP",
    "AZO", "BA", "BAC", "BALL", "BAX", "BBY", "BDX", "BEN", "BF-B", "BG",
    "BIIB", "BK", "BKNG", "BKR", "BLDR", "BLK", "BMY", "BR", "BRK-B", "BRO",
    "BSX", "BX", "BXP", "C", "CAG", "CAH", "CARR", "CASY", "CAT", "CB",
    "CBOE", "CBRE", "CCI", "CCL", "CDNS", "CDW", "CEG", "CF", "CFG", "CHD",
    "CHRW", "CHTR", "CI", "CIEN", "CINF", "CL", "CLX", "CMCSA", "CME", "CMG",
    "CMI", "CMS", "CNC", "CNP", "COF", "COHR", "COIN", "COO", "COP", "COR",
    "COST", "CPAY", "CPB", "CPRT", "CPT", "CRH", "CRL", "CRM", "CRWD", "CSCO",
    "CSGP", "CSX", "CTAS", "CTRA", "CTSH", "CTVA", "CVNA", "CVS", "CVX", "D",
    "DAL", "DASH", "DD", "DDOG", "DE", "DECK", "DELL", "DG", "DGX", "DHI",
    "DHR", "DIS", "DLR", "DLTR", "DOC", "DOV", "DOW", "DPZ", "DRI", "DTE",
    "DUK", "DVA", "DVN", "DXCM", "EA", "EBAY", "ECL", "ED", "EFX", "EG",
    "EIX", "EL", "ELV", "EME", "EMR", "EOG", "EPAM", "EQIX", "EQR", "EQT",
    "ERIE", "ES", "ESS", "ETN", "ETR", "EVRG", "EW", "EXC", "EXE", "EXPD",
    "EXPE", "EXR", "F", "FANG", "FAST", "FCX", "FDS", "FDX", "FE", "FFIV",
    "FICO", "FIS", "FISV", "FITB", "FIX", "FOX", "FOXA", "FRT", "FSLR", "FTNT",
    "FTV", "GD", "GDDY", "GE", "GEHC", "GEN", "GEV", "GILD", "GIS", "GL",
    "GLW", "GM", "GNRC", "GOOG", "GOOGL", "GPC", "GPN", "GRMN", "GS", "GWW",
    "HAL", "HAS", "HBAN", "HCA", "HD", "HIG", "HII", "HLT", "HON", "HOOD",
    "HPE", "HPQ", "HRL", "HSIC", "HST", "HSY", "HUBB", "HUM", "HWM", "IBKR",
    "IBM", "ICE", "IDXX", "IEX", "IFF", "INCY", "INTC", "INTU", "INVH", "IP",
    "IQV", "IR", "IRM", "ISRG", "IT", "ITW", "IVZ", "J", "JBHT", "JBL",
    "JCI", "JKHY", "JNJ", "JPM", "KDP", "KEY", "KEYS", "KHC", "KIM", "KKR",
    "KLAC", "KMB", "KMI", "KO", "KR", "KVUE", "L", "LDOS", "LEN", "LH",
    "LHX", "LII", "LIN", "LITE", "LLY", "LMT", "LNT", "LOW", "LRCX", "LULU",
    "LUV", "LVS", "LYB", "LYV", "MA", "MAA", "MAR", "MAS", "MCD", "MCHP",
    "MCK", "MCO", "MDLZ", "MDT", "MET", "META", "MGM", "MKC", "MLM", "MMM",
    "MNST", "MO", "MOS", "MPC", "MPWR", "MRK", "MRNA", "MRSH", "MS", "MSCI",
    "MSFT", "MSI", "MTB", "MTD", "MU", "NCLH", "NDAQ", "NDSN", "NEE", "NEM",
    "NFLX", "NI", "NKE", "NOC", "NOW", "NRG", "NSC", "NTAP", "NTRS", "NUE",
    "NVDA", "NVR", "NWS", "NWSA", "NXPI", "O", "ODFL", "OKE", "OMC", "ON",
    "ORCL", "ORLY", "OTIS", "OXY", "PANW", "PAYX", "PCAR", "PCG", "PEG", "PEP",
    "PFE", "PFG", "PG", "PGR", "PH", "PHM", "PKG", "PLD", "PLTR", "PM",
    "PNC", "PNR", "PNW", "PODD", "POOL", "PPG", "PPL", "PRU", "PSA", "PSKY",
    "PSX", "PTC", "PWR", "PYPL", "Q", "QCOM", "RCL", "REG", "REGN", "RF",
    "RJF", "RL", "RMD", "ROK", "ROL", "ROP", "ROST", "RSG", "RTX", "RVTY",
    "SATS", "SBAC", "SBUX", "SCHW", "SHW", "SJM", "SLB", "SMCI", "SNA", "SNDK",
    "SNPS", "SO", "SOLV", "SPG", "SPGI", "SRE", "STE", "STLD", "STT", "STX",
    "STZ", "SW", "SWK", "SWKS", "SYF", "SYK", "SYY", "T", "TAP", "TDG",
    "TDY", "TECH", "TEL", "TER", "TFC", "TGT", "TJX", "TKO", "TMO", "TMUS",
    "TPL", "TPR", "TRGP", "TRMB", "TROW", "TRV", "TSCO", "TSLA", "TSN", "TT",
    "TTD", "TTWO", "TXN", "TXT", "TYL", "UAL", "UBER", "UDR", "UHS", "ULTA",
    "UNH", "UNP", "UPS", "URI", "USB", "V", "VICI", "VLO", "VLTO", "VMC",
    "VRSK", "VRSN", "VRT", "VRTX", "VST", "VTR", "VTRS", "VZ", "WAB", "WAT",
    "WBD", "WDAY", "WDC", "WEC", "WELL", "WFC", "WM", "WMB", "WMT", "WRB",
    "WSM", "WST", "WTW", "WY", "WYNN", "XEL", "XOM", "XYL", "XYZ", "YUM",
    "ZBH", "ZBRA", "ZTS",
]

_NASDAQ100 = [
    "AAPL", "ABNB", "ADBE", "ADI", "ADP", "ADSK", "AEP", "ALNY", "AMAT", "AMD",
    "AMGN", "AMZN", "APP", "ARM", "ASML", "AVGO", "AXON", "BKNG", "BKR", "CCEP",
    "CDNS", "CEG", "CHTR", "CMCSA", "COST", "CPRT", "CRWD", "CSCO", "CSGP", "CSX",
    "CTAS", "CTSH", "DASH", "DDOG", "DXCM", "EA", "EXC", "FANG", "FAST", "FER",
    "FTNT", "GEHC", "GILD", "GOOG", "GOOGL", "HON", "IDXX", "INSM", "INTC", "INTU",
    "ISRG", "KDP", "KHC", "KLAC", "LIN", "LRCX", "MAR", "MCHP", "MDLZ", "MELI",
    "META", "MNST", "MPWR", "MRVL", "MSFT", "MSTR", "MU", "NFLX", "NVDA", "NXPI",
    "ODFL", "ORLY", "PANW", "PAYX", "PCAR", "PDD", "PEP", "PLTR", "PYPL", "QCOM",
    "REGN", "ROP", "ROST", "SBUX", "SHOP", "SNPS", "STX", "TEAM", "TMUS", "TRI",
    "TSLA", "TTWO", "TXN", "VRSK", "VRTX", "WBD", "WDAY", "WDC", "WMT", "XEL",
    "ZS",
]

_SECTOR_ETFS = [
    "XLB", "XLC", "XLE", "XLF", "XLI", "XLK",
    "XLP", "XLRE", "XLU", "XLV", "XLY",
]

_CRYPTO_TOP30 = [
    "BTC-USD", "ETH-USD", "BNB-USD", "XRP-USD", "SOL-USD",
    "ADA-USD", "DOGE-USD", "TRX-USD", "DOT-USD", "MATIC-USD",
    "AVAX-USD", "SHIB-USD", "LTC-USD", "LINK-USD", "ATOM-USD",
    "UNI-USD", "NEAR-USD", "APT-USD", "ARB-USD", "OP-USD",
    "FIL-USD", "XLM-USD", "HBAR-USD", "ICP-USD", "VET-USD",
    "CRO-USD", "ALGO-USD", "MANA-USD", "SAND-USD", "AXS-USD",
]

_INTL_ADRS = [
    "BABA", "JD", "PDD", "TSM", "ASML", "NVO", "SAP", "TM", "SONY", "NVS",
    "AZN", "BP", "SHEL", "GSK", "UL", "HSBC", "BCS", "HDB", "INFY", "RIO",
    "BHP", "TEVA", "TTE", "EQNR", "SNY",
]


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
    "sp500": {
        "name": "S&P 500 (full)",
        "description": "All current S&P 500 constituents (snapshotted from Wikipedia)",
        "symbols": _SP500,
    },
    "nasdaq100": {
        "name": "NASDAQ 100 (full)",
        "description": "All current NASDAQ-100 constituents (snapshotted from Wikipedia)",
        "symbols": _NASDAQ100,
    },
    "sector_etfs": {
        "name": "SPDR Sector ETFs",
        "description": "All 11 SPDR sector-select ETFs",
        "symbols": _SECTOR_ETFS,
    },
    "crypto": {
        "name": "Crypto Top 5",
        "description": "Top 5 cryptocurrencies by market cap (via Yahoo Finance)",
        "symbols": ["BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD"],
    },
    "crypto_top30": {
        "name": "Crypto Top 30",
        "description": "Top 30 cryptocurrencies by market cap (via Yahoo Finance)",
        "symbols": _CRYPTO_TOP30,
    },
    "intl_adrs": {
        "name": "International ADRs",
        "description": "Liquid non-US stocks listed as ADRs on US exchanges",
        "symbols": _INTL_ADRS,
    },
    "etf_core": {
        "name": "Core ETFs",
        "description": "Widely-used broad market and sector ETFs",
        "symbols": [
            "SPY", "QQQ", "IWM", "DIA",
            "GLD", "TLT", "VNQ",
            "XLE", "XLF", "XLK",
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
