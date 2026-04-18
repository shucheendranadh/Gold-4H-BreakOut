
import unittest
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/../")

from Core.trade_manager import TradeManager

class TestGapLogic(unittest.TestCase):
    def setUp(self):
        self.tm = TradeManager()
        # Setup common data
        self.technical_levels = {
            "4dHH": 200000.0,
            "4dLL": 100000.0,
            "2dHH": 180000.0,
            "2dLL": 120000.0
        }
        self.daily_candles = [{
            "high": 190000.0,
            "low": 110000.0,
            "close": 150000.0 # Prev Close
        }]
        
        # Calculate expected Standard Entries for reference
        # Buy Entry = MROUND(4dHH * 1.0012, 1) = 200000 * 1.0012 = 200240
        # Sell Entry = MROUND(4dLL * 0.9988, 1) = 100000 * 0.9988 = 99880
        self.expected_buy_entry = 200240.0
        self.expected_sell_entry = 99880.0

    def test_gap_up_detected(self):
        """
        Scenario: Open Price (200500) > Buy Entry (200240)
        Expected: Gap Up True, Condition specific
        """
        intraday_data = {"open": 200500.0, "high_915": 201000.0}
        
        plan = self.tm.calculate_trade_levels(self.technical_levels, self.daily_candles, intraday_data)
        
        buy_plan = plan['BUY']
        self.assertTrue(buy_plan['gap_up'], "Gap Up should be detected when Open > Buy Entry")
        self.assertIn("Gap Up", buy_plan['condition'])
        
        # Verify Entry is calculated based on 9:15 high
        # MROUND(201000 * 1.0012, 1) = 201241.2 -> 201241
        expected_gap_entry = self.tm.mround(201000.0 * 1.0012, 1)
        self.assertEqual(buy_plan['entry'], expected_gap_entry)

    def test_gap_down_detected(self):
        """
        Scenario: Open Price (99000) < Sell Entry (99880)
        Expected: Gap Down True, Condition specific
        """
        intraday_data = {"open": 99000.0, "low_915": 98000.0}
        
        plan = self.tm.calculate_trade_levels(self.technical_levels, self.daily_candles, intraday_data)
        
        sell_plan = plan['SELL']
        self.assertTrue(sell_plan['gap_down'], "Gap Down should be detected when Open < Sell Entry")
        self.assertIn("Gap Down", sell_plan['condition'])
        
        # Verify Entry is calculated based on 9:15 low
        # MROUND(98000 * 0.9988, 1) = 97882.4 -> 97882
        expected_gap_entry = self.tm.mround(98000.0 * 0.9988, 1)
        self.assertEqual(sell_plan['entry'], expected_gap_entry)

    def test_no_gap_inside_range(self):
        """
        Scenario: Sell Entry < Open (150000) < Buy Entry
        Expected: Standard Entries, No Gap flags
        """
        intraday_data = {"open": 150000.0} # Same as prev close, safely inside
        
        plan = self.tm.calculate_trade_levels(self.technical_levels, self.daily_candles, intraday_data)
        
        # Buy Check
        self.assertFalse(plan['BUY']['gap_up'])
        self.assertEqual(plan['BUY']['entry'], self.expected_buy_entry)
        self.assertEqual(plan['BUY']['condition'], "Standard")
        
        # Sell Check
        self.assertFalse(plan['SELL']['gap_down'])
        self.assertEqual(plan['SELL']['entry'], self.expected_sell_entry)
        self.assertEqual(plan['SELL']['condition'], "Standard")

    def test_false_positive_check(self):
        """
        Scenario: Open (160000) > Prev Close (150000) BUT Open < Buy Entry (200240)
        Old Logic would say Gap Up. New Logic should say No Gap.
        """
        intraday_data = {"open": 160000.0}
        
        plan = self.tm.calculate_trade_levels(self.technical_levels, self.daily_candles, intraday_data)
        
        self.assertFalse(plan['BUY']['gap_up'], "Should NOT be Gap Up just because Open > Prev Close")
        self.assertEqual(plan['BUY']['entry'], self.expected_buy_entry)

    def test_false_positive_check_down(self):
        """
        Scenario: Open (140000) < Prev Close (150000) BUT Open > Sell Entry (99880)
        Old Logic would say Gap Down. New Logic should say No Gap.
        """
        intraday_data = {"open": 140000.0}
        
        plan = self.tm.calculate_trade_levels(self.technical_levels, self.daily_candles, intraday_data)
        
        self.assertFalse(plan['SELL']['gap_down'], "Should NOT be Gap Down just because Open < Prev Close")
        self.assertEqual(plan['SELL']['entry'], self.expected_sell_entry)

if __name__ == '__main__':
    unittest.main()
