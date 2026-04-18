"""
exit_and_reset.py
-----------------
Closes the active Lot 2 paper position at current LTP,
records P&L, cancels all remaining GTTs, and clears
trading state so the bot is clean for the next session (21:00).

Run ONCE manually: python exit_and_reset.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Core.paper_exchange import PaperExchange
from Core.state_manager import StateManager
from DataLoader.historical_data_loader import HistoricalDataFetcher
from Core.cancel_gtts import CancelGTTs
from datetime import datetime

def main():
    sm = StateManager()
    pe = PaperExchange()
    cancel_tool = CancelGTTs()

    # --- 1. Load current state ---
    state = sm.load_state()
    if not state:
        print("No active state found. Nothing to exit.")
        return

    triggered_side = state.get("triggered_side")
    entry_price    = state.get("entry_price")
    instrument     = state.get("instrument")

    if not triggered_side:
        print("No triggered trade in state. Nothing to exit.")
        return

    print(f"\n{'='*55}")
    print(f"  Current Position: {triggered_side} @ {entry_price}")
    print(f"  Instrument      : {instrument}")
    print(f"{'='*55}")

    # --- 2. Fetch current LTP ---
    fetcher = HistoricalDataFetcher()
    ltp = fetcher.fetch_ltp(instrument)
    if not ltp:
        print("ERROR: Could not fetch LTP. Exiting without closing position.")
        return

    print(f"  Current LTP     : {ltp}")

    # --- 3. Close the active Lot 2 paper order at LTP ---
    orders = pe._load_orders()
    lot2_id = state.get("gtts", {}).get(triggered_side, {}).get("SINGLE")
    closed = False

    for order in orders:
        if order.get("status") == "ACTIVE" and order.get("side") == triggered_side:
            pnl = (ltp - order["entry_price"]) if triggered_side == "BUY" \
                  else (order["entry_price"] - ltp)
            pnl = round(pnl * order["qty"], 2)

            print(f"\n  Closing: {order['id']}")
            print(f"  Entry  : {order['entry_price']}  ->  Exit: {ltp}")
            print(f"  P&L    : {'+'if pnl>=0 else ''}{pnl}")

            pe._close_order(order, ltp, "MANUAL_EXIT")
            closed = True

    if closed:
        pe._save_orders(orders)
        print("\n  [OK] Lot 2 closed successfully.")
    else:
        print("\n  [WARN] No ACTIVE paper order found for Lot 2 -- may already be closed.")

    # --- 4. Cancel all remaining GTTs (pending SELL side, etc.) ---
    print("\n  Cancelling remaining GTTs...")
    cancel_tool.cancel_stored_gtts()

    # --- 5. Clear trading state ---
    sm.save_state({})
    print("  [OK] Trading state cleared.")

    # --- 6. Summary ---
    pnl_data = pe._load_pnl()
    print(f"\n{'='*55}")
    print(f"  READY FOR NEXT SESSION (21:00)")
    print(f"  Total Realized P&L : Rs.{pnl_data.get('realized_pnl', 0):,.2f}")
    print(f"  Current Balance    : Rs.{pnl_data.get('current_balance', 0):,.2f}")
    print(f"  State              : CLEAN -- bot will place fresh GTTs at 21:00")
    print(f"{'='*55}\n")

if __name__ == "__main__":
    main()
