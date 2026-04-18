import logging
import os
from datetime import datetime
from config import LOG_FILE_PATH_SESSION

# Ensure log directory exists
log_dir = os.path.dirname(LOG_FILE_PATH_SESSION)
if log_dir and not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Helper to setup dedicated logger
def setup_session_logger():
    logger = logging.getLogger("SESSION_REPORTS")
    logger.setLevel(logging.INFO)
    
    # Check if handler already exists to avoid duplicates
    if not logger.handlers:
        file_handler = logging.FileHandler(LOG_FILE_PATH_SESSION)
        formatter = logging.Formatter('%(message)s') # Plain format for clean reports
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    logger.propagate = False # Do not log to main console/file
    return logger

session_logger = setup_session_logger()

class SessionLogger:
    @staticmethod
    def log_session_transition(session_name, levels, status_message, state=None):
        """
        Logs a structured report for Session Transitions or System Start.
        """
        
        # Extract Levels
        buy_levels = levels.get("BUY", {})
        sell_levels = levels.get("SELL", {})
        ref_levels = levels.get("REFERENCE", {})
        
        # Format Report
        report = []
        report.append(f"\n{'='*20} {session_name.upper()} REPORT {'='*20}")
        report.append(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Status: {status_message}")
        
        active_side = state.get("triggered_side") if state else None
        
        if active_side:
            # --- ACTIVE TRADE REPORT ---
            report.append(f"\n*** ACTIVE TRADE: {active_side} ***")
            report.append(f"  Entry Price:       {state.get('entry_price', 'N/A')}")
            
            # Get current SL/Target from the *levels* passed (which represents the NEW calculated plan)
            # OR from state if available. Usually 'levels' contains the updated TSL.
            current_sl = levels.get(active_side, {}).get("sl_1", "N/A")
            current_target = levels.get(active_side, {}).get("target", "N/A")
            
            report.append(f"  Updated SL:        {current_sl}")
            report.append(f"  Target:            {current_target}")
            
            # Check for Target 1 Hit (Heuristic: If we are updating TSL, maybe T1 hit? 
            # Or we can't know for sure without checking orders. 
            # User asked: 'whether target 1 is hit'. 
            # We'll default to 'Pending' unless we can verify.)
            # For now, we don't have direct access to 'Target 1 Hit' bool in this scope.
            # We will just print the levels as requested.
            
            report.append(f"  Target 1 Status:   Check P&L/Orders") 

        else:
            # --- FULL LEVELS REPORT (No Trade) ---
            report.append(f"Active Trade: NONE")
            report.append(f"\n--- LEVELS (Ref High: {ref_levels.get('high')}, Ref Low: {ref_levels.get('low')}) ---")
            
            # BUY Table
            report.append("BUY SIDE:")
            report.append(f"  Entry:    {buy_levels.get('entry')}")
            report.append(f"  SL (L1):  {buy_levels.get('sl_1')}")
            report.append(f"  SL (L2):  {buy_levels.get('sl_2')}")
            report.append(f"  Target:   {buy_levels.get('target')}")
            
            # SELL Table
            report.append("SELL SIDE:")
            report.append(f"  Entry:    {sell_levels.get('entry')}")
            report.append(f"  SL (L1):  {sell_levels.get('sl_1')}")
            report.append(f"  SL (L2):  {sell_levels.get('sl_2')}")
            report.append(f"  Target:   {sell_levels.get('target')}")
        
        report.append("="*60 + "\n")
        
        # Log it to dedicated file
        session_logger.info("\n".join(report))
