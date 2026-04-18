import logging
from Core.technical_calculator import TechnicalCalculator

logger = logging.getLogger("GOLD_MARKET")

class ConfidenceScorer:
    def __init__(self):
        self.calc = TechnicalCalculator()

    def calculate_scores(self, comex_data, usdinr_data, mcx_data):
        """
        Calculates Buy and Sell confidence scores based on provided data.
        
        comex_data: { 'current_price', 'candles', 'closes' }
        usdinr_data: list of closes (oldest first)
        mcx_data: { 'current_price', 'candles', 'levels', 'intraday_candles' }
        """
        buy_score = 0
        sell_score = 0
        
        # --- 1. COMEX GOLD (45%) ---
        comex_buy = 0
        comex_sell = 0
        
        if comex_data:
            price = comex_data['current_price']
            closes = comex_data['closes']
            candles = comex_data['candles']
            
            # Trend (15%)
            ema20 = self.calc.calculate_ema(closes, 20)
            ema50 = self.calc.calculate_ema(closes, 50)
            
            if price is not None and ema20 is not None and ema50 is not None:
                if price > ema20 and price > ema50: comex_buy += 15
                if price < ema20 and price < ema50: comex_sell += 15
            
            # Structure (10%)
            structure = self.calc.detect_structure(candles)
            if structure == "Bullish": comex_buy += 10
            if structure == "Bearish": comex_sell += 10
            
            # Breakout/Breakdown (10%)
            prev_high = candles[1]['high'] if len(candles) > 1 else None
            prev_low = candles[1]['low'] if len(candles) > 1 else None
            if price is not None and prev_high is not None and prev_low is not None:
                if price > prev_high: comex_buy += 10
                if price < prev_low: comex_sell += 10
            
            # RSI (5%)
            rsi = self.calc.calculate_rsi(closes, 14)
            if rsi is not None:
                if 55 <= rsi <= 70: comex_buy += 5
                if rsi < 45: comex_sell += 5
            
            # VWAP (5%)
            vwap = self.calc.detect_vwap(candles[:5]) 
            if price is not None and vwap is not None:
                if price > vwap: comex_buy += 5
                if price < vwap: comex_sell += 5
                
        # --- 2. USDINR (25%) ---
        usd_buy = 0
        usd_sell = 0
        
        if usdinr_data:
            usd_price = usdinr_data[-1]
            usd_ema20 = self.calc.calculate_ema(usdinr_data, 20)
            
            if usd_price is not None and usd_ema20 is not None:
                if usd_price > usd_ema20: usd_buy += 15
                if usd_price < usd_ema20: usd_sell += 15
                
                # Momentum (10%)
                if len(usdinr_data) > 1:
                    prev_usd = usdinr_data[-2]
                    if prev_usd is not None:
                        if usd_price >= prev_usd: usd_buy += 10
                        if usd_price < prev_usd: usd_sell += 10

        # --- 3. MCX (30%) ---
        mcx_buy = 0
        mcx_sell = 0
        
        if mcx_data:
            mcx_price = mcx_data['current_price']
            mcx_candles = mcx_data.get('candles', []) 
            mcx_intraday = mcx_data.get('intraday_candles', [])
            
            # Daily EMA 50 Trend (10%)
            if mcx_candles:
                closes_mcx = [c['close'] for c in reversed(mcx_candles)] 
                mcx_ema50 = self.calc.calculate_ema(closes_mcx, 50)
                if mcx_price is not None and mcx_ema50 is not None:
                    if mcx_price > mcx_ema50: mcx_buy += 10
                    if mcx_price < mcx_ema50: mcx_sell += 10
            
            # 20 EMA Pullback (10%)
            if mcx_intraday:
                intra_closes = [c['close'] for c in mcx_intraday]
                mcx_ema20_intra = self.calc.calculate_ema(intra_closes, 20)
                if mcx_price is not None and mcx_ema20_intra is not None and mcx_ema20_intra != 0:
                    dist = (mcx_price - mcx_ema20_intra) / mcx_ema20_intra
                    if 0 < dist < 0.002: mcx_buy += 10
                    if -0.002 < dist < 0: mcx_sell += 10
            
            # Swing Breakout/Breakdown (10%)
            levels = mcx_data.get('levels', {})
            if levels and mcx_price is not None:
                h = levels.get('4dHH')
                l = levels.get('4dLL')
                if h is not None and mcx_price > h: mcx_buy += 10
                if l is not None and mcx_price < l: mcx_sell += 10

        total_buy = comex_buy + usd_buy + mcx_buy
        total_sell = comex_sell + usd_sell + mcx_sell
        
        return {
            "buy_confidence": total_buy,
            "sell_confidence": total_sell,
            "details": {
                "comex": {"buy": comex_buy, "sell": comex_sell},
                "usdinr": {"buy": usd_buy, "sell": usd_sell},
                "mcx": {"buy": mcx_buy, "sell": mcx_sell}
            }
        }
