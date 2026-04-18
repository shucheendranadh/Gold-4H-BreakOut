
from config import GTT_LOG_PATH
import json
import os
from datetime import datetime


class TradeRegistry:
    def __init__(self):
        pass

    def load_registry(self):
        filename = GTT_LOG_PATH.format(date=datetime.now().strftime("%Y-%m-%d"))
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    content = f.read().strip()
                    if not content: return []
                    return json.loads(content)
            except json.JSONDecodeError:
                return []
        return []

    def save_registry(self, registry):
        filename = GTT_LOG_PATH.format(date=datetime.now().strftime("%Y-%m-%d"))
        # Ensure dir exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'w') as f:
            json.dump(registry, f, indent=4)

    def log_trade(self, action, details):
        registry = self.load_registry()
        registry.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": action,
            "details": details
        })
        self.save_registry(registry)
