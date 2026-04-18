import logging
import math

logger = logging.getLogger("GOLD_MAIN")

class TradeManager:
    @staticmethod
    def mround(value, factor):
        """
        Returns value rounded to the nearest multiple of factor.
        Emulates Excel's MROUND(value, factor).
        """
        if factor == 0:
            return 0
        return round(value / factor) * factor

    def calculate_trade_levels(self, technical_levels, daily_candles, intraday_data=None):
        """
        Calculates trade levels based on strategy.
        
        Args:
            technical_levels (dict): Output from TechnicalCalculator (4dHH, 4dLL, 2dHH, 2dLL).
            daily_candles (list): List of previous day candles [D1, D2..]. D1 is yesterday.
            intraday_data (dict): Optional. Contains 'open', 'high_915', 'low_915' for today.
                                  If None, specific Gap logic might not return actionable signals yet.
                                  
        Returns:
            dict: Trade plan details.
        """
        if not technical_levels or not daily_candles:
            logger.error("Missing technical levels or daily candles for trade calculation.")
            return None

        # Extract levels
        four_d_hh = technical_levels.get("4dHH")
        four_d_ll = technical_levels.get("4dLL")
        two_d_hh = technical_levels.get("2dHH")
        two_d_ll = technical_levels.get("2dLL")
        
        prev_day_high = daily_candles[0]['high']
        prev_day_low = daily_candles[0]['low']
        prev_day_close = daily_candles[0]['close']

        # --- BUY SIDE ---
        # "at 9:00:05 AM, get the entry price."
        # Standard Entry: MROUND(4dHH * (1 + 0.12%), 1)
        buy_entry_raw = four_d_hh * (1 + 0.0012)
        buy_entry = self.mround(buy_entry_raw, 1)

        buy_gap_up = False
        buy_entry_condition = "Standard"
        
        # Gap Up Logic
        if intraday_data:
            today_open = intraday_data.get('open')
            # Gap Up: Open > Buy Entry
            if today_open and buy_entry and today_open > buy_entry:
                buy_gap_up = True
                buy_entry_condition = "Gap Up (Wait for 9:15 Breakout)"
                
                # "enter only after 9 15 AM when the price hit MROUND(day high at 9:15 * (1 + 0.12%), 1)"
                day_high_915 = intraday_data.get('high_915')
                if day_high_915:
                     gap_buy_entry_raw = day_high_915 * (1 + 0.0012)
                     buy_entry = self.mround(gap_buy_entry_raw, 1)
                else:
                    buy_entry = None # Cannot calculate yet

        # Targets & SL for BUY
        # Target 1: MROUND(EntryPrice * (1 + 1.5%), 1)
        buy_target_1 = None
        buy_sl_1 = None
        buy_tsl_2nd_lot = None

        if buy_entry:
            buy_target_1 = self.mround(buy_entry * (1 + 0.015), 1)
            # Initial SL 1: MROUND(MAX(EntryPrice * (1 - 1.5%), 2dLL * (1 - 0.12%)), 1)
            sl_choice_1 = buy_entry * (1 - 0.015)
            sl_choice_2 = two_d_ll * (1 - 0.0012)
            buy_sl_1 = self.mround(max(sl_choice_1, sl_choice_2), 1)
            
            # Trailing Stop Loss (TSL) for 2nd Lot: MROUND(MAX(EntryPrice * (1 - 1.5%), 4dLL * (1 - 0.12%)), 1)
            tsl_choice_1 = buy_entry * (1 - 0.015)
            tsl_choice_2 = four_d_ll * (1 - 0.0012)
            buy_tsl_2nd_lot = self.mround(max(tsl_choice_1, tsl_choice_2), 1)


        # --- SELL SIDE ---
        # "sell side entry price is MROUND(4dLL * (1 - 0.12%), 1)"
        sell_entry_raw = four_d_ll * (1 - 0.0012)
        sell_entry = self.mround(sell_entry_raw, 1)
        
        sell_gap_down = False
        sell_entry_condition = "Standard"

        # Gap Down Handling
        if intraday_data:
            today_open = intraday_data.get('open')
            # Gap Down: Open < Sell Entry
            if today_open and sell_entry and today_open < sell_entry:
                sell_gap_down = True
                sell_entry_condition = "Gap Down (Wait for 9:15 Breakout)"
                
                # "use: MROUND(day low at 9:15AM * (1 - 0.12%), 1)."
                day_low_915 = intraday_data.get('low_915')
                if day_low_915:
                    gap_sell_entry_raw = day_low_915 * (1 - 0.0012)
                    sell_entry = self.mround(gap_sell_entry_raw, 1)
                else:
                    sell_entry = None

        # Targets & SL for SELL
        # Target 1 : MROUND(EntryPrice * (1 - 1.5%), 1)
        sell_target_1 = None
        sell_sl_1 = None
        sell_tsl_2nd_lot = None

        if sell_entry:
            sell_target_1 = self.mround(sell_entry * (1 - 0.015), 1)
            # Stop Loss (SL) 1: MROUND(MIN(EntryPrice * (1 + 1.5%), 2dHH * (1 + 0.12%)), 1)
            sell_sl_choice_1 = sell_entry * (1 + 0.015)
            sell_sl_choice_2 = two_d_hh * (1 + 0.0012)
            sell_sl_1 = self.mround(min(sell_sl_choice_1, sell_sl_choice_2), 1)
            
            # Trailing Stop Loss (TSL) for 2nd Lot: MROUND(MIN(EntryPrice * (1 + 1.5%), 4dHH * (1 + 0.12%)), 1)
            sell_tsl_choice_1 = sell_entry * (1 + 0.015)
            sell_tsl_choice_2 = four_d_hh * (1 + 0.0012)
            sell_tsl_2nd_lot = self.mround(min(sell_tsl_choice_1, sell_tsl_choice_2), 1)

        return {
            "BUY": {
                "entry": buy_entry,
                "condition": buy_entry_condition,
                "gap_up": buy_gap_up,
                "target_1": buy_target_1,
                "sl_1": buy_sl_1,
                "tsl_2nd_lot": buy_tsl_2nd_lot
            },
            "SELL": {
                "entry": sell_entry,
                "condition": sell_entry_condition,
                "gap_down": sell_gap_down,
                "target_1": sell_target_1,
                "sl_1": sell_sl_1,
                "tsl_2nd_lot": sell_tsl_2nd_lot
            }
        }
