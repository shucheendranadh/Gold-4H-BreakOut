import json
import os
import logging
from datetime import datetime

logger = logging.getLogger("GOLD_MAIN")

class StateManager:
    def __init__(self, file_path="Data/trading_state.json"):
        self.file_path = file_path
        self._ensure_dir()

    def _ensure_dir(self):
        directory = os.path.dirname(self.file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

    def save_state(self, state_data):
        """Save the trading state to a JSON file."""
        try:
            with open(self.file_path, 'w') as f:
                json.dump(state_data, f, indent=4)
            logger.info(f"Trading state saved to {self.file_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving trading state: {e}")
            return False

    def load_state(self):
        """Load the trading state from a JSON file."""
        if not os.path.exists(self.file_path):
            return {}
        try:
            with open(self.file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading trading state: {e}")
            return {}

    def update_gtt_id(self, side, lot_type, gtt_id):
        """Helper to update a specific GTT ID in the state."""
        state = self.load_state()
        if 'gtts' not in state:
            state['gtts'] = {'BUY': {}, 'SELL': {}}
        state['gtts'][side][lot_type] = gtt_id
        return self.save_state(state)
    def clear_state(self):
        """Clears the trading state by saving an empty dictionary."""
        return self.save_state({})

    def save_session_levels(self, session_name, plan, high_low_data):
        """
        Appends session level data to Data/session_levels.json
        """
        file_path = "Data/session_levels.json"
        
        # Ensure directory exists
        self._ensure_dir() # Uses self.file_path's dir which is same "Data/"
        
        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "session": session_name,
            "high": high_low_data.get('high'),
            "low": high_low_data.get('low'),
            "plan": plan
        }

        try:
            data = []
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    try:
                        data = json.load(f)
                    except json.JSONDecodeError:
                        data = []
            
            data.append(entry)
            
            # Limit to last 50 entries
            if len(data) > 50:
                data = data[-50:]
                
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=4)
                
            logger.info(f"Saved Session Levels for {session_name}")
            return True
        except Exception as e:
            logger.error(f"Error saving session levels: {e}")
            return False
