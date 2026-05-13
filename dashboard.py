import streamlit as st
import json
import os
import time
import subprocess
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="Gold 4H Breakout",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: 1.4rem; }
.log-box {
    background: #0d1117;
    color: #c9d1d9;
    font-family: monospace;
    font-size: 0.78rem;
    padding: 12px;
    border-radius: 6px;
    height: 420px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-all;
}
.status-pill-active  { background:#1a4731; color:#3fb950; padding:3px 10px; border-radius:12px; font-weight:600; }
.status-pill-none    { background:#21262d; color:#8b949e; padding:3px 10px; border-radius:12px; }
.status-pill-pending { background:#3d2b00; color:#e3b341; padding:3px 10px; border-radius:12px; }
</style>
""", unsafe_allow_html=True)

# ── Paths ────────────────────────────────────────────────────────────────────
STATE_PATH   = "Data/trading_state.json"
PNL_PATH     = "Data/paper_pnl.json"
ORDERS_PATH  = "Data/paper_orders.json"
SESSION_PATH = "Data/session_levels.json"
LOG_MARKET   = "Logs/GOLD_MARKET.log"
LOG_SESSION  = "Logs/SESSION_REPORTS.log"
LOG_CONSOLE  = "Logs/console_output.log"
LOG_STARTUP  = "Logs/startup_log.txt"

# ── Helpers ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=10)
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return default

@st.cache_data(ttl=10)
def read_log(path, lines=300):
    if not os.path.exists(path):
        return f"[File not found: {path}]"
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
        return "".join(all_lines[-lines:])
    except Exception as e:
        return f"[Error reading log: {e}]"

def pnl_color(val):
    if val > 0: return "green"
    if val < 0: return "red"
    return "grey"

def fmt_inr(val):
    return f"₹{val:,.2f}"

def get_service_status():
    try:
        r = subprocess.run(
            ["systemctl", "is-active", "gold-4h-breakout.service"],
            capture_output=True, text=True, timeout=3
        )
        return r.stdout.strip()
    except Exception:
        return "unknown"

def restart_service():
    try:
        r = subprocess.run(
            ["sudo", "systemctl", "restart", "gold-4h-breakout.service"],
            capture_output=True, text=True, timeout=15
        )
        return r.returncode == 0, r.stderr.strip() or "Restarted successfully."
    except Exception as e:
        return False, str(e)

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🏆 Gold 4H Bot")
    st.caption("Live Dashboard")
    st.divider()

    # Service status
    svc_status = get_service_status()
    if svc_status == "active":
        st.markdown('<span class="status-pill-active">● Service Running</span>', unsafe_allow_html=True)
    else:
        st.markdown(f'<span class="status-pill-pending">● Service {svc_status}</span>', unsafe_allow_html=True)

    st.divider()

    # Restart button with confirmation
    if "confirm_restart" not in st.session_state:
        st.session_state.confirm_restart = False

    if not st.session_state.confirm_restart:
        if st.button("🔁 Restart Bot Service", use_container_width=True):
            st.session_state.confirm_restart = True
            st.rerun()
    else:
        st.warning("Restart the bot service?")
        col_y, col_n = st.columns(2)
        if col_y.button("✅ Yes", use_container_width=True):
            with st.spinner("Restarting..."):
                ok, msg = restart_service()
                time.sleep(2)
            st.session_state.confirm_restart = False
            if ok:
                st.success("Service restarted.")
            else:
                st.error(f"Failed: {msg}")
        if col_n.button("❌ No", use_container_width=True):
            st.session_state.confirm_restart = False
            st.rerun()

    st.divider()
    refresh = st.slider("Auto-refresh (sec)", 5, 120, 15)
    log_lines = st.slider("Log lines to show", 50, 500, 200, step=50)
    st.divider()
    if st.button("🔄 Refresh Now"):
        st.rerun()
    st.caption(f"Last loaded: {datetime.now().strftime('%H:%M:%S')}")

# ── Load data ────────────────────────────────────────────────────────────────
state   = load_json(STATE_PATH,   {})
pnl     = load_json(PNL_PATH,     {"initial_capital": 100000, "current_balance": 100000, "realized_pnl": 0, "trades": []})
orders  = load_json(ORDERS_PATH,  [])
sessions = load_json(SESSION_PATH, [])

# ── Header status bar ────────────────────────────────────────────────────────
st.title("Gold 4H Breakout — Dashboard")

triggered_side = state.get("triggered_side") or "NONE"
entry_price    = state.get("entry_price", "—")
instrument     = state.get("instrument", "—")
last_updated   = state.get("last_updated", "—")
triggered_at   = state.get("triggered_at", "—")
paper_mode     = state.get("paper_mode", True)

col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("Mode",         "📄 Paper" if paper_mode else "🔴 Live")
col2.metric("Active Trade", triggered_side)
col3.metric("Entry Price",  f"₹{entry_price}" if isinstance(entry_price, (int, float)) else entry_price)
col4.metric("Triggered At", triggered_at)
col5.metric("Instrument",   instrument)
col6.metric("Last Updated", last_updated)

st.divider()

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab_pnl, tab_orders, tab_state, tab_sessions, tab_mktlog, tab_seslog, tab_console, tab_startup = st.tabs([
    "📈 P&L",
    "📋 Orders",
    "⚙️ Trading State",
    "🕒 Session Levels",
    "📜 Market Log",
    "📊 Session Reports",
    "🖥️ Console",
    "🚀 Startup Log",
])

# ═══════════════════════════════════════════════════════════════
# TAB 1 — P&L
# ═══════════════════════════════════════════════════════════════
with tab_pnl:
    initial  = pnl.get("initial_capital", 100000)
    realized = pnl.get("realized_pnl", 0.0)
    balance  = pnl.get("current_balance", initial)
    trades   = pnl.get("trades", [])
    roi      = (realized / initial * 100) if initial else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Initial Capital",  fmt_inr(initial))
    c2.metric("Current Balance",  fmt_inr(balance),  delta=fmt_inr(balance - initial))
    c3.metric("Realized P&L",     fmt_inr(realized), delta=f"{roi:.2f}% ROI")
    c4.metric("Closed Trades",    len(trades))

    st.divider()

    if trades:
        df_trades = pd.DataFrame(trades)
        df_trades["date"] = pd.to_datetime(df_trades["date"], errors="coerce")
        df_trades = df_trades.sort_values("date", ascending=False)

        # Cumulative P&L chart
        df_chart = df_trades.sort_values("date").copy()
        df_chart["cumulative_pnl"] = df_chart["pnl"].cumsum()
        st.subheader("Cumulative P&L")
        st.line_chart(df_chart.set_index("date")["cumulative_pnl"])

        st.subheader("Trade History")
        st.dataframe(
            df_trades[["id", "side", "pnl", "reason", "date"]].rename(columns={
                "id": "Order ID", "side": "Side", "pnl": "P&L (₹)",
                "reason": "Exit Reason", "date": "Closed At"
            }),
            use_container_width=True,
        )
    else:
        st.info("No closed trades yet.")

# ═══════════════════════════════════════════════════════════════
# TAB 2 — Orders
# ═══════════════════════════════════════════════════════════════
with tab_orders:
    if orders:
        df_orders = pd.DataFrame(orders)

        # Status filter
        statuses = ["ALL"] + sorted(df_orders["status"].unique().tolist())
        sel = st.selectbox("Filter by Status", statuses)
        if sel != "ALL":
            df_orders = df_orders[df_orders["status"] == sel]

        # Column selection
        cols_want = ["id", "side", "status", "entry_price", "sl_price", "target_price",
                     "qty", "placed_at", "filled_at", "closed_at", "exit_reason", "exit_price", "pnl"]
        cols_avail = [c for c in cols_want if c in df_orders.columns]

        st.dataframe(
            df_orders[cols_avail].sort_values("placed_at", ascending=False)
            .rename(columns={
                "id": "Order ID", "side": "Side", "status": "Status",
                "entry_price": "Entry", "sl_price": "SL", "target_price": "Target",
                "qty": "Qty", "placed_at": "Placed", "filled_at": "Filled",
                "closed_at": "Closed", "exit_reason": "Exit Reason",
                "exit_price": "Exit Price", "pnl": "P&L (₹)"
            }),
            use_container_width=True,
        )

        # Summary counts
        s_counts = df_orders["status"].value_counts()
        cc = st.columns(len(s_counts))
        for i, (s, n) in enumerate(s_counts.items()):
            cc[i].metric(s, n)
    else:
        st.info("No orders found.")

# ═══════════════════════════════════════════════════════════════
# TAB 3 — Trading State
# ═══════════════════════════════════════════════════════════════
with tab_state:
    if state:
        # Key fields as metrics
        st.subheader("Key State")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Triggered Side",  state.get("triggered_side", "NONE"))
        k2.metric("Entry Price",     state.get("entry_price", "—"))
        k3.metric("Triggered At",    state.get("triggered_at", "—"))
        k4.metric("Instrument",      state.get("instrument", "—"))

        k5, k6, k7, k8 = st.columns(4)
        k5.metric("Strategy Mode",   state.get("strategy_mode", "—"))
        k6.metric("Session",         state.get("current_session", "—"))
        k7.metric("Paper Mode",      str(state.get("paper_mode", "—")))
        current_sl = state.get("current_sl")
        k8.metric("Current TSL",     f"₹{current_sl:,.0f}" if isinstance(current_sl, (int, float)) else "—")

        # GTT Table
        gtts = state.get("gtts")
        if gtts:
            st.subheader("GTT Orders in State")
            gtt_rows = []
            for side, types in gtts.items():
                if isinstance(types, dict):
                    for t, gid in types.items():
                        gtt_rows.append({"Side": side, "Type": t, "GTT ID": gid or "—"})
            if gtt_rows:
                st.table(pd.DataFrame(gtt_rows))

        st.subheader("Raw State JSON")
        st.json(state)
    else:
        st.info("Trading state is empty — bot may not have run yet.")

# ═══════════════════════════════════════════════════════════════
# TAB 4 — Session Levels
# ═══════════════════════════════════════════════════════════════
with tab_sessions:
    if sessions:
        st.subheader(f"Last {min(len(sessions), 20)} Sessions")

        rows = []
        for s in reversed(sessions[-20:]):
            plan = s.get("plan", {})
            buy  = plan.get("BUY", {})
            sell = plan.get("SELL", {})
            rows.append({
                "Timestamp":   s.get("timestamp"),
                "Session":     s.get("session"),
                "High":        s.get("high"),
                "Low":         s.get("low"),
                "BUY Entry":   buy.get("entry"),
                "BUY SL":      buy.get("sl_1"),
                "BUY Target":  buy.get("target_1"),
                "SELL Entry":  sell.get("entry"),
                "SELL SL":     sell.get("sl_1"),
                "SELL Target": sell.get("target_1"),
            })

        st.dataframe(pd.DataFrame(rows), use_container_width=True)

        # Latest session detail
        with st.expander("Latest Session Full JSON"):
            st.json(sessions[-1])
    else:
        st.info("No session levels recorded yet.")

# ═══════════════════════════════════════════════════════════════
# TAB 5 — Gold Market Log
# ═══════════════════════════════════════════════════════════════
with tab_mktlog:
    st.subheader("GOLD_MARKET.log")
    content = read_log(LOG_MARKET, log_lines)
    st.markdown(f'<div class="log-box">{content}</div>', unsafe_allow_html=True)
    with st.expander("Download log"):
        st.download_button("⬇ Download", content, file_name="GOLD_MARKET.log")

# ═══════════════════════════════════════════════════════════════
# TAB 6 — Session Reports Log
# ═══════════════════════════════════════════════════════════════
with tab_seslog:
    st.subheader("SESSION_REPORTS.log")
    content = read_log(LOG_SESSION, log_lines)
    st.markdown(f'<div class="log-box">{content}</div>', unsafe_allow_html=True)
    with st.expander("Download log"):
        st.download_button("⬇ Download", content, file_name="SESSION_REPORTS.log")

# ═══════════════════════════════════════════════════════════════
# TAB 7 — Console Output
# ═══════════════════════════════════════════════════════════════
with tab_console:
    st.subheader("console_output.log")
    content = read_log(LOG_CONSOLE, log_lines)
    st.markdown(f'<div class="log-box">{content}</div>', unsafe_allow_html=True)
    with st.expander("Download log"):
        st.download_button("⬇ Download", content, file_name="console_output.log")

# ═══════════════════════════════════════════════════════════════
# TAB 8 — Startup Log
# ═══════════════════════════════════════════════════════════════
with tab_startup:
    st.subheader("startup_log.txt")
    content = read_log(LOG_STARTUP, log_lines)
    st.markdown(f'<div class="log-box">{content}</div>', unsafe_allow_html=True)
    with st.expander("Download log"):
        st.download_button("⬇ Download", content, file_name="startup_log.txt")

# ── Auto-refresh ─────────────────────────────────────────────────────────────
time.sleep(refresh)
st.rerun()
