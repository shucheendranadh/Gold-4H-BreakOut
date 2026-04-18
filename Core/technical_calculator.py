
class TechnicalCalculator:
    def calculate_levels(self, candles):
        """
        Calculates 4-Day and 2-Day Highs/Lows.
        
        Args:
            candles (list): List of candle dictionaries. 
                            Expected order: Newest first [D1, D2, D3, D4, ...]
        """
        if not candles or len(candles) < 4:
            return None
            
        d1 = candles[0]
        d2 = candles[1]
        d3 = candles[2]
        d4 = candles[3]
        
        # 4dHH: max(D1.High, D2.High, D3.High, D4.High)
        four_day_highs = [d1['high'], d2['high'], d3['high'], d4['high']]
        four_day_hh = max(four_day_highs)
        
        # 4dLL: min(D1.Low, D2.Low, D3.Low, D4.Low)
        four_day_lows = [d1['low'], d2['low'], d3['low'], d4['low']]
        four_day_ll = min(four_day_lows)
        
        # 2dHH (High of Days 3 & 4)
        two_day_highs = [d3['high'], d4['high']]
        two_day_hh = max(two_day_highs)
        
        # 2dLL (Low of Days 3 & 4)
        two_day_lows = [d3['low'], d4['low']]
        two_day_ll = min(two_day_lows)
        
        return {
            "4dHH": four_day_hh,
            "4dLL": four_day_ll,
            "2dHH": two_day_hh,
            "2dLL": two_day_ll
        }

    def calculate_ema(self, prices, period):
        """Calculates Exponential Moving Average."""
        if len(prices) < period:
            return None
        
        # Simple implementation: Start with SMA as first EMA value
        sma = sum(prices[:period]) / period
        ema = sma
        multiplier = 2 / (period + 1)
        
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        return round(ema, 2)

    def calculate_rsi(self, prices, period=14):
        """Calculates Relative Strength Index."""
        if len(prices) < period + 1:
            return None
        
        deltas = []
        for i in range(1, len(prices)):
            deltas.append(prices[i] - prices[i-1])
            
        avg_gain = sum([d for d in deltas[:period] if d > 0]) / period
        avg_loss = sum([-d for d in deltas[:period] if d < 0]) / period
        
        if avg_loss == 0:
            return 100
            
        for i in range(period, len(deltas)):
            delta = deltas[i]
            gain = delta if delta > 0 else 0
            loss = -delta if delta < 0 else 0
            
            avg_gain = (avg_gain * (period - 1) + gain) / period
            avg_loss = (avg_loss * (period - 1) + loss) / period
            
        if avg_loss == 0:
            return 100
            
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return round(rsi, 2)

    def detect_structure(self, candles):
        """
        Detects if current structure is Bullish (HH/HL) or Bearish (LH/LL).
        Expects candles ordered Newest First [D1, D2, D3, D4].
        """
        if len(candles) < 3:
            return "Neutral"
            
        # D1=current/prev, D2=2nd, D3=3rd
        h1, l1 = candles[0]['high'], candles[0]['low']
        h2, l2 = candles[1]['high'], candles[1]['low']
        h3, l3 = candles[2]['high'], candles[2]['low']
        
        is_hh = h1 > h2 > h3
        is_hl = l1 > l2 > l3
        is_lh = h1 < h2 < h3
        is_ll = l1 < l2 < l3
        
        if is_hh and is_hl:
            return "Bullish"
        if is_lh and is_ll:
            return "Bearish"
        return "Range"

    def detect_vwap(self, intraday_candles):
        """Calculates standard VWAP for the given candles."""
        if not intraday_candles:
            return None
        
        total_pv = 0
        total_v = 0
        for c in intraday_candles:
            v = c.get('volume', 0)
            if v == 0: continue
            avg_p = (c['high'] + c['low'] + c['close']) / 3
            total_pv += (avg_p * v)
            total_v += v
            
        if total_v == 0:
            return None
        return round(total_pv / total_v, 2)
