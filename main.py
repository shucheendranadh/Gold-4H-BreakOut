
import os
import sys
import logging
import time
import atexit
from datetime import datetime
from config import LOG_FILE_PATH_MARKET, MARKET_START_TIME, SESSION_END_TIME, GUARDIAN_CHECK_INTERVAL, ENABLE_PAPER_TRADING, INITIAL_PAPER_CAPITAL
from Core.signal_engine import SignalEngine
from Core.gtt_manager import GTTManager
from Core.instrument_manager import InstrumentManager
from Core.cancel_gtts import CancelGTTs
from Core.guardian import Guardian
from Core.position_manager import PositionManager
from Core.state_manager import StateManager
from Core.paper_exchange import PaperExchange

# Ensure log directory exists
log_dir = os.path.dirname(LOG_FILE_PATH_MARKET)
if log_dir and not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Configure logging
logger = logging.getLogger("GOLD_MARKET")
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(LOG_FILE_PATH_MARKET)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

LOCK_FILE = "gold_market.lock"

def cleanup_lock():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

def main():
    logger.info("=== STARTING GOLD 4H BREAKOUT SYSTEM ===")
    
    # --- Lock Handling ---
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                old_pid = int(f.read().strip())
                logger.warning(f"Found existing lock file (PID {old_pid}). Overwriting assuming restart.")
        except Exception:
            pass

    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))
    
    atexit.register(cleanup_lock)
    
    # --- Initialization ---
    signal_engine = SignalEngine()
    gtt_manager = GTTManager()
    cancel_tool = CancelGTTs()
    sm = StateManager() # StateManager initialized here
    pm = PositionManager() # PositionManager initialized here
    guardian = Guardian() # Initialize Guardian
    paper = PaperExchange() # Initialize Paper Exchange
    
    # Fetch Active Contract once
    im = InstrumentManager()
    active_contract = im.get_active_contract()
    
    if not active_contract:
        logger.error("Failed to determine active contract. Exiting.")
        return

    logger.info(f"Active Contract: {active_contract}")
    now = datetime.now()
    current_hhmm = now.strftime("%H:%M:%S")
    
    if current_hhmm < MARKET_START_TIME:
        logger.info(f"System waiting for start time {MARKET_START_TIME} (Current: {current_hhmm})...")
    else:
        logger.info(f"Market is Open (Current: {current_hhmm}). Starting System...")
    
    # --- Startup Logic: Mid-Day Recovery ---
    # If starting mid-day with NO state, we assume we missed the earlier sessions.
    # We attempt to place GTTs based on the *last completed* session immediately.
    # This relies on SESSIONS config to define what "last session" means.
    current_state = sm.load_state()
    if not current_state:
        now = datetime.now()
        current_hhmm = now.strftime("%H:%M")
        
        # Only run if we are within market hours but "late" (e.g., after 09:00 and before 23:30)
        # signal_engine.generate_restorative_plan handles the time logic (returns None if too early/invalid)
        if current_hhmm > MARKET_START_TIME and current_hhmm < SESSION_END_TIME:
            logger.info("Fresh Start detected Mid-Day. Checking for restorative GTT opportunity...")
            
            # Use the "Restorative Plan" logic (same as Guardian)
            plan, meta = signal_engine.generate_restorative_plan(active_contract)
            
            if plan:
                if meta:
                     sm.save_session_levels(
                         session_name=meta.get('session', "Startup-Restoration"),
                         plan=plan,
                         high_low_data=meta
                     )
                logger.info("Restorative Plan Generated. Placing Startup GTTs...")
                gtt_manager.place_gtts(
                    active_contract=active_contract,
                    plan=plan,
                    session_name="Startup-Restoration"
                )
            else:
                logger.info("No Restorative Plan available (Time might be too early or data missing). waiting for next session.")

    # --- Timing Variables ---
    last_maintenance_time = 0
    last_guardian_time = time.time()
    
    # --- Main Loop ---
    running = True
    
    while running:
        try:
            now = datetime.now()
            current_hhmm = now.strftime("%H:%M")
            
            # Stop condition
            if current_hhmm >= SESSION_END_TIME:
                logger.info(f"Session End Time ({SESSION_END_TIME}) reached. Shutting down.")
                running = False
                break
                
            current_ts = time.time()
 \
 
            # --- JOB 1: GUARDIAN CHECK (Every Configured Interval) ---
            # Only run Guardian if Market is OPEN (after start time)
            if current_hhmm >= MARKET_START_TIME and (current_ts - last_guardian_time > GUARDIAN_CHECK_INTERVAL):
                logger.info("Running Scheduled Guardian Check...")
                try:
                     # Guardian Internal Logic: Check Crash -> Panic -> Restore
                     guardian.check_for_crash(active_contract)
                except Exception as e:
                     logger.error(f"Error in Guardian Check: {e}")
                last_guardian_time = current_ts

            # --- JOB 2: SIGNAL & MAINTENANCE (Every 5 Seconds) ---
            if current_ts - last_maintenance_time > 5:
                # 0. Paper Trading Monitor (Live Execution Simulation)
                if ENABLE_PAPER_TRADING:
                    ltp = signal_engine.md.fetcher.fetch_ltp(active_contract)
                    if ltp:
                        paper.monitor(ltp)
                        
                # A. Handle Maintenance (Triggers, Trailing SL)
                current_state = sm.load_state()
                if current_state:
                    pm.handle_daily_maintenance(current_state, active_contract=active_contract)

                # B. Handle Schedule & Events
                actions = signal_engine.check_schedule(active_contract, state=current_state)
                
                for act in actions:
                    logger.info(f"Event Received: {act.get('action', act.get('event'))}")
                    
                    if act.get('action') == "PLACE_GTT":
                         gtt_manager.place_gtts(
                            active_contract=active_contract,
                            plan=act['plan'],
                            session_name=act['session']
                        )
                    
                    elif act.get('action') == "GAP_WAIT":
                        session = act.get('session')
                        timeout = act.get('timeout')
                        logger.info(f"[{session}] Gap Protection Active. Waiting until {timeout} to calculate range.")
                         
                    elif act.get('action') == "CANCEL_ONLY":
                        session = act.get('session')
                        logger.info(f"[{session}] Gap detected at boundary. Cancelling existing GTTs first.")
                        cancel_tool.cancel_stored_gtts()
                        
                    elif act.get('event') == "SESSION_BOUNDARY":
                        session_name = act.get('session_name')
                        high = act.get('high')
                        low = act.get('low')
                        plan = act.get('plan')
                        
                        logger.info(f"Processing Session Boundary for {session_name} (Range: {high}-{low})")
                        
                        state = sm.load_state()
                        if state.get("triggered_side"):
                            pm.update_trailing_sl_from_session(high, low)
                        else:
                            # Level Rotation
                            cancel_tool.cancel_stored_gtts()
                            gtt_manager.place_gtts(
                                active_contract=active_contract,
                                plan=act['plan'],
                                session_name=act['session_name']
                            )
                        
                        # Save Levels for recovery
                        sm.save_session_levels(
                            session_name=session_name, 
                            plan=plan, 
                            high_low_data={'high': high, 'low': low}
                        )


                last_maintenance_time = current_ts

            # Sleep Logic
            sleep_duration = signal_engine.get_sleep_interval()
            time.sleep(sleep_duration)

        except KeyboardInterrupt:
            logger.info("User interrupted. Exiting.")
            running = False
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
            time.sleep(1) # Prevent tight error loop
            
    logger.info("=== SYSTEM SHUTDOWN ===")

if __name__ == "__main__":
    main()
