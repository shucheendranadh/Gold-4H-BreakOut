
import json
import logging
from datetime import datetime
from Core.market_data import MarketData
from Core.instrument_manager import InstrumentManager

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VERIFY_STATUS")

def verify_status():
    print("\n=== GOLD 4H BREAKOUT SYSTEM STATUS ===\n")
    
    # 1. Load Strategy State
    state_path = "Data/trading_state.json"
    try:
        with open(state_path, 'r') as f:
            state = json.load(f)
    except FileNotFoundError:
        print("No trading state found. Is the bot running?")
        return

    # 2. Get Active Contract and LTP
    im = InstrumentManager()
    active_contract = state.get("instrument")
    if not active_contract:
        active_contract = im.get_active_contract()
    
    if not active_contract:
        print("Could not determine active contract.")
        return
    
    md = MarketData()
    ltp = md.fetcher.fetch_ltp(active_contract)
    
    print(f"Active Contract: {active_contract}")
    print(f"Current Market Price (LTP): {ltp}")
    print(f"Last State Update: {state.get('last_updated')}")
    print(f"Triggered Side: {state.get('triggered_side')}")
    
    # 3. Analyze Open Paper Trades
    orders_path = "Data/paper_orders.json"
    try:
        with open(orders_path, 'r') as f:
            orders = json.load(f)
    except FileNotFoundError:
        orders = []

    active_orders = [o for o in orders if o.get("status") == "ACTIVE"]
    
    print(f"\n--- Open Paper Trades ({len(active_orders)}) ---")
    
    total_unrealized_pnl = 0
    for order in active_orders:
        entry = order.get("entry_price")
        side = order.get("side")
        qty = order.get("qty", 1)
        
        if ltp:
            if side == "BUY":
                unrealized = (ltp - entry) * qty
            else:
                unrealized = (entry - ltp) * qty
            
            total_unrealized_pnl += unrealized
            print(f"ID: {order['id']} | Side: {side} | Entry: {entry} | Current: {ltp} | P&L: {unrealized:.2f}")
    
    print(f"\nTotal Unrealized P&L: {total_unrealized_pnl:.2f}")

    # 4. Load Realized P&L
    pnl_path = "Data/paper_pnl.json"
    try:
        with open(pnl_path, 'r') as f:
            pnl_data = json.load(f)
            realized_pnl = pnl_data.get("realized_pnl", 0)
            initial_capital = pnl_data.get("initial_capital", 100000)
            current_balance = pnl_data.get("current_balance", initial_capital)
            
            print(f"\n--- Performance Summary ---")
            print(f"Initial Capital: {initial_capital}")
            print(f"Realized P&L: {realized_pnl}")
            print(f"Total P&L (Realized + Unrealized): {realized_pnl + total_unrealized_pnl:.2f}")
            print(f"Overall ROI: {((realized_pnl + total_unrealized_pnl) / initial_capital * 100):.2f}%")
            
    except FileNotFoundError:
        print("\nNo paper P&L data found.")

if __name__ == "__main__":
    verify_status()
