import logging
import time
from Core.state_manager import StateManager
from Core.order_manager import OrderManager

logger = logging.getLogger("GOLD_MARKET")

class CancelGTTs:
    def __init__(self):
        self.sm = StateManager()
        self.om = OrderManager()

    def cancel_stored_gtts(self):
        """
        Reads trading_state.json, finds all GTT IDs (BUY/SELL -> OCO/SINGLE),
        and cancels them using OrderManager. 
        Updates key in state to None upon successful cancellation.
        """
        state = self.sm.load_state()
        if not state:
            logger.warning("No trading state found or empty.")
            return

        gtts = state.get('gtts', {})
        if not gtts:
            logger.info("No 'gtts' key found in trading state.")
            return

        updates_made = False
        
        # Traverse expected structure: gtts -> BUY/SELL -> OCO/SINGLE
        for side in ['BUY', 'SELL']:
            side_gtts = gtts.get(side, {})
            if not isinstance(side_gtts, dict):
                continue

            for order_type, gtt_id in side_gtts.items():
                # Check for valid GTT ID (strings, not None/Empty/SKIPPED)
                if gtt_id and isinstance(gtt_id, str) and gtt_id != "SKIPPED":
                    logger.info(f"Found Stored GTT ID to cancel: {gtt_id} ({side} {order_type})")
                    
                    success = self.om.cancel_gtt_order(gtt_id)
                    
                    if success:
                        logger.info(f"Successfully cancelled {gtt_id}. Removing from state.")
                        side_gtts[order_type] = None
                        updates_made = True
                    else:
                        logger.error(f"Failed to cancel {gtt_id}. Keeping in state for retry.") # Or remove if 404? 
                        # For now, let's assume we keep it if API fail, but if it's 404/invalid, manual intervention might be needed.
                        # Existing OrderManager.cancel_gtt_order returns False on error.
                        
                        # OPTIONAL check: if error was 'not found', we could clear it. 
                        # But OrderManager doesn't expose error code easily. 
                        # Sticking to safe approach: retry later / keep key.
                elif gtt_id == "SKIPPED":
                     # If it was skipped, we can just clear it out as "done" or leave it. 
                     # Usually "SKIPPED" means we didn't place it. 
                     pass

        if updates_made:
            self.sm.save_state(state)
            logger.info("Trading state updated after GTT cancellations.")
        else:
            logger.info("No active GTT cancellations performed or state remained unchanged.")
