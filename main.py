
import os
import sys
import logging
import time
import atexit
import fcntl
from datetime import datetime
from config import LOG_FILE_PATH_MARKET, MARKET_START_TIME, SESSION_END_TIME, GUARDIAN_CHECK_INTERVAL, GUARDIAN_ENABLED, ENABLE_PAPER_TRADING
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
logger.propagate = False

if not logger.handlers:
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler = logging.FileHandler(LOG_FILE_PATH_MARKET)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

LOCK_FILE = "gold_market.lock"
_lock_fd = None

def acquire_lock():
    """Acquire an exclusive OS-level file lock. Returns True if acquired, False if another instance holds it."""
    global _lock_fd
    try:
        _lock_fd = open(LOCK_FILE, 'w')
        fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock_fd.write(str(os.getpid()))
        _lock_fd.flush()
        return True
    except (IOError, OSError):
        if _lock_fd:
            _lock_fd.close()
            _lock_fd = None
        return False

def release_lock():
    global _lock_fd
    if _lock_fd:
        try:
            fcntl.flock(_lock_fd, fcntl.LOCK_UN)
            _lock_fd.close()
        except Exception:
            pass
        _lock_fd = None
    try:
        os.remove(LOCK_FILE)
    except Exception:
        pass

def main():
    # --- Lock Handling (atomic flock — race-condition-free) ---
    # Acquire lock BEFORE any logging so a losing duplicate process stays silent.
    if not acquire_lock():
        print("Another instance is already running. Exiting to prevent duplicate trades.", flush=True)
        return

    atexit.register(release_lock)
    logger.info("=== STARTING GOLD 4H BREAKOUT SYSTEM ===")
    
    # --- Initialization ---
    signal_engine = SignalEngine()
    gtt_manager = GTTManager()
    cancel_tool = CancelGTTs()
    sm = StateManager() # StateManager initialized here
    pm = PositionManager() # PositionManager initialized here
    guardian = Guardian() # Initialize Guardian
    paper = PaperExchange() # Initialize Paper Exchange
    
    # Fetch Active Contract — retry up to 3 times (quotes may be empty at market open)
    im = InstrumentManager()
    active_contract = None
    for attempt in range(1, 4):
        try:
            active_contract = im.get_active_contract()
        except Exception as e:
            logger.error(f"Exception in get_active_contract (attempt {attempt}/3): {e}")
        if active_contract:
            break
        if attempt < 3:
            logger.warning(f"Active contract not found (attempt {attempt}/3). Retrying in 60s...")
            time.sleep(60)

    if not active_contract:
        logger.error("Failed to determine active contract after 3 attempts. Exiting.")
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
        if current_hhmm > MARKET_START_TIME[:5] and current_hhmm < SESSION_END_TIME:
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

            # --- JOB 1: GUARDIAN CHECK (Every Configured Interval) ---
            # Only run Guardian if Market is OPEN (after start time) and Guardian is enabled
            if GUARDIAN_ENABLED and current_hhmm >= MARKET_START_TIME[:5] and (current_ts - last_guardian_time > GUARDIAN_CHECK_INTERVAL):
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
                         # Reload state to get the freshest triggered_side before placing
                         fresh_state = sm.load_state()
                         if fresh_state and fresh_state.get("triggered_side"):
                             logger.info(f"[{act.get('session', '?')}] Active trade ({fresh_state['triggered_side']}) in progress. Skipping GTT placement until trade closes.")
                         else:
                             cancel_tool.cancel_stored_gtts()
                             gtt_manager.place_gtts(
                                active_contract=active_contract,
                                plan=act['plan'],
                                session_name=act['session']
                            )
                             ref = act.get('ref_level', {})
                             sm.save_session_levels(
                                 session_name=act['session'],
                                 plan=act['plan'],
                                 high_low_data={'high': ref.get('high'), 'low': ref.get('low')}
                             )

                    elif act.get('action') == "GAP_WAIT":
                        session = act.get('session')
                        timeout = act.get('timeout')
                        logger.info(f"[{session}] Gap Protection Active. Waiting until {timeout} to calculate range.")

                    elif act.get('action') == "CANCEL_ONLY":
                        session = act.get('session')
                        # Guard: never cancel GTTs while a trade is active
                        fresh_state = sm.load_state()
                        if fresh_state and fresh_state.get("triggered_side"):
                            logger.info(f"[{session}] Active trade ({fresh_state['triggered_side']}) in progress. Skipping GTT cancellation.")
                        else:
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
