
import streamlit as st
import json
import os
import pandas as pd
import time
from datetime import datetime
from Core.market_data import MarketData
from Core.instrument_manager import InstrumentManager

# Set Page Config
st.set_page_config(page_title="Gold 4H Breakout Dashboard", layout="wide")

# Custom CSS for Premium Look
st.markdown("""
    <style>
    .main {
        background-color: #0e1117;
    }
    .metric-card {
        background-color: #1e2130;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.5);
    }
    .stMetric {
        background-color: #1e2126;
        padding: 15px;
        border-radius: 8px;
    }
    </style>
""", unsafe_allow_html=True)

# Helper to load JSON safely
def load_json(path, default=[]):
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception:
            return default
    return default

# Data Paths
STATE_PATH = "Data/trading_state.json"
PNL_PATH = "Data/paper_pnl.json"
ORDERS_PATH = "Data/paper_orders.json"
SESSION_PATH = "Data/session_levels.json"

def main():
    st.title("🏆 Gold 4H Breakout Strategy Dashboard")
    
    # Auto-refresh check
    refresh_rate = st.sidebar.slider("Refresh Interval (seconds)", 5, 60, 10)
    
    # --- Current Market Info ---
    im = InstrumentManager()
    md = MarketData()
    
    # Load State
    state = load_json(STATE_PATH, {})
    active_contract = state.get("instrument")
    
    if not active_contract:
        # Fallback if no state
        # In actual live trading, you might want to fetch the current active contract
        active_contract = "MCX_FO|477176" # Placeholder or dynamic fetch

    # Fetch LTP
    ltp = md.fetcher.fetch_ltp(active_contract)
    
    # Display Status Header
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("LTP (Gold)", f"{ltp if ltp else 'N/A'}")
    with col2:
        status = "Active Session" if ltp else "Exchange Closed / No Token"
        st.metric("System Status", status)
    with col3:
        st.metric("Active Trade", state.get("triggered_side", "NONE"))
    with col4:
        st.metric("Last Updated", state.get("last_updated", "N/A"))

    # --- P&L Section ---
    st.header("📈 Performance & P&L")
    pnl_data = load_json(PNL_PATH, {"initial_capital": 100000, "realized_pnl": 0, "current_balance": 100000})
    
    # Calculate Unrealized
    orders = load_json(ORDERS_PATH, [])
    active_orders = [o for o in orders if o.get("status") == "ACTIVE"]
    unrealized_pnl = 0
    if ltp:
        for order in active_orders:
            side = order.get("side")
            entry = order.get("entry_price")
            qty = order.get("qty", 1)
            if side == "BUY":
                unrealized_pnl += (ltp - entry) * qty
            else:
                unrealized_pnl += (entry - ltp) * qty
    
    realized_pnl = pnl_data.get("realized_pnl", 0)
    total_pnl = realized_pnl + unrealized_pnl
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Initial Capital", f"₹{pnl_data['initial_capital']:,}")
    c2.metric("Realized P&L", f"₹{realized_pnl:,}", delta=f"{realized_pnl}", delta_color="normal")
    c3.metric("Unrealized P&L", f"₹{unrealized_pnl:,.2f}", delta=f"{unrealized_pnl:.2f}")
    c4.metric("Total P&L", f"₹{total_pnl:,.2f}", delta=f"{(total_pnl/pnl_data['initial_capital']*100):.2f}% (ROI)")

    # --- Active Position & GTTs ---
    col_pos, col_gtt = st.columns([1, 1])
    
    with col_pos:
        st.subheader("📍 Running Position")
        if state.get("triggered_side"):
            pos_info = {
                "Instrument": active_contract,
                "Side": state["triggered_side"],
                "Entry Price": state.get("entry_price"),
                "Current Price": ltp,
                "Last Sync": state.get("last_updated")
            }
            st.json(pos_info)
        else:
            st.info("No active trade currently running.")

    with col_gtt:
        st.subheader("🛡️ Active GTT Monitoring")
        if state.get("gtts"):
            gtt_table = []
            for side, types in state["gtts"].items():
                for t, g_id in types.items():
                    if g_id:
                        gtt_table.append({"Side": side, "Type": t, "GTT ID": g_id})
            if gtt_table:
                st.table(pd.DataFrame(gtt_table))
            else:
                st.write("No GTTs placed.")
        else:
            st.write("No GTTs in state.")

    # --- Session History ---
    st.header("🕒 Session Levels History")
    sessions = load_json(SESSION_PATH, [])
    if sessions:
        # Show last 10 sessions in a table
        session_df = []
        for s in reversed(sessions[-10:]):
            session_df.append({
                "Timestamp": s.get("timestamp"),
                "Session": s.get("session"),
                "High": s.get("high"),
                "Low": s.get("low"),
                "Buy Entry": s.get("plan", {}).get("BUY", {}).get("entry"),
                "Sell Entry": s.get("plan", {}).get("SELL", {}).get("entry")
            })
        st.dataframe(pd.DataFrame(session_df), use_container_width=True)
    else:
        st.write("No session levels recorded yet.")

    # --- Recent Paper Orders ---
    st.header("📜 Recent Trade History")
    if orders:
        order_df = pd.DataFrame(orders).tail(10)
        # Select key columns
        cols = ["id", "side", "status", "entry_price", "exit_price", "pnl", "closed_at", "exit_reason"]
        available_cols = [c for c in cols if c in order_df.columns]
        st.dataframe(order_df[available_cols].sort_index(ascending=False), use_container_width=True)

    # Footer
    st.markdown("---")
    st.caption(f"Last UI Refresh: {datetime.now().strftime('%H:%M:%S')}")

    # Re-run after interval
    time.sleep(refresh_rate)
    st.rerun()

if __name__ == "__main__":
    main()
