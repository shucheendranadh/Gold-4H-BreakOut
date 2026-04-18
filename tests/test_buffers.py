import unittest
from Core.signal_engine import SignalEngine
from config import ENTRY_BUFFER_PCT, SL_BUFFER_PCT

class TestBufferLogic(unittest.TestCase):
    def setUp(self):
        self.engine = SignalEngine()

    def test_buffer_calculations(self):
        # Scenario: 
        # High = 1000
        # Low = 900
        # Entry Buffer = 0.20% -> 0.0020
        # SL Buffer = 0.15% -> 0.0015
        
        high = 1000
        low = 900
        
        # Expected Logic:
        # Buy Entry = 1000 * 1.0020 = 1002.0
        # Buy SL = 1002.0 * (1 - 0.0015) = 1002.0 * 0.9985 = 1000.497 -> MROUND 0.05 -> 1000.50
        
        # Sell Entry = 900 * (1 - 0.0020) = 900 * 0.998 = 898.2
        # Sell SL = 898.2 * (1 + 0.0015) = 898.2 * 1.0015 = 899.5473 -> MROUND 0.05 -> 899.55
        
        levels = self.engine.calculate_levels_with_buffers(high, low)
        
        # Verify Buy Side
        self.assertAlmostEqual(levels["BUY"]["entry"], 1002.0, delta=0.01)
        self.assertAlmostEqual(levels["BUY"]["sl"], 1000.50, delta=0.01)
        
        # Verify Sell Side
        self.assertAlmostEqual(levels["SELL"]["entry"], 898.2, delta=0.01)
        self.assertAlmostEqual(levels["SELL"]["sl"], 899.55, delta=0.01)

    def test_mround(self):
        self.assertEqual(self.engine.mround(100.02, 0.05), 100.00)
        self.assertEqual(self.engine.mround(100.03, 0.05), 100.05)
        self.assertEqual(self.engine.mround(100.07, 0.05), 100.05)

if __name__ == '__main__':
    unittest.main()
