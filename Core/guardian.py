import logging
import time
import sys
from collections import deque
from datetime import datetime
from config import (
    GUARDIAN_CHECK_INTERVAL,
    GUARDIAN_CRASH_DROP_PCT,
    GUARDIAN_LOOKBACK_MINUTES
)
from Core.state_manager import StateManager
from Core.order_manager import OrderManager
from Core.gtt_manager import GTTManager
from Core.signal_engine import SignalEngine
from Core.cancel_gtts import CancelGTTs
from DataLoader.historical_data_loader import HistoricalDataFetcher

# Configure Logger for Guardian
guardian_logger = logging.getLogger("GOLD_GUARDIAN")

class Guardian:
    def __init__(self):
        self.sm = StateManager()
        self.om = OrderManager()
        self.gtt_manager = GTTManager()
        self.signal_engine = SignalEngine()
        self.cancel_gtts_tool = CancelGTTs()
        self.fetcher = HistoricalDataFetcher()
        # maxlen caps memory if pruning ever lags; LOOKBACK*60 = max 1 entry/sec
        self.price_history = deque(maxlen=GUARDIAN_LOOKBACK_MINUTES * 60)

    def measure_crash_metrics(self, current_price, triggered_side):
        """
        Analyzes price history to detect a crash relative to the active side.
        Returns: (is_crash, magnitude_pct)
        """
        now = datetime.now()
        self.price_history.append((now, current_price))

        # Prune Old Prices
        cutoff_time = now.timestamp() - (GUARDIAN_LOOKBACK_MINUTES * 60)
        while self.price_history and self.price_history[0][0].timestamp() < cutoff_time:
            self.price_history.popleft()

        if len(self.price_history) < 2:
            return False, 0.0

        # Oldest price in window
        oldest_price = self.price_history[0][1]
        
        # Calculate Percentage Change
        drop_pct = (oldest_price - current_price) / oldest_price
        rise_pct = (current_price - oldest_price) / oldest_price
        
        # Detection Logic specific to Triggered Side
        # If we are LONG (BUY), a DROP is bad.
        # If we are SHORT (SELL), a RISE is bad.
        
        if triggered_side == "BUY":
            if drop_pct >= GUARDIAN_CRASH_DROP_PCT:
                return True, drop_pct * 100
        elif triggered_side == "SELL":
            if rise_pct >= GUARDIAN_CRASH_DROP_PCT:
                 return True, rise_pct * 100
                 
        return False, 0.0

    def check_for_crash(self, instrument_token):
        """
        Main check method called by main.py.
        """
        # 1. Load State to see if we are active
        state = self.sm.load_state()
        if not state:
            return False
            
        triggered_side = state.get("triggered_side")
        instrument = state.get("instrument")
        
        if not triggered_side or not instrument:
            # No active trade to guard
            return False

        if instrument != instrument_token:
            # Contract roll: state has expired contract, active contract is new.
            # Update state and re-engage guard on next cycle.
            guardian_logger.warning(f"Guardian: Instrument mismatch — state has {instrument}, active is {instrument_token}. Updating state instrument.")
            state["instrument"] = instrument_token
            self.sm.save_state(state)
            instrument = instrument_token
            
        # 2. Fetch Price
        ltp = self.fetcher.fetch_ltp(instrument)
        if ltp is None:
            guardian_logger.warning("Guardian: Failed to fetch LTP.")
            return False
            
        # 3. Measure
        is_crash, mag = self.measure_crash_metrics(ltp, triggered_side)
        
        if is_crash:
            guardian_logger.critical(f"GUARD CRASH DETECTED! Side: {triggered_side}, Magnitude: {mag:.2f}%")
            self.execute_panic_protocol(instrument, ltp)
            return True
            
        return False

    def execute_panic_protocol(self, instrument, current_ltp):
        """
        Step 1: Cancel All GTTs
        Step 2: Exit Position (Limit Chase)
        Step 3: Restore System (New GTTs)
        """
        guardian_logger.info(">>> INITIATING PANIC PROTOCOL <<<")
        
        # --- Step 1: Cancel GTTs ---
        guardian_logger.info("[Step 1] Cancelling All GTTs...")
        self.cancel_gtts_tool.cancel_stored_gtts()
        
        # --- Step 2: Exit Position (Limit Chase) ---
        guardian_logger.info(f"[Step 2] Exiting Position via Limit Chase. Initial LTP: {current_ltp}")
        
        net_qty = self.om.get_net_position_qty(instrument)
        if net_qty == 0:
            guardian_logger.info("Net Qty is 0. No position to exit.")
        else:
            self._run_chase_loop(instrument, net_qty, current_ltp)
            
        # --- Step 3: Clear State completely ---
        guardian_logger.info("[Step 3] Clearing Trading State.")
        self.sm.save_state({}) # Clear triggers
        
        # --- Step 4: Restore System ---
        guardian_logger.info("[Step 4] Restoration: Generating new GTT Plan based on last 4H session.")
        restorative_plan, _ = self.signal_engine.generate_restorative_plan(instrument)
        
        if restorative_plan:
            guardian_logger.info("Placing Restorative GTTs...")
            # We assume "Restoration" is the session name
            self.gtt_manager.place_gtts(instrument, restorative_plan, "Restoration")
        else:
            guardian_logger.error("Failed to generate restorative plan. Manual intervention required.")

        guardian_logger.info(">>> PANIC PROTOCOL COMPLETE <<<")

    def _run_chase_loop(self, instrument, initial_qty, initial_price):
        """
        Places Limit Order. Monitors every 30s. If not filled, cancels & replaces at NEW LTP.
        """
        qty = abs(initial_qty)
        transaction_type = "SELL" if initial_qty > 0 else "BUY"
        current_limit_price = initial_price
        
        # Place Initial Order
        current_order_id = self.om.place_order(
            instrument_token=instrument,
            transaction_type=transaction_type,
            quantity=qty,
            order_type="LIMIT",
            price=current_limit_price
        )
        
        if not current_order_id:
            guardian_logger.critical("Failed to place Initial Panic Limit Order!")
            return # What else can we do? Retry loop?
            
        # Chase Loop
        while True:
            guardian_logger.info(f"Monitor: Waiting 30s for Limit Fill (Qty: {qty} @ {current_limit_price})...")
            time.sleep(30)
            
            # Check Position
            current_net_qty = self.om.get_net_position_qty(instrument)
            if current_net_qty == 0:
                guardian_logger.info("Position Closed. Chase complete.")
                break
                
            # If Qty changed (partial fill), update tracking
            # But Upstox place_order qty is fixed. if partial fill, we need remaining.
            remaining_qty = abs(current_net_qty)
            
            guardian_logger.warning(f"Position Still Open ({current_net_qty}). Updating Order...")
            
            # Fetch New LTP
            new_ltp = self.fetcher.fetch_ltp(instrument)
            if not new_ltp:
                continue

            # Cancel Old
            self.om.cancel_order(current_order_id)
            
            # Place New
            current_limit_price = new_ltp
            current_order_id = self.om.place_order(
                 instrument_token=instrument,
                 transaction_type=transaction_type,
                 quantity=remaining_qty,
                 order_type="LIMIT",
                 price=current_limit_price
            )
            
            if not current_order_id:
                guardian_logger.error("Failed to place Replacement Order in Chase Loop.")
