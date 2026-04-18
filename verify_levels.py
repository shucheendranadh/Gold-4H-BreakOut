import logging
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from Core.signal_engine import SignalEngine
from Core.market_data import MarketData
from config import SESSIONS

# Setup basic logging to console
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("GOLD_MARKET")

def verify():
    print("Initializing SignalEngine...")
    se = SignalEngine()
    md = MarketData()
    
    # We need the instrument token. In main.py it's fetched via search.
    # Let's try to fetch it dynamically or use a known one.
    # The logs showed "MCX_FO|472782" (e.g. GOLD 5M). 
    # Or I can use 'GOLDM FUT' logic if I import `get_instrument_token`.
    # Let's try to replicate the token fetch from main.py logic or just use the common one if possible.
    # Actually, let's use the token from the logs I saw earlier: "MCX_FO|436573" (GOLDM FEB FUT)?
    # Wait, the logs I saw in `checking_current_trade_status` mentioned specific token?
    # Let's check the logs or just use the `main.py` approach.
    
    # I'll just copy the token fetching logic from main.py (lines 50-70 approx)
    from dateutil.relativedelta import relativedelta
    from datetime import datetime
    import requests
    
    # Hardcoded from trading_state.json
    token = "MCX_FO|472784"
    print(f"Using Instrument Token: {token}")

    print(f"\n--- Verifying Levels for {token} ---")
    
    # Testing Session Logging via Restorative Plan
    print("\n--- Testing Session Logging (Restorative Plan) ---")
    plan, meta = se.generate_restorative_plan(token)
    
    if plan:
        print("Plan Generated successfully (Check logs for 'System Start (Restorative)' report).")
    else:
        print("No Plan generated (might be out of hours or data missing).")

if __name__ == "__main__":
    verify()
