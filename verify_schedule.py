
import sys
import os
import logging
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from Core.signal_engine import SignalEngine

# Configure logging to console
logging.basicConfig(level=logging.INFO)

def verify_schedule_logic():
    se = SignalEngine()
    
    # 1. Simulate State from User's File (Early Morning Update)
    # 08:22 is BEFORE 09:00 Start Time
    state = {
        "instrument": "MCX_FO|472784",
        "last_updated": "2026-02-11 08:22:18", 
        "triggered_side": "SELL",
        "entry_price": 157684.0
    }
    
    token = "MCX_FO|472784"
    
    print("\n--- Verifying Check Schedule Logic ---")
    print(f"Current Time: {datetime.now()}")
    print(f"Simulated State Last Update: {state['last_updated']}")
    
    # Call check_schedule
    # Expected: Should trigger 'Session 1 (Start)' because 08:22 < 09:00
    actions = se.check_schedule(token, state=state)
    
    print(f"\nResulting Actions ({len(actions)}):")
    for act in actions:
        print(f" - Event: {act.get('event', act.get('action'))}")
        if 'session_name' in act:
            print(f"   Session Name: {act['session_name']}")
    
    
    if len(actions) > 0:
        print("\n[SUCCESS] Logic triggered actions. Check Logs/SESSION_REPORTS.log for formatting.")
    else:
        print("\n[FAILURE] Logic did NOT trigger actions.")

    # 2. Simulate NO Active Trade (Fresh Start)
    print("\n--- Verifying Schedule (Fresh Start - No Trade) ---")
    state_fresh = {
        "instrument": "MCX_FO|472784",
        "last_updated": "2026-02-11 08:22:18", 
        "triggered_side": None, # No active trade
        "entry_price": None
    }
    actions_fresh = se.check_schedule(token, state=state_fresh)
    print(f"Resulting Actions (Fresh): {len(actions_fresh)}")

if __name__ == "__main__":
    verify_schedule_logic()
