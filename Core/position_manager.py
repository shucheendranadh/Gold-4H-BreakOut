import logging
import json
from datetime import datetime
from Core.order_manager import OrderManager
from DataLoader.historical_data_loader import HistoricalDataFetcher
from Core.state_manager import StateManager

logger = logging.getLogger("GOLD_MARKET")

class PositionManager:
    def __init__(self):
        self.om = OrderManager()
        self.fetcher = HistoricalDataFetcher()
        self.sm = StateManager()

    @staticmethod
    def mround(number, base):
        """Excel-like MROUND function."""
        if base == 0: return 0
        return int(round(number / base) * base)

    def cleanup_stale_state(self, state):
        """
        Checks for stale state (from previous sessions).
        If found, checks for active triggers.
        - If active trigger found: Updates state to current day and returns True (Active).
        - If no trigger: Cancels all stale GTTs, clears state, and returns False (Clean).
        - If state is already fresh: Returns True (Active/Fresh).
        """
        if not state:
            return False

        triggered_side = state.get("triggered_side")

        # Check if state is from TODAY
        last_updated = state.get("last_updated", "")
        if last_updated:
            try:
                state_date = datetime.strptime(last_updated, "%Y-%m-%d %H:%M:%S").date()
                if state_date == datetime.now().date():
                    # State is from today, so it's fresh. Do not clean up.
                    return True
            except ValueError:
                pass

        # Always check for triggers, regardless of the day
        if not triggered_side:
            logger.info("State is stale or from previous day. Checking for triggers...")
            gtts = state.get("gtts", {})
            recovered_side = self._check_for_external_triggers(gtts)
            
            if recovered_side:
                side, entry_price = recovered_side
                logger.info(f"Recovered triggered side: {side}, Entry: {entry_price} from previous session.")
                state["triggered_side"] = side
                state["entry_price"] = entry_price
                # Update timestamp to 'today' so it's not stale next run
                state["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.sm.save_state(state)
                return True
            else:
                logger.info("No triggers found for previous session. Cleaning up stale GTTs...")
                for side in ["BUY", "SELL"]:
                    for lot_type in ["OCO", "SINGLE"]:
                        gtt_id = gtts.get(side, {}).get(lot_type)
                        if gtt_id:
                            logger.info(f"Cancelling stale {side} {lot_type} GTT: {gtt_id}")
                            self.om.cancel_gtt_order(gtt_id)
                
                # Clear state
                self.sm.save_state({})
                logger.info("Stale state cleared. Resetting to clean slate.")
                return False
        else:
             # If stale BUT has a triggered_side (active overnight position), we just update the timestamp
             # This handles the case where the bot crashed/stopped after trigger but before next day
             logger.info(f"Stale state has active trigger ({triggered_side}). Retaining state.")
             state["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
             self.sm.save_state(state)
             return True

    def handle_daily_maintenance(self, state, active_contract=None):
        """
        Performs trigger detection, cross-side cancellation, and trailing SL updates.
        This is designed to be run ONCE daily at startup.
        Returns True if maintenance was performed (even if no SL update was needed).
        """
        # 0. Ensure State is Clean/Valid for Today
        is_active_or_fresh = self.cleanup_stale_state(state)
        
        if not is_active_or_fresh:
            # State was cleared (empty), so no maintenance to do
            return False
            
        # Refresh local var after potential cleanup updates
        triggered_side = state.get("triggered_side")
        gtts = state.get("gtts", {})

        if not triggered_side:
            logger.debug("Checking for new GTT triggers (Today)...")
            for side in ["BUY", "SELL"]:
                oco_id = gtts.get(side, {}).get("OCO")
                if oco_id:
                    details = self.om.get_gtt_order_details(oco_id)
                    # If Lot 1 is TRIGGERED, the trade has started
                    rules = details.get("rules", []) if details else []
                    entry_rule = next((r for r in rules if r.get("strategy") == "ENTRY"), None)
                    status = entry_rule.get("status") if entry_rule else None
                    
                    if status in ["TRIGGERED", "COMPLETED"]:
                        logger.info(f"Trigger detected on {side} side (GTT: {oco_id}, Status: {status}).")
                        
                        # Update state
                        triggered_side = side
                        state["triggered_side"] = side
                        # In the absence of a live entry price fetch, we use the rule trigger price
                        entry_price = next((r.get("trigger_price") for r in rules if r.get("strategy") == "ENTRY"), None)
                        state["entry_price"] = entry_price
                        state["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        # Save state before cancellation to avoid loops
                        self.sm.save_state(state)
                        break # Only one side can trigger

        # --- 2. Trailing SL Logic (If triggered) ---
        if triggered_side:
            # --- 1. Robust Opposite Side Cancellation ---
            if not state.get("opposite_cancelled", False):
                from config import ENABLE_PAPER_TRADING
                if ENABLE_PAPER_TRADING:
                    # In paper mode, triggered_side in state is sufficient — no API call needed
                    self._cancel_opposite_side_gtts(triggered_side, gtts)
                    state["opposite_cancelled"] = True
                    self.sm.save_state(state)
                else:
                    instrument = state.get("instrument")
                    if instrument and self.om.has_open_position(instrument):
                        self._cancel_opposite_side_gtts(triggered_side, gtts)
                        state["opposite_cancelled"] = True
                        self.sm.save_state(state)
                    elif not instrument:
                        logger.warning("Instrument token missing in state. Cannot verify position for opposite cancellation.")
                    else:
                        logger.info(f"Trigger detected ({triggered_side}) but Open Position not yet confirmed. Waiting before cancelling opposite side.")

            entry_price = state.get("entry_price")
            lot1_id = gtts.get(triggered_side, {}).get("OCO")
            lot2_id = gtts.get(triggered_side, {}).get("SINGLE")

            # --- Robust Entry Price Check ---
            if not entry_price:
                logger.warning(f"Entry price missing for {triggered_side} in state. Attempting to recover from GTTs...")
                # Try OCO first
                if lot1_id:
                    details = self.om.get_gtt_order_details(lot1_id)
                    if details:
                        rules = details.get("rules", [])
                        entry_price = next((r.get("trigger_price") for r in rules if r.get("strategy") == "ENTRY"), None)
                        if entry_price:
                            state["entry_price"] = entry_price
                            self.sm.save_state(state)
                            logger.info(f"Entry price recovered from OCO GTT: {entry_price}")
                
                # If OCO is None or didn't have entry price, try SINGLE
                if not entry_price and lot2_id:
                    logger.info(f"OCO unavailable, attempting to recover entry price from SINGLE GTT...")
                    details = self.om.get_gtt_order_details(lot2_id)
                    if details:
                        rules = details.get("rules", [])
                        entry_price = next((r.get("trigger_price") for r in rules if r.get("strategy") == "ENTRY"), None)
                        if entry_price:
                            state["entry_price"] = entry_price
                            self.sm.save_state(state)
                            logger.info(f"Entry price recovered from SINGLE GTT: {entry_price}")
            
            if not entry_price:
                logger.warning(f"Could not recover entry price for {triggered_side}. Cannot trail SL.")
                return True
                
            if not lot2_id:
                logger.error(f"Could not find Lot 2 GTT ID for {triggered_side}")
                return True

            # --- Session-Slot Gate ---
            # TSL should only be recalculated once per 4H session (at session close),
            # not every 5 seconds. Derive the current session slot from SESSIONS config
            # and skip if we already updated this slot.
            from config import SESSIONS
            now_dt = datetime.now()
            session_hours = sorted([int(s.split(":")[0]) for s in SESSIONS])
            current_hour = now_dt.hour
            # Find which session slot we are currently in (the last session start <= current hour)
            current_slot_hour = session_hours[0]
            for h in session_hours:
                if current_hour >= h:
                    current_slot_hour = h
            tsl_session_slot = f"{now_dt.strftime('%Y-%m-%d')}_{current_slot_hour:02d}"

            if state.get("tsl_session_slot") == tsl_session_slot:
                logger.debug(f"TSL already updated for session slot {tsl_session_slot}. Skipping.")
                return True

            # Condition: Only update if Lot 1 (OCO) has hit its TARGET
            if lot1_id:
                lot1_details = self.om.get_gtt_order_details(lot1_id)
                if lot1_details:
                    rules = lot1_details.get("rules", [])
                    target_rule = next((r for r in rules if r.get("strategy") == "TARGET"), None)
                    sl_rule = next((r for r in rules if r.get("strategy") == "STOPLOSS"), None)

                    # 1. Check if Stop Loss hit
                    if sl_rule and sl_rule.get("status") in ["TRIGGERED", "COMPLETED"]:
                        logger.info(f"Lot 1 ({lot1_id}) hit Stop Loss. Trade complete. Clearing state.")
                        self.sm.save_state({})
                        return True

                    # 2. Check if Target hit
                    if target_rule and target_rule.get("status") in ["TRIGGERED", "COMPLETED"]:
                        logger.info(f"Lot 1 ({lot1_id}) hit Target. Proceeding with Lot 2 trailing SL.")
                    else:
                        logger.info(f"Lot 1 ({lot1_id}) target not hit yet. Lot 2 maintains initial SL.")
                        # Latch the session slot so we don't re-log every 5 seconds
                        state["tsl_session_slot"] = tsl_session_slot
                        self.sm.save_state(state)
                        return True
                else:
                    # Lot 1 details missing (likely completed/expired)
                    if self.om.is_gtt_active(lot2_id):
                        logger.info(f"Lot 1 ({lot1_id}) details missing, but Lot 2 ({lot2_id}) is active. Assuming Lot 1 target hit. Proceeding with TSL.")
                    else:
                        logger.info(f"Both Lot 1 and Lot 2 are inactive or missing. Trade complete. Clearing state.")
                        self.sm.save_state({})
                        return True
            else:
                # OCO is None - likely already completed/cancelled
                # In this case, we assume Lot 1 target was hit (that's why OCO completed)
                # and we should proceed with trailing SL for Lot 2
                logger.info(f"Lot 1 OCO not found (likely completed). Proceeding with Lot 2 trailing SL update.")

            # Calculate Technical Levels
            # Prefer active_contract (current contract) over stale state instrument.
            # This is critical after contract rolls (e.g., Feb -> Mar expiry).
            instrument = active_contract or state.get("instrument")
            if not instrument:
                logger.error("Instrument not found in state or active_contract. Cannot calculate trailing SL.")
                return True

            # If active_contract differs from what's in state, update state to avoid stale data next time
            if active_contract and state.get("instrument") != active_contract:
                logger.info(f"Updating state instrument from {state.get('instrument')} to {active_contract} (contract roll detected).")
                state["instrument"] = active_contract
                self.sm.save_state(state)

            candles = self.fetcher.fetch_previous_trading_days(instrument)
            if not candles or len(candles) < 4:
                logger.error(f"Not enough historical data for 4d levels (instrument: {instrument}, got {len(candles) if candles else 0} candles).")
                # Latch the slot so we don't retry every 5s when data is unavailable
                state["tsl_session_slot"] = tsl_session_slot
                state["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.sm.save_state(state)
                return True
                
            last_4 = candles[:4]
            four_d_hh = max(c['high'] for c in last_4)
            four_d_ll = min(c['low'] for c in last_4)
            
            # Apply TSL Formulas
            if triggered_side == "BUY":
                val1 = entry_price * (1 - 0.015)
                val2 = four_d_ll * (1 - 0.0012)
                new_sl = self.mround(max(val1, val2), 1)
            else:
                val1 = entry_price * (1 + 0.015)
                val2 = four_d_hh * (1 + 0.0012)
                new_sl = self.mround(min(val1, val2), 1)
            
            logger.info(f"Daily Trailing SL Calculation for {triggered_side}: {new_sl}")
            self.om.modify_gtt_order(lot2_id, new_sl)

            # Mark this session slot as done so we don't recalculate every 5s
            state["tsl_session_slot"] = tsl_session_slot
            state["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.sm.save_state(state)
            return True

        return False
    def _check_for_external_triggers(self, gtts):
        """Checks if any GTT has triggered Since the last run."""
        for side in ["BUY", "SELL"]:
            oco_id = gtts.get(side, {}).get("OCO")
            single_id = gtts.get(side, {}).get("SINGLE")
            
            # Check OCO first
            if oco_id:
                details = self.om.get_gtt_order_details(oco_id)
                if details:
                    rules = details.get("rules", [])
                    entry_rule = next((r for r in rules if r.get("strategy") == "ENTRY"), None)
                    if entry_rule and entry_rule.get("status") in ["TRIGGERED", "COMPLETED"]:
                        entry_price = entry_rule.get("trigger_price")
                        return side, entry_price
            
            # If OCO is None, check SINGLE GTT as well
            elif single_id:
                details = self.om.get_gtt_order_details(single_id)
                if details:
                    rules = details.get("rules", [])
                    entry_rule = next((r for r in rules if r.get("strategy") == "ENTRY"), None)
                    if entry_rule and entry_rule.get("status") in ["TRIGGERED", "COMPLETED"]:
                        entry_price = entry_rule.get("trigger_price")
                        return side, entry_price
        return None

    def update_trailing_sl_from_session(self, high, low):
        """
        Updates the Trailing Stop Loss for Lot 2 based on the High/Low of the closed session.
        Called by main.py when a SESSION_BOUNDARY event occurs and a trade is ACTIVE.
        
        Args:
            high: High of the just-closed session.
            low: Low of the just-closed session.
        """
        state = self.sm.load_state()
        triggered_side = state.get("triggered_side")
        gtts = state.get("gtts", {})
        
        if not triggered_side:
            logger.info("No active triggered trade. Skipping Session TSL Update.")
            return False

        logger.info(f"Processing Session TSL Update for {triggered_side} (Ref High: {high}, Ref Low: {low})")
        
        # Verify Lot 1 Target Hit (Condition for Trailing)
        # Note: If Lot 1 was hit, OCO ID might be None or TRIGGERED.
        # We check order details if ID exists.
        
        lot1_id = gtts.get(triggered_side, {}).get("OCO")
        lot2_id = gtts.get(triggered_side, {}).get("SINGLE")
        
        if not lot2_id:
            logger.error("Lot 2 ID missing. Cannot update TSL.")
            return False
            
        # Check Lot 1 Status
        target_hit = False
        if lot1_id:
            details = self.om.get_gtt_order_details(lot1_id)
            if details:
                rules = details.get("rules", [])
                target_rule = next((r for r in rules if r.get("strategy") == "TARGET"), None)
                if target_rule and target_rule.get("status") in ["TRIGGERED", "COMPLETED"]:
                    target_hit = True
            else:
                # If details missing but we assume it's done? Safer to say true if Lot 2 is active?
                # For now strict check.
                pass
        else:
            # If Lot 1 ID is gone/None but state says triggered, implies Lot 1 finished?
            # Or it implies state issue. 
            # If triggered_side is set, we assume valid trade.
            # If Lot 1 is missing, we assume it's closed (Target Hit likely).
            target_hit = True 

        if not target_hit:
            logger.info("Lot 1 Target NOT hit yet. Skipping TSL update (waiting for partial profit).")
            # Mark as handled to avoid loop
            state["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.sm.save_state(state)
            return False

        # Calculate New SL
        # BUY: SL = Session Low - Buffer
        # SELL: SL = Session High + Buffer
        
        from config import SL_BUFFER_PCT
        new_sl = None
        
        if triggered_side == "BUY":
            # SL below the low
            raw_sl = low * (1 - SL_BUFFER_PCT)
            # Rounding 0.1?
            new_sl = self.mround(raw_sl, 0.05) # Gold ticks 0.05 usually or 1? MCX Gold is 1. Checking usage.
            # mround in this class uses int(). Let's stick to simple logic or verify tick.
            # Base class generic mround (int):
            new_sl = int(raw_sl) 
        else:
            # SL above the high
            raw_sl = high * (1 + SL_BUFFER_PCT)
            new_sl = int(raw_sl) # Ceil preferred for Sell SL? Rounding safe enough.

        logger.info(f"Calculated New Session TSL: {new_sl}")
        
        # Modify Order
        # We need to ensure we don't move SL backwards? 
        # Ideally TSL should only tighten. 
        # Fetch current SL to compare?
        # modify_gtt_order (Upstox) replaces rule. 
        # Proper TSL logic: Only update if New SL is "Better" (Higher for Buy, Lower for Sell).
        
        current_details = self.om.get_gtt_order_details(lot2_id)
        if current_details:
             rules = current_details.get("rules", [])
             sl_rule = next((r for r in rules if r.get("strategy") == "STOPLOSS"), None)
             current_sl = float(sl_rule['trigger_price']) if sl_rule else None
             
             if current_sl:
                 if triggered_side == "BUY" and new_sl <= current_sl:
                     logger.info(f"New SL ({new_sl}) is not higher than Current SL ({current_sl}). Holding.")
                     # Mark as handled
                     state["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                     self.sm.save_state(state)
                     return False
                 if triggered_side == "SELL" and new_sl >= current_sl:
                     logger.info(f"New SL ({new_sl}) is not lower than Current SL ({current_sl}). Holding.")
                     # Mark as handled
                     state["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                     self.sm.save_state(state)
                     return False
        
        if self.om.modify_gtt_order(lot2_id, new_sl=new_sl):
             logger.info(f"Successfully updated Lot 2 TSL to {new_sl}")
             state["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
             self.sm.save_state(state)
             return True
        else:
             logger.error("Failed to modify Lot 2 TSL.")
             state["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S") # Mark as handled anyway
             self.sm.save_state(state)
             return False



    def _cancel_opposite_side_gtts(self, triggered_side, gtts):
        """
        Cancels the GTTs of the opposite side once one side is triggered.
        """
        opposite_side = "SELL" if triggered_side == "BUY" else "BUY"
        logger.info(f"Cancelling Opposite Side ({opposite_side}) GTTs...")
        
        opp_gtts = gtts.get(opposite_side, {})
        for gtt_id in opp_gtts.values():
             if gtt_id:
                  self.om.cancel_gtt_order(gtt_id)
                  
        logger.info(f"Opposite Side ({opposite_side}) GTTs Cancelled.")
