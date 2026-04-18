
import logging
import sys
from Core.order_manager import OrderManager
from Core.state_manager import StateManager

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("GOLD_MARKET")

def main():
    logger.info("=== STARTING FORCE CLEANUP OF ALL GTTS ===")
    
    om = OrderManager()
    
    # 1. Fetch All Active GTTs
    logger.info("Fetching active GTTs from Upstox...")
    active_gtts = om.fetch_active_gtts()
    
    if not active_gtts:
        logger.info("No Active GTTs found on Upstox Account.")
    else:
        logger.info(f"Found {len(active_gtts)} active GTTs. Cancelling...")
        
        # 2. Cancel Each
        count = 0
        for gtt in active_gtts:
            gtt_id = gtt.get("gtt_order_id")
            logger.info(f"Cancelling GTT ID: {gtt_id}...")
            if om.cancel_gtt_order(gtt_id):
                logger.info(f"✓ Cancelled {gtt_id}")
                count += 1
            else:
                logger.error(f"✗ Failed to cancel {gtt_id}")
                
        logger.info(f"Cleanup Complete. Cancelled {count}/{len(active_gtts)} GTTs.")
    
    # 3. Clear State
    sm = StateManager()
    sm.clear_state()
    logger.info("Trading State Cleared.")

if __name__ == "__main__":
    main()
