
import sys
import os

print("Current Working Directory:", os.getcwd())
print("Sys Path:", sys.path)

try:
    import Core.market_data
    print("Successfully imported Core.market_data")
except ImportError as e:
    print("Failed to import Core.market_data:", e)

try:
    from Core.signal_engine import SignalEngine
    print("Successfully imported SignalEngine")
except ImportError as e:
    print("Failed to import SignalEngine:", e)
