# Constants for Upstox Data
UPSTOX_MCX_URL = "https://assets.upstox.com/market-quote/instruments/exchange/MCX.json.gz"
DATA_FILENAME = "Data/MCX.json"

# Upstox API
UPSTOX_MARKET_QUOTE_URL = "https://api.upstox.com/v2/market-quote/quotes"
UPSTOX_HISTORICAL_CANDLE_URL = "https://api.upstox.com/v3/historical-candle"
UPSTOX_ORDER_URL = "https://api.upstox.com/v2/order/place"
UPSTOX_GTT_URL = "https://api.upstox.com/v2/order/gtt"
UPSTOX_POSITIONS_URL = "https://api.upstox.com/v2/portfolio/short-term-positions"
import os
from dotenv import load_dotenv

# Load token from hardcoded secure path: ~/tradingbridge/.token.env
# File format: UPSTOX_ACCESS_TOKEN=eyJ0eXAiOi...
_token_file = os.path.expanduser("~/tradingbridge/.token.env")
_token_cache = {"token": None, "mtime": None}

def _read_token_from_file():
    if os.path.isfile(_token_file):
        with open(_token_file, "r") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line.startswith("UPSTOX_ACCESS_TOKEN="):
                    return _line.split("=", 1)[1].strip()
    return None

def get_access_token():
    """Return the current access token, reloading from file if it has changed.
    Falls back to UPSTOX_ACCESS_TOKEN environment variable if the file is missing."""
    try:
        mtime = os.path.getmtime(_token_file)
        if _token_cache["token"] is not None and mtime == _token_cache["mtime"]:
            return _token_cache["token"]
        token = _read_token_from_file()
        if token:
            _token_cache["token"] = token
            _token_cache["mtime"] = mtime
            return token
    except Exception:
        pass
    # Fallback: environment variable (e.g. CI, Docker, or when token file is absent)
    return _token_cache["token"] or os.environ.get("UPSTOX_ACCESS_TOKEN", "").strip() or None

# Validate token exists at startup — file first, then env var
UPSTOX_ACCESS_TOKEN = _read_token_from_file() or os.environ.get("UPSTOX_ACCESS_TOKEN", "").strip() or None
if not UPSTOX_ACCESS_TOKEN:
    raise ValueError(
        "UPSTOX_ACCESS_TOKEN not found in ~/tradingbridge/.token.env "
        "or environment variable UPSTOX_ACCESS_TOKEN"
    )
_token_cache["token"] = UPSTOX_ACCESS_TOKEN
try:
    _token_cache["mtime"] = os.path.getmtime(_token_file)
except Exception:
    pass

# Confidence Scoring & Arming
MIN_CONFIDENCE_THRESHOLD = 50
CONFIDENCE_CHECK_INTERVAL = 60
ENABLE_SMART_ENTRY = False
ENTRY_TOLERANCE_PCT = 0.0025  # 0.25%

# COMEX Data (Yahoo Finance)
COMEX_DATA_URL = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1d&range=5d"
COMEX_DATA_URL_LONG = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1d&range=100d"
COMEX_MONITOR_INTERVAL = 30  # seconds

# Guardian Settings (Crash Protection)
GUARDIAN_ENABLED = False           # Set to False to temporarily disable Guardian checks
GUARDIAN_CHECK_INTERVAL = 60      # Seconds (1 minute)
GUARDIAN_CRASH_DROP_PCT = 0.008   # 0.8% drop/spike threshold
GUARDIAN_LOOKBACK_MINUTES = 5     # Time window for crash detection

# Currency Data (USDINR)
USD_INR_URL = "https://query1.finance.yahoo.com/v8/finance/chart/INR=X?interval=1d&range=30d"



# Trading Settings
ENABLE_GTT = True # Set to True for LIVE TRADING. False for Dry Run (Logs only). 
ENABLE_COMEX_FILTER = False   # Set to True to enable international momentum check
ENABLE_MCX_CONFIRMATION = False # Set to True to enable MCX Hourly Close & Momentum checks
MARKET_START_TIME = "09:00:00" # HH:MM:SS format (IST)
GTT_PLACEMENT_CUTOFF_TIME = "23:30" # HH:MM format (IST). Stop monitoring/placing orders after this time.
TOTAL_LOTS = int(os.getenv("TOTAL_LOTS", "1"))
ENABLE_PAPER_TRADING = os.getenv("ENABLE_PAPER_TRADING", "true").lower() == "true"
INITIAL_PAPER_CAPITAL = float(os.getenv("INITIAL_PAPER_CAPITAL", "100000.0"))

# Strategy Settings (4H Breakout)
STRATEGY_MODE = "GTT_SESSION_BREAKOUT"
SESSIONS = ["09:00", "13:00", "17:00", "21:00"]
SESSION_END_TIME = "23:30"
ENTRY_BUFFER_PCT = 0.0020  # 0.20%
SL_BUFFER_PCT = 0.0015     # 0.15%
TARGET_RISK_REWARD_RATIO = 1.5 # Target = Entry + (Entry - SL) * 1.5

# Advanced SL/Target Formulas
FIXED_SL_PCT = 0.015       # 1.5% Fixed SL from Entry
FIXED_TARGET_PCT = 0.015   # 1.5% Fixed Target from Entry
LL_BUFFER_PCT = 0.0015     # 0.15% Buffer from Candle Low/High

# Logging & Data
LOG_FILE_PATH_MARKET = "Logs/GOLD_MARKET.log"
LOG_FILE_PATH_SESSION = "Logs/SESSION_REPORTS.log"
GTT_LOG_PATH = "Data/placed_trades_{date}.json"
