import requests
import logging
import time
from datetime import datetime
from config import COMEX_DATA_URL

logger = logging.getLogger("GOLD_MARKET")

class ComexDataLoader:
    def __init__(self):
        self.symbol = "GC=F"  # Gold Continuous Futures
        self.url = COMEX_DATA_URL
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def fetch_comex_data(self):
        """
        Fetches last 5 days of COMEX Gold data.
        Returns a dict with 'current_price', '4dHH', and '4dLL'.
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"Fetching COMEX Gold data for {self.symbol} (Attempt {attempt+1}/{max_retries})...")
                response = requests.get(self.url, headers=self.headers, timeout=20)
                response.raise_for_status()
                data = response.json()

                chart_data = data.get("chart", {}).get("result", [])[0]
                indicators = chart_data.get("indicators", {}).get("quote", [])[0]
                
                # Highs/Lows/Closes
                highs = [h for h in indicators.get("high", []) if h is not None]
                lows = [l for l in indicators.get("low", []) if l is not None]
                
                if not highs or not lows:
                    logger.error("Incomplete COMEX data received.")
                    return None

                # 4-day High/Low (excluding the very latest candle if it's still 'today's' partial candle)
                # Actually, Yahoo '1d' with '5d' range usually gives 4 closed + 1 live.
                # We want the HH/LL of the 4 PREVIOUS candles.
                last_4_highs = highs[:-1] if len(highs) >= 5 else highs[:4]
                last_4_lows = lows[:-1] if len(lows) >= 5 else lows[:4]
                
                four_d_hh = max(last_4_highs)
                four_d_ll = min(last_4_lows)
                current_price = chart_data.get("meta", {}).get("regularMarketPrice")

                return {
                    "current_price": current_price,
                    "4dHH": four_d_hh,
                    "4dLL": four_d_ll
                }

            except requests.exceptions.RequestException as e:
                logger.warning(f"Network error fetching COMEX data (Attempt {attempt+1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff: 1, 2, 4s
            except Exception as e:
                logger.error(f"Error fetching COMEX data: {e}")
                return None
        
        logger.error("Max retries reached for COMEX data.")
        return None

    def check_breakout(self):
        """
        Returns True if LTP has broken 4dHH or 4dLL.
        """
        data = self.fetch_comex_data()
        if not data:
            return False

        price = data["current_price"]
        hh = data["4dHH"]
        ll = data["4dLL"]

        if price > hh or price < ll:
            logger.info(f"COMEX BREAKOUT DETECTED! LTP ({price}) vs Range ({ll} - {hh})")
            return True
        else:
            logger.info(f"COMEX Neutral. LTP ({price}) inside range ({ll} - {hh}).")
            return False

    def fetch_advanced_comex_data(self):
        """
        Fetches historical data for advanced indicators (EMA, RSI, VWAP).
        Uses a longer range defined in config.
        """
        from config import COMEX_DATA_URL_LONG
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Fetching Advanced COMEX Gold data (Attempt {attempt+1}/{max_retries})...")
                response = requests.get(COMEX_DATA_URL_LONG, headers=self.headers, timeout=20)
                response.raise_for_status()
                data = response.json()

                chart_data = data.get("chart", {}).get("result", [])[0]
                indicators = chart_data.get("indicators", {}).get("quote", [])[0]
                
                # Highs/Lows/Closes/Volumes
                highs = [h for h in indicators.get("high", []) if h is not None]
                lows = [l for l in indicators.get("low", []) if l is not None]
                closes = [c for c in indicators.get("close", []) if c is not None]
                volumes = [v for v in indicators.get("volume", []) if v is not None]
                
                if not highs or not lows or not closes:
                    logger.error("Incomplete advanced COMEX data received.")
                    return None

                # Create candle objects
                candles = []
                for i in range(len(closes)):
                    candles.append({
                        "high": highs[i],
                        "low": lows[i],
                        "close": closes[i],
                        "volume": volumes[i] if i < len(volumes) else 0
                    })

                # Return in newest-first order
                candles.reverse()
                
                return {
                    "current_price": chart_data.get("meta", {}).get("regularMarketPrice"),
                    "candles": candles,
                    "closes": closes # oldest first for indicator calculation
                }

            except requests.exceptions.RequestException as e:
                logger.warning(f"Network error fetching Advanced COMEX data (Attempt {attempt+1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"Error fetching advanced COMEX data: {e}")
                return None
        
        logger.error("Max retries reached for Advanced COMEX data.")
        return None
