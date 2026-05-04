from datetime import datetime, timedelta
import logging
import requests
from config import get_access_token, UPSTOX_ACCESS_TOKEN, UPSTOX_HISTORICAL_CANDLE_URL, UPSTOX_MARKET_QUOTE_URL

logger = logging.getLogger("GOLD_MAIN")

class HistoricalDataFetcher:
    def __init__(self):
        self.base_url = UPSTOX_HISTORICAL_CANDLE_URL
        self._ltp_err_logged_at = None   # rate-limit repeated LTP error logs
        self._ltp_err_status = None

    def fetch_previous_trading_days(self, instrument_key, days=4, interval="day", include_today=False):
        """
        Fetches historical candle data for the given instrument key.
        Returns the last `days` trading candles strictly BEFORE today (unless include_today=True).
        """
        #instrument_key = "MCX_FO|472782"
        if not get_access_token():
            logger.error("UPSTOX_ACCESS_TOKEN not set.")
            return []

        today = datetime.now()
        # Fetch enough data to cover weekends/holidays. 15 days should be safe for 4 trading days.
        # Calculate date range
        # We want to go back enough to find X trading days. 
        # Simple heuristic: 1 trading day ~= 1.5 calendar days (weekends).
        # Safety margin: days * 2 (Reduced from 5 to avoid 400 Bad Request on 30min data)
        lookback_days = max(days * 2 + 2, 7) # Min 7 days, max dependent on request
        from_date = today - timedelta(days=lookback_days)
        
        to_date_str = today.strftime("%Y-%m-%d")
        from_date_str = from_date.strftime("%Y-%m-%d")
        
        # URL construction: {instrumentKey}/{interval}/{to_date}/{from_date}
        # interval = 'days' (from requirements: D1=Previous Day...)
        # Upstox V3 API expects format: {instrument_key}/{interval_unit}/{interval_value}/{to_date}/{from_date}
        # Example from docs: .../days/1/2025-03-01/2025-01-01
        
        # URL encode instrument_key to handle special characters like '|'
        from urllib.parse import quote
        safe_key = quote(instrument_key)
        
        if interval == "day":
             url = f"{self.base_url}/{safe_key}/days/1/{to_date_str}/{from_date_str}"
        elif interval == "week":
             url = f"{self.base_url}/{safe_key}/weeks/1/{to_date_str}/{from_date_str}"
        elif interval == "month":
             url = f"{self.base_url}/{safe_key}/months/1/{to_date_str}/{from_date_str}"
        elif interval == "1minute":
             # V3 Format: /minutes/1
             url = f"{self.base_url}/{safe_key}/minutes/1/{to_date_str}/{from_date_str}"
        elif interval == "30minute":
             # V3 Format: /minutes/30
             url = f"{self.base_url}/{safe_key}/minutes/30/{to_date_str}/{from_date_str}"
        else:
             # Default fallback
             url = f"{self.base_url}/{safe_key}/{interval}/{to_date_str}/{from_date_str}"
        
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {get_access_token()}'
        }

        try:
            cleaned_candles = []
            
            # 1. Fetch Historical Data (V3)
            try:
                logger.info(f"Fetching V3 Historical data from {from_date_str} to {to_date_str}")
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                if data.get("status") == "success" and data.get("data") and data.get("data", {}).get("candles"):
                    hist_candles = data["data"]["candles"]
                    for c in hist_candles:
                         ts_str = c[0]
                         cleaned_candles.append({
                             "timestamp": ts_str,
                             "date": datetime.strptime(ts_str.split('T')[0], "%Y-%m-%d").date(),
                             "open": c[1], "high": c[2], "low": c[3], "close": c[4], "volume": c[5], "oi": c[6]
                         })
            except Exception as e:
                logger.error(f"V3 Historical Fetch Failed: {e}")

            # 2. Fetch Intraday Data (V2) - ONLY if interval is minute-based
            if interval in ["1minute", "30minute"]:
                try:
                    v2_intraday_url = "https://api.upstox.com/v2/historical-candle/intraday"
                    # Determine interval string
                    v2_int_val = "1minute" if interval == "1minute" else "30minute"
                    v2_url = f"{v2_intraday_url}/{safe_key}/{v2_int_val}"
                    
                    logger.info(f"Fetching V2 Intraday data from {v2_url}")
                    resp_v2 = requests.get(v2_url, headers=headers)
                    if resp_v2.status_code == 200:
                        data_v2 = resp_v2.json()
                        if data_v2.get("data") and data_v2.get("data", {}).get("candles"):
                            intra_candles = data_v2["data"]["candles"]
                            for c in intra_candles:
                                 ts_str = c[0]
                                 cleaned_candles.append({
                                     "timestamp": ts_str,
                                     "date": datetime.strptime(ts_str.split('T')[0], "%Y-%m-%d").date(),
                                     "open": c[1], "high": c[2], "low": c[3], "close": c[4], "volume": c[5], "oi": c[6]
                                 })
                except Exception as e:
                    logger.error(f"V2 Intraday Fetch Failed: {e}")
            
            # 3. Deduplicate and Sort
            seen = set()
            final_candles = []
            for c in cleaned_candles:
                if c['timestamp'] not in seen:
                    seen.add(c['timestamp'])
                    final_candles.append(c)

            final_candles.sort(key=lambda x: x["timestamp"], reverse=True)

            if interval == "day":
                final_candles = final_candles[:days]

            return final_candles

        except Exception as e:
            logger.error(f"Error fetching historical data: {e}")
            return []

    def fetch_candles_range(self, instrument_key, from_date, to_date, interval="1minute"):
        """
        Fetches historical candles for a specific date range.
        Wrapper for Upstox Historical Candle API.
        
        Args:
            from_date (str): "YYYY-MM-DD" or "YYYY-MM-DD HH:MM:SS" (Will be formatted)
            to_date (str): "YYYY-MM-DD" or "YYYY-MM-DD HH:MM:SS"
            interval (str): "1minute", "30minute", "day", etc.
        """
        if not get_access_token():
             return []

        # Format dates for API (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS is accepted? Docs say YYYY-MM-DD for From/To usually)
        # However, for minute data, date-based URL works. Upstox filters within that?
        # Standard URL: {instrumentKey}/{interval}/{to_date}/{from_date}
        # Based on docs, inputs are strings YYYY-MM-DD.
        # But for intraday minute data, we might need timestamps?
        # Actually, Upstox API v3 uses YYYY-MM-DD for the path parameters.
        # It returns FULL DAYS of data for those days. We must filter locally.
        
        # Validating Input format: If full timestamp passed, extract Date.
        # But if we need 'Today 9am to Today 1pm', we can just pass Today.
        
        # Try exact from/to from args first.
        # Since the URL structure is .../to_date/from_date
        # Let's clean them to YYYY-MM-DD if they are longer
        
        to_date_str = to_date.split(" ")[0]
        from_date_str = from_date.split(" ")[0]
        
        from urllib.parse import quote
        safe_key = quote(instrument_key)

        if interval == "day":
             url = f"{self.base_url}/{safe_key}/days/1/{to_date_str}/{from_date_str}"
        elif interval == "week":
             url = f"{self.base_url}/{safe_key}/weeks/1/{to_date_str}/{from_date_str}"
        elif interval == "month":
             url = f"{self.base_url}/{safe_key}/months/1/{to_date_str}/{from_date_str}"
        elif interval == "1minute":
             # V3 Format: /minutes/1
             url = f"{self.base_url}/{safe_key}/minutes/1/{to_date_str}/{from_date_str}"
        elif interval == "30minute":
             # V3 Format: /minutes/30
             url = f"{self.base_url}/{safe_key}/minutes/30/{to_date_str}/{from_date_str}"
        else:
             # Default fallback
             url = f"{self.base_url}/{safe_key}/{interval}/{to_date_str}/{from_date_str}"
        
        headers = { 'Accept': 'application/json', 'Authorization': f'Bearer {get_access_token()}' }
        
        all_raw_candles = []
        
        # 1. Fetch Historical Data (V3)
        try:
            logger.info(f"Fetching V3 Historical data: {url}")
            response = requests.get(url, headers=headers)
            # 400 likely if data not found, but we want to continue to V2
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success" and data.get("data") and data.get("data", {}).get("candles"):
                     all_raw_candles.extend(data["data"]["candles"])
            else:
                 logger.warning(f"V3 Historical Fetch returned status {response.status_code}")
        except Exception as e:
            logger.error(f"V3 Historical Fetch Failed: {e}")

        # 2. Fetch Intraday Data (V2) - For Minute Data
        if interval in ["1minute", "30minute"]:
            try:
                v2_intraday_url = "https://api.upstox.com/v2/historical-candle/intraday"
                v2_int_val = "1minute" if interval == "1minute" else "30minute" # V2 supports these
                v2_url = f"{v2_intraday_url}/{safe_key}/{v2_int_val}"
                
                logger.info(f"Fetching V2 Intraday data: {v2_url}")
                resp_v2 = requests.get(v2_url, headers=headers)
                if resp_v2.status_code == 200:
                    data_v2 = resp_v2.json()
                    if data_v2.get("data") and data_v2.get("data", {}).get("candles"):
                        all_raw_candles.extend(data_v2["data"]["candles"])
            except Exception as e:
                logger.error(f"V2 Intraday Fetch Failed: {e}")

        # 3. Process, De-duplicate and Filter
        cleaned = []
        seen_timestamps = set()
        
        # Parse filter timestamps
        # Handle formats carefully
        def parse_dt(dt_str):
             if " " in dt_str:
                 return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
             return datetime.strptime(dt_str, "%Y-%m-%d")
             
        from_dt = parse_dt(from_date)
        to_dt = parse_dt(to_date)
        
        for c in all_raw_candles:
            ts_str = c[0]
            if ts_str in seen_timestamps:
                continue
            seen_timestamps.add(ts_str)
            
            # Parse candle timestamp
            # Format: 2023-01-01T09:00:00+05:30
            try:
                if "T" in ts_str:
                     dt_part = ts_str.split("+")[0]
                     c_dt = datetime.strptime(dt_part, "%Y-%m-%dT%H:%M:%S")
                else:
                     c_dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                
                # Filter Logic
                if c_dt >= from_dt and c_dt <= to_dt:
                    cleaned.append({
                        "timestamp": ts_str,
                        "open": c[1],
                        "high": c[2],
                        "low": c[3],
                        "close": c[4],
                        "volume": c[5],
                        "oi": c[6]
                    })
            except Exception as e:
                 logger.warning(f"Error parsing candle timestamp {ts_str}: {e}")
                 continue

        # Sort ascending
        cleaned.sort(key=lambda x: x["timestamp"])
        return cleaned

    def fetch_intraday_candles(self, instrument_key, interval="1minute"):
        """
        Fetches intraday (1minute) candles for the current trading day.
        Used to get 'today's' data for Gap detection.
        """
        if not get_access_token():
            logger.error("UPSTOX_ACCESS_TOKEN not set.")
            return []

        # URL construction: {instrumentKey}/1minute (for today's intraday)
        from urllib.parse import quote
        safe_key = quote(instrument_key)
        
        # Correct Intraday Format for V3: /intraday/{instrument_key}/minutes/1
        # Correct Intraday Format for V3: /intraday/{instrument_key}/minutes/1
        # If interval is passed, we might need to adjust logic, but mostly used for 1minute gaps.
        # But if 'interval' arg is passed as "1minute", it works.
        # If the caller passes something else, we might need a mapping.
        
        # Upstox Intraday API specific: /intraday/{instrument_key}/minutes/{interval}
        if interval == "1minute":
            url = f"{self.base_url}/intraday/{safe_key}/minutes/1"
        else:
            # Fallback or other intervals if supported by API
             url = f"{self.base_url}/intraday/{safe_key}/minutes/1"
        
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {get_access_token()}'
        }

        try:
            logger.info(f"Fetching live intraday data for {instrument_key}")
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "success" and data.get("data") and data.get("data", {}).get("candles"):
                candles = data["data"]["candles"]
                cleaned_candles = []
                
                for c in candles:
                    # Format: [Timestamp, Open, High, Low, Close, Volume, OI]
                    ts_str = c[0]
                    # Parse simplified
                    # 2025-01-01T09:15:00+05:30
                    cleaned_candles.append({
                        "timestamp": ts_str,
                        "open": c[1],
                        "high": c[2],
                        "low": c[3],
                        "close": c[4],
                        "volume": c[5],
                        "oi": c[6]
                    })
                
                # Sort chronological (oldest first) to easily find Open
                cleaned_candles.sort(key=lambda x: x["timestamp"])
                
                return cleaned_candles
            else:
                return []

        except Exception as e:
            logger.error(f"Error fetching intraday data: {e}")
            return []

    def _get_quote_data(self, response_json, instrument_key):
        """
        Helper to find quote data in response using case-insensitive key or instrument token.
        """
        data_map = response_json.get("data", {})
        if not data_map:
            return {}

        # 1. Exact match
        if instrument_key in data_map:
            return data_map[instrument_key]

        # 2. Case-insensitive and prefix/token match
        try:
            target_token = instrument_key.split('|')[-1]
            for key, val in data_map.items():
                # Check if token matches (numeric part)
                if key.endswith(f"|{target_token}"):
                    logger.info(f"Instrument key mismatch handled: Requested '{instrument_key}', found '{key}'.")
                    return val
        except Exception:
            pass

        # 3. Last resort fallback: if only one instrument in response, use it
        if len(data_map) == 1:
            key = list(data_map.keys())[0]
            logger.debug(f"Single instrument fallback: Using data for '{key}' instead of '{instrument_key}'.")
            return data_map[key]

        return {}

    def fetch_ltp(self, instrument_key):
        """
        Fetches the current Last Traded Price (LTP) using the Market Quote API.
        """
        if not get_access_token():
            return None

        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {get_access_token()}'
        }
        params = {'instrument_key': instrument_key}

        try:
            response = requests.get(UPSTOX_MARKET_QUOTE_URL, headers=headers, params=params)

            if response.status_code == 401:
                now = datetime.now()
                if self._ltp_err_status != 401 or self._ltp_err_logged_at is None or \
                        (now - self._ltp_err_logged_at).total_seconds() > 300:
                    logger.error("Upstox token expired (401 Unauthorized). Please refresh the access token in the token file.")
                    self._ltp_err_logged_at = now
                    self._ltp_err_status = 401
                return None

            # Reset error tracking on successful response
            self._ltp_err_status = None
            self._ltp_err_logged_at = None

            response.raise_for_status()
            data = response.json()

            if data.get("status") == "success":
                quote_data = self._get_quote_data(data, instrument_key)
                ltp = quote_data.get("last_price")
                return ltp
            return None
        except Exception as e:
            now = datetime.now()
            if self._ltp_err_logged_at is None or \
                    (now - self._ltp_err_logged_at).total_seconds() > 300:
                logger.error(f"Error fetching LTP: {e}")
                self._ltp_err_logged_at = now
                self._ltp_err_status = "other"
            return None

    def fetch_day_open(self, instrument_key):
        """
        Fetches the day's opening price using the Market Quote API.
        This is more reliable than candles immediately after market open.
        """
        if not get_access_token():
            logger.error("UPSTOX_ACCESS_TOKEN not set.")
            return None

        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {get_access_token()}'
        }
        params = {'instrument_key': instrument_key}
        
        try:
            logger.info(f"Fetching market quote for day open: {instrument_key}")
            response = requests.get(UPSTOX_MARKET_QUOTE_URL, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "success":
                quote_data = self._get_quote_data(data, instrument_key)
                ohlc = quote_data.get("ohlc", {})
                open_price = ohlc.get("open")
                
                if open_price and open_price > 0:
                    logger.info(f"Day Open detected via Quote API: {open_price}")
                    return open_price
                else:
                    logger.warning(f"Open price not yet available in Quote API (got {open_price}). Checking intraday candles...")
                    # Fallback to Intraday Candles
                    candles = self.fetch_intraday_candles(instrument_key)
                    if candles:
                        # Find the first candle of today
                        today_str = datetime.now().strftime("%Y-%m-%d")
                        for candle in candles:
                            if candle['timestamp'].startswith(today_str):
                                day_open = candle['open']
                                logger.info(f"Day Open detected via Intraday Candle fallback: {day_open}")
                                return day_open
                    
                    logger.warning(f"Open price not available via Intraday Candles for {instrument_key} either.")
                    return None
            else:
                logger.error(f"Quote API Error: {data}")
                return None
        except Exception as e:
            logger.error(f"Error fetching day open from Quote API: {e}")
            return None
