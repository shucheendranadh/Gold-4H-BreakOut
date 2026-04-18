import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

try:
    from Core.instrument_manager import InstrumentManager
    print("Successfully imported InstrumentManager")
    im = InstrumentManager()
    print("Successfully instantiated InstrumentManager")
except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Error: {e}")
