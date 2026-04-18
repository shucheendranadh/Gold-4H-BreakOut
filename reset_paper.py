import os
import json
import logging
from config import INITIAL_PAPER_CAPITAL

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RESET_UTIL")

class PaperTradingReset:
    def __init__(self, data_dir="Data"):
        self.data_dir = data_dir
        self.files_to_reset = {
            "paper_orders.json": [],
            "paper_pnl.json": {
                "initial_capital": INITIAL_PAPER_CAPITAL,
                "current_balance": INITIAL_PAPER_CAPITAL,
                "realized_pnl": 0.0,
                "trades": []
            },
            "trading_state.json": {},
            "session_levels.json": []
        }
        self.debug_files = [
            "debug_historical_data.py", 
            "debug_low.py", 
            "debug_v3_params.py", 
            "debug_session_fetch.py"
        ]

    def reset_all(self):
        """
        Resets all paper trading logs to their initial empty states.
        """
        logger.info("Starting Paper Trading Reset...")
        
        # 1. Reset JSON Data Files
        for filename, default_content in self.files_to_reset.items():
            file_path = os.path.join(self.data_dir, filename)
            try:
                with open(file_path, 'w') as f:
                    json.dump(default_content, f, indent=4)
                logger.info(f"✔ Reset {filename}")
            except Exception as e:
                logger.error(f"✘ Failed to reset {filename}: {e}")

        # 2. Delete Debug Scripts (Root or Core)
        # Assuming script is run from Root
        for script in self.debug_files:
            if os.path.exists(script):
                try:
                    os.remove(script)
                    logger.info(f"✔ Deleted {script}")
                except Exception as e:
                    logger.error(f"✘ Failed to delete {script}: {e}")
            else:
                pass # Silent ignore if not found

        logger.info("Reset Complete. You can now restart the bot.")

if __name__ == "__main__":
    confirm = input("Are you sure you want to RESET all paper trading data? (y/n): ")
    if confirm.lower() == 'y':
        resetter = PaperTradingReset()
        resetter.reset_all()
    else:
        print("Reset cancelled.")
