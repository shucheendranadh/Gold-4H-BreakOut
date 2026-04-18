import requests
import logging
from config import USD_INR_URL

logger = logging.getLogger("GOLD_MARKET")

class CurrencyDataLoader:
    def __init__(self):
        self.url = USD_INR_URL
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def fetch_usdinr_data(self):
        """
        Fetches USDINR data from Yahoo Finance.
        Returns a list of closing prices.
        """
        try:
            response = requests.get(self.url, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            chart_data = data.get("chart", {}).get("result", [])[0]
            indicators = chart_data.get("indicators", {}).get("quote", [])[0]
            closes = [c for c in indicators.get("close", []) if c is not None]
            
            if not closes:
                logger.error("No USDINR data received.")
                return None

            return closes

        except Exception as e:
            logger.error(f"Error fetching USDINR data: {e}")
            return None
