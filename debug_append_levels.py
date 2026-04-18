from Core.state_manager import StateManager
import json
import os

def test_append():
    print("--- Testing save_session_levels Append Behavior ---")
    sm = StateManager()
    file_path = "Data/session_levels.json"
    
    # 1. Clear file first (Simulate reset)
    with open(file_path, 'w') as f:
        json.dump([], f)
    print("1. File cleared.")
        
    # 2. Save Session 1
    print("2. Saving Session 1...")
    sm.save_session_levels("Session 1", {"buy": 100}, {"high": 200, "low": 100})
    
    # 3. Save Session 2
    print("3. Saving Session 2...")
    sm.save_session_levels("Session 2", {"buy": 105}, {"high": 205, "low": 105})
    
    # 4. Check Content
    with open(file_path, 'r') as f:
        data = json.load(f)
        
    print(f"Entries found: {len(data)}")
    for i, entry in enumerate(data):
        print(f"[{i}] {entry['session']}")
        
    if len(data) == 2:
        print("SUCCESS: Data appended correctly.")
    else:
        print("FAILURE: Data NOT appended.")

if __name__ == "__main__":
    test_append()
