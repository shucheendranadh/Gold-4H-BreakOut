import logging
import math
from datetime import datetime, timedelta
from config import (
    SESSIONS, MARKET_START_TIME, STRATEGY_MODE, 
    ENTRY_BUFFER_PCT, SL_BUFFER_PCT, TARGET_RISK_REWARD_RATIO,
    FIXED_SL_PCT, FIXED_TARGET_PCT, LL_BUFFER_PCT
)
from Core.market_data import MarketData
from Core.session_logger import SessionLogger

logger = logging.getLogger("GOLD_MARKET")

class SignalEngine:
    def __init__(self):
        self.md = MarketData()
        self.sessions = SESSIONS # ["09:00", "13:00", "17:00", "21:00"]
        self._session1_retry_after = None  # cooldown after PDH/PDL fetch failure

    def mround(self, number, base=0.05):
        return round(round(number / base) * base, 2)

    def calculate_levels_with_buffers(self, high, low, historical_candles=[], use_structural_entry=True):
        """
        Calculates Entry, SL (Lot 1 & 2), and Target using advanced 4H Logic.
        
        Buy SL Lot 1 = MAX( (Entry * (1 - 1.5%)), (2_Candle_LL * (1 - 0.12%)) )
        Buy SL Lot 2 = MAX( (Entry * (1 - 1.5%)), (4_Candle_LL * (1 - 0.12%)) )
        Buy Target   = Entry * (1 + 1.5%)
        """
        # 2. Historical Lows/Highs
        # Last 4 candles (list of dicts with 'high', 'low')
        
        ref_high = high
        ref_low = low
        
        last_2_low = low
        last_4_low = low
        last_2_high = high
        last_4_high = high
        
        if historical_candles:
             # Sort presumably ascending by time
             # 2-Candle LL (Last 2)
             last_2 = historical_candles[-2:]
             last_2_low = min(c['low'] for c in last_2)
             last_2_high = max(c['high'] for c in last_2)
             
             # 4-Candle LL (Last 4)
             last_4 = historical_candles[-4:]
             last_4_low = min(c['low'] for c in last_4)
             last_4_high = max(c['high'] for c in last_4)
             
             # OVERRIDE: Entry Reference is based on Last 4 Sessions (If not Gap resolution)
             if use_structural_entry:
                  ref_high = last_4_high
                  ref_low = last_4_low
             else:
                  logger.info(f"Gap Resolution active: Skipping Structural Entry Override (Ref: H={high}, L={low})")
        else:
             logger.warning("No historical candles provided. Using current session Low/High as fallback.")

        # 1. Calculate Entry (Based on Ref High/Low + Buffer)
        buy_entry = self.mround(ref_high * (1 + ENTRY_BUFFER_PCT), base=1.0)
        sell_entry = self.mround(ref_low * (1 - ENTRY_BUFFER_PCT), base=1.0)
             
        # 3. Calculate BUY Levels
        # Fixed SL Component
        buy_sl_fixed = self.mround(buy_entry * (1 - FIXED_SL_PCT), base=1.0)
        
        # Structure SL Component (LL - Buffer)
        buy_sl_struct_2 = self.mround(last_2_low * (1 - LL_BUFFER_PCT), base=1.0)
        buy_sl_struct_4 = self.mround(last_4_low * (1 - LL_BUFFER_PCT), base=1.0)
        
        # Lot 1 SL (Max of Fixed vs 2-Candle)
        # Components are already rounded, but taking MAX preserves integer/rounded property.
        # We can keep mround here or not, but removing it is cleaner if inputs are rounded.
        # However, to be extra safe and consistent with "Apply MROUND to all formula", let's keep it or just rely on inputs.
        # The user's request was "apply round to all formula like... MROUND(...)". 
        # So I will apply it to the base components.
        
        buy_sl_1 = max(buy_sl_fixed, buy_sl_struct_2)
        
        # Lot 2 SL (Max of Fixed vs 4-Candle)
        buy_sl_2 = max(buy_sl_fixed, buy_sl_struct_4)
        
        # Target
        buy_target = self.mround(buy_entry * (1 + FIXED_TARGET_PCT), base=1.0)
        
        
        # 4. Calculate SELL Levels
        # Fixed SL Component
        sell_sl_fixed = self.mround(sell_entry * (1 + FIXED_SL_PCT), base=1.0)
        
        # Structure SL Component (HH + Buffer)
        sell_sl_struct_2 = self.mround(last_2_high * (1 + LL_BUFFER_PCT), base=1.0)
        sell_sl_struct_4 = self.mround(last_4_high * (1 + LL_BUFFER_PCT), base=1.0)
        
        # Lot 1 SL (Min of Fixed vs 2-Candle)
        sell_sl_1 = min(sell_sl_fixed, sell_sl_struct_2)
        sell_sl_2 = min(sell_sl_fixed, sell_sl_struct_4)
        
        # Target
        sell_target = self.mround(sell_entry * (1 - FIXED_TARGET_PCT), base=1.0)

        return {
            "BUY":  {
                "entry": buy_entry,  
                "sl_1": buy_sl_1,
                "sl_2": buy_sl_2, # Explicitly separate
                "target": buy_target,
                "ref_high": ref_high # Added for transparency
            },
            "SELL": {
                "entry": sell_entry, 
                "sl_1": sell_sl_1,
                "sl_2": sell_sl_2, 
                "target": sell_target,
                "ref_low": ref_low # Added for transparency
            },
            "REFERENCE": {
                "high": ref_high,
                "low": ref_low
            }
        }

    def _format_plan_from_levels(self, levels):
        """Helper to format levels into the standard trade plan dictionary."""
        return {
            "BUY": {
                "entry": levels["BUY"]["entry"],
                "sl_1": levels["BUY"]["sl_1"],
                "sl_2": levels["BUY"]["sl_2"],
                "target_1": levels["BUY"]["target"] 
            },
            "SELL": {
                "entry": levels["SELL"]["entry"],
                "sl_1": levels["SELL"]["sl_1"],
                "sl_2": levels["SELL"]["sl_2"],
                "target_1": levels["SELL"]["target"]
            }
        }

    def check_schedule(self, instrument_token, state=None):
        """
        Checks the current time against the schedule and returns a list of actions.
        """
        now = datetime.now()
        current_time_str = now.strftime("%H:%M:%S")
        
        actions = []
        
        # Parse last_updated early
        last_updated_str = state.get("last_updated") if state else None
        last_updated_dt = None
        if last_updated_str:
            try:
                last_updated_dt = datetime.strptime(last_updated_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass 

        # 1. Start of Day / Pre-Market Check (09:00:01)
        # Logic: We must run Session 1 if:
        # A. Current time is >= MARKET_START_TIME
        # B. AND we haven't run it yet today (Checked via last_updated or no state)
        # C. AND we are before Session 2 (13:00) - otherwise we fall into "Restorative" path via main.py or "Session 2" logic.
        
        h, m, s = map(int, MARKET_START_TIME.split(":"))
        today_start_dt = now.replace(hour=h, minute=m, second=s, microsecond=0)
        
        # Check if we assume we haven't run Session 1 today
        has_run_today = False
        if last_updated_dt and last_updated_dt >= today_start_dt:
             has_run_today = True
             
        is_session_1_window = (now >= today_start_dt and current_time_str < "13:00:00")
        
        should_run_start = is_session_1_window and not has_run_today

        # Cooldown: after a PDH/PDL fetch failure, don't retry every 5s — wait 60s
        if should_run_start and self._session1_retry_after and now < self._session1_retry_after:
            should_run_start = False

        if should_run_start:
            logger.info(f"Triggering Session 1 Preparation (Current: {current_time_str})")
            
            # 0. Fetch Market Open (Reliable for Gap Check)
            day_open = self.md.fetcher.fetch_day_open(instrument_token)
            if day_open is None:
                 # Fallback to LTP
                 day_open = self.md.fetcher.fetch_ltp(instrument_token)
            
            # 1. Standard Preparation
            high, low = self.md.get_yesterday_high_low(instrument_token)
            
            if high and low:
                self._session1_retry_after = None
                # CHECK FOR ACTIVE TRADE (Fix for Overnight/Rollover Bug)
                active_trade_side = state.get("triggered_side") if state else None
                
                if active_trade_side:
                    logger.info(f"Start of Day: Active Trade ({active_trade_side}) detected. Treating as SESSION_BOUNDARY update.")
                    hist_candles = self.md.get_last_n_candles_4h(instrument_token)
                    levels = self.calculate_levels_with_buffers(high, low, hist_candles)
                    plan = self._format_plan_from_levels(levels)

                    actions.append({
                        "event": "SESSION_BOUNDARY",
                        "session_index": 0,
                        "session_name": "Session 1 (Start)",
                        "high": levels['REFERENCE']['high'],
                        "low": levels['REFERENCE']['low'],
                        "prev_start": "Yesterday",
                        "prev_end": "Today 09:00",
                        "plan": plan
                    })
                else:
                    # FRESH START: Gap Logic
                    hist_candles = self.md.get_last_n_candles_4h(instrument_token)
                    std_levels = self.calculate_levels_with_buffers(high, low, hist_candles)
                    
                    # Detect Gap
                    is_gap = False
                    if day_open is None:
                        logger.warning("day_open unavailable (API returned None) — skipping gap detection, using standard levels.")
                    elif day_open > std_levels['BUY']['entry']:
                        is_gap = "UP"
                    elif day_open < std_levels['SELL']['entry']:
                        is_gap = "DOWN"
                    
                    if is_gap:
                         gap_resolve_time = today_start_dt + timedelta(minutes=15)
                         if now < gap_resolve_time:
                              logger.info(f"GAP {is_gap} Detected at 09:00 (Open: {day_open}). Waiting for 09:15 range...")
                              actions.append({
                                  "action": "GAP_WAIT",
                                  "session": "Session 1",
                                  "timeout": "09:15"
                              })
                         else:
                              # Resolve Gap at 09:15
                              logger.info(f"Resolving 09:00 GAP {is_gap}. Fetching 09:00-09:15 range...")
                              g_high, g_low = self.md.get_session_high_low(instrument_token, "09:00", "09:15")
                              if g_high and g_low:
                                   # Use 15m range as reference. Bypass structural override.
                                   levels = self.calculate_levels_with_buffers(g_high, g_low, hist_candles, use_structural_entry=False)
                                   plan = self._format_plan_from_levels(levels)
                                   actions.append({
                                       "action": "PLACE_GTT",
                                       "plan": plan,
                                       "ref_level": {"high": g_high, "low": g_low, "type": "09:15-Gap-Range"},
                                       "session": "Session 1"
                                   })
                              else:
                                   logger.error("Failed to fetch Gap range. Falling back to Standard Session 1.")
                                   # Simple fallback (this loop can retry)
                    else:
                         # No Gap -> Standard Placement
                         levels = self.calculate_levels_with_buffers(high, low, hist_candles)
                         plan = self._format_plan_from_levels(levels)
                         actions.append({
                             "action": "PLACE_GTT",
                             "plan": plan,
                             "ref_level": {"high": high, "low": low, "type": "PDH/PDL"},
                             "session": "Session 1"
                         })
            else:
                self._session1_retry_after = now + timedelta(seconds=60)
                logger.error("Failed to fetch PDH/PDL for Session 1. Will retry in 60s.")

        # 2. Intraday Session Borders
        # Sessions: 13:00, 17:00, 21:00
        # Logic: If current time is PAST the session start, AND our last state update was BEFORE it, triggers event.
        


        for i, session_start in enumerate(self.sessions):
            if i == 0: continue # Skip 09:00 (handled by Start logic)
            
            # Create a datetime for this session start (Today)
            h, m = map(int, session_start.split(":"))
            target_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
            
            # Check if we crossed this boundary
            # Condition: Now >= SessionTime AND (No State OR State is older than SessionTime)
            # Note: If no state, usually handled by main.py startup logic. But to be safe:
            # We strictly check: if state exists, check timestamp. 
            
            should_trigger = False
            
            if now >= target_dt:
                if last_updated_dt:
                     # Check if we already processed this session
                     # If last update was BEFORE target_dt, we need to process.
                     if last_updated_dt < target_dt:
                         should_trigger = True
            
            if should_trigger:
                logger.info(f"Triggering Session Transition for {session_start} (Last Updated: {last_updated_str})")
                
                # Previous session
                prev_start = self.sessions[i-1]
                prev_end = session_start
                
                # Fetch Data for the closed session
                high, low = self.md.get_session_high_low(instrument_token, prev_start, prev_end)
                
                if high and low:
                    # Fetch 3 prior completed 4H candles, then inject the newly formed
                    # session as the 4th so structural entry/SL always uses last 4 sessions
                    # including the one that just closed.
                    hist_candles = self.md.get_last_n_candles_4h(instrument_token, n=3)
                    hist_candles = hist_candles + [{'high': high, 'low': low}]
                    std_levels = self.calculate_levels_with_buffers(high, low, hist_candles)
                    active_trade_side = state.get("triggered_side")
                    
                    if not active_trade_side:
                         # 1. Detect Intraday Gap at session start
                         ltp = self.md.fetcher.fetch_ltp(instrument_token)
                         is_gap = False
                         if ltp:
                             if ltp > std_levels['BUY']['entry']: is_gap = "UP"
                             elif ltp < std_levels['SELL']['entry']: is_gap = "DOWN"
                         
                         gap_resolve_time = target_dt + timedelta(minutes=15)
                         
                         if is_gap and now < gap_resolve_time:
                              logger.info(f"SESSION GAP {is_gap} detected at {session_start} (LTP: {ltp}). Cancelling old and waiting until {gap_resolve_time.strftime('%H:%M')}...")
                              actions.append({
                                  "action": "CANCEL_ONLY",
                                  "session": f"Session {i+1}"
                              })
                              actions.append({
                                  "action": "GAP_WAIT",
                                  "session": f"Session {i+1}",
                                  "timeout": (target_dt + timedelta(minutes=15)).strftime("%H:%M")
                              })
                              continue # Skip emitting SESSION_BOUNDARY until resolved or timeout
                         
                         if is_gap and now >= gap_resolve_time:
                              logger.info(f"Resolving {session_start} GAP {is_gap}. Fetching 15m range...")
                              g_start = session_start
                              g_end = (target_dt + timedelta(minutes=15)).strftime("%H:%M")
                              g_high, g_low = self.md.get_session_high_low(instrument_token, g_start, g_end)
                              if g_high and g_low:
                                   levels = self.calculate_levels_with_buffers(g_high, g_low, hist_candles, use_structural_entry=False)
                                   plan = self._format_plan_from_levels(levels)
                                   actions.append({
                                       "event": "SESSION_BOUNDARY",
                                       "session_index": i,
                                       "session_name": f"Session {i+1}",
                                       "high": levels['REFERENCE']['high'],
                                       "low": levels['REFERENCE']['low'],
                                       "prev_start": g_start,
                                       "prev_end": g_end,
                                       "plan": plan
                                   })
                                   continue # Processed
                    
                    # 2. Standard Logic (No Gap or Active Trade)
                    levels = self.calculate_levels_with_buffers(high, low, hist_candles)
                    plan = self._format_plan_from_levels(levels)

                    actions.append({
                        "event": "SESSION_BOUNDARY",
                        "session_index": i,
                        "session_name": f"Session {i+1}",
                        "high": levels['REFERENCE']['high'],
                        "low": levels['REFERENCE']['low'],
                        "prev_start": prev_start,
                        "prev_end": prev_end,
                        "plan": plan
                    })
                else:
                    logger.error(f"Failed to fetch High/Low for range {prev_start}-{prev_end}")
        
        return actions

    def generate_restorative_plan(self, instrument_token):
        """
        Generates a trade plan based on the LAST CLOSED 4H session.
        Used by Guardian to restore GTTs after a panic exit/reset.
        """
        now = datetime.now()
        current_time_str = now.strftime("%H:%M")
        
        # Find the last completed session
        # SESSIONS = ["09:00", "13:00", "17:00", "21:00"]
        last_session_idx = -1
        for i, s_start in enumerate(self.sessions):
            if current_time_str >= s_start:
                last_session_idx = i
            else:
                break
        
        # If we are before 09:00, use yesterday? Or just fail?
        # If we are between 09:00 and 13:00, we use 09:00 (which is open) -> logic might need PDH/PDL?
        # User said "based on last 4hrs candle".
        
        # If currently in Session 1 (09:00-13:00), "last 4h" is YESTERDAY'S last? 
        # Or Pre-market? 
        # Simpler: If < 13:00, use PDH/PDL (Session 1 Logic).
        # If >= 13:00, use the immediately preceding session (e.g. 09:00-13:00).
        
        plan = None
        high, low = None, None
        
        if current_time_str < "13:00":
            # Use PDH/PDL Logic
            high, low = self.md.get_yesterday_high_low(instrument_token)
            ref_type = "PDH/PDL (Restorative)"
        else:
            # Use last closed session
            # If 14:00, last closed is 09:00-13:00 (index 0 to 1)
            # last_session_idx would be 1 (13:00). So we want 09:00 to 13:00.
            
            # If last_session_idx is 0 (09:00), we are in it.
            # We need start/end of the block BEFORE current one.
            
            # Correct logic:
            # If > 13:00, we have at least one closed session today.
            # If now is 14:00. sessions[i] <= 14:00 is 13:00.
            # We want data from 09:00 (sessions[i-1]) to 13:00 (sessions[i]).
            
            # SESSIONS = ["09:00", "13:00", "17:00", "21:00"]
            
            end_idx = last_session_idx
            start_idx = end_idx - 1
            
            if start_idx < 0:
                # Fallback to PDH/PDL
                high, low = self.md.get_yesterday_high_low(instrument_token)
                ref_type = "PDH/PDL (Restorative Fallback)"
            else:
                prev_start = self.sessions[start_idx]
                prev_end = self.sessions[end_idx]
                high, low = self.md.get_session_high_low(instrument_token, prev_start, prev_end)
                ref_type = f"Session {prev_start}-{prev_end} (Restorative)"

        if high and low:
            hist_candles = self.md.get_last_n_candles_4h(instrument_token, n=3)
            hist_candles = hist_candles + [{'high': high, 'low': low}]
            levels = self.calculate_levels_with_buffers(high, low, hist_candles)
            plan = self._format_plan_from_levels(levels)
            logger.info(f"Generated Restorative Plan based on {ref_type}: Effective High={levels['REFERENCE']['high']}, Low={levels['REFERENCE']['low']}")
            
            meta = {
                "high": levels['REFERENCE']['high'], 
                "low": levels['REFERENCE']['low'], 
                "session": ref_type if 'ref_type' in locals() else "Restorative",
                "type": ref_type if 'ref_type' in locals() else "Unknown",
                "original_session_high": high,
                "original_session_low": low
            }
            
            # LOGGING
            SessionLogger.log_session_transition(
                "System Start (Restorative)", 
                levels, 
                f"Mid-Day Recovery based on {ref_type}", 
                None # No state available yet
            )
            
            return plan, meta
        else:
            logger.error("Failed to generate restorative plan: High/Low missing.")
            return None, None
        
    def get_sleep_interval(self):
        """
        Returns dynamic sleep interval. 
        """
        now = datetime.now()
        # If close to XX:XX:00 or XX:XX:01, sleep tiny (0.1s)
        if now.second >= 59 or now.second <= 1:
            return 0.1
        return 0.5
