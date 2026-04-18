import logging
import pandas as pd
from datetime import datetime
from DataLoader.historical_data_loader import HistoricalDataFetcher

logger = logging.getLogger("GOLD_MARKET")

class MarketData:
    def __init__(self):
        self.fetcher = HistoricalDataFetcher()

    def get_session_high_low(self, instrument_token, start_time_str, end_time_str):
        """
        Fetches historical data for the specified time window and returns the High and Low.
        
        Args:
            instrument_token (str): The instrument key.
            start_time_str (str): Start time in "HH:MM" format (Current Day).
            end_time_str (str): End time in "HH:MM" format (Current Day).
            
        Returns:
            tuple: (High, Low) or (None, None) if data is unavailable.
        """
        try:
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            
            from_date = f"{today_str} {start_time_str}:00"
            to_date = f"{today_str} {end_time_str}:00"
            
            logger.info(f"Fetching session data for {instrument_token} from {from_date} to {to_date}")
            
            # We use 1-minute candles for granularity
            candles = self.fetcher.fetch_candles_range(
                instrument_token, 
                from_date, 
                to_date, 
                interval="1minute"
            )
            
            if not candles:
                logger.error(f"No data returned for {from_date} - {to_date}")
                return None, None
            
            # Assuming fetcher returns list of dicts like {'date':..., 'open':..., 'high':..., 'low':..., 'close':...}
            # Or list of lists.
            # Based on main.py check:
            # "candles_formatted.append({'date':..., 'high': c['high']...})" implies list of dicts.
            
            df = pd.DataFrame(candles)
            if 'high' not in df.columns or 'low' not in df.columns:
                 logger.error(f"Data format unexpected. Columns: {df.columns}")
                 return None, None
            
            session_high = df['high'].max()
            session_low = df['low'].min()
            
            logger.info(f"Session {start_time_str}-{end_time_str} -> High: {session_high}, Low: {session_low}")
            return session_high, session_low

        except Exception as e:
            logger.error(f"Error executing get_session_high_low: {e}", exc_info=True)
            return None, None

    def get_yesterday_high_low(self, instrument_token):
        """
        Fetches Yesterday's High and Low.
        """
        try:
            candles = self.fetcher.fetch_previous_trading_days(
                instrument_token,
                days=5 
            )
             
            if not candles:
                return None, None
                
            df = pd.DataFrame(candles)
            if 'high' not in df.columns or 'low' not in df.columns:
                 return None, None
                 
            df = df.sort_values(by='timestamp') if 'timestamp' in df.columns else df
            
            # Assuming list of dicts for now
            # Last candle handling
            
            if len(df) < 1:
                # Need at least yesterday
                return None, None
                
            # fetch_previous_trading_days excludes "Today", so the last candle (-1) is "Yesterday"
            prev_candle = df.iloc[-1]
            
            return prev_candle['high'], prev_candle['low']
            
        except Exception as e:
            logger.error(f"Error fetching Yesterday's High/Low: {e}", exc_info=True)
            return None, None
    def get_last_n_candles_4h(self, instrument_token, n=4):
        """
        Fetches the last N completed 4H candles (High, Low).
        
        Args:
            instrument_token (str): Instrument Token
            n (int): Number of 4H candles to look back (default 4 for 4d logic adaptation)
            
        Returns:
            list of dict: [{'high': H, 'low': L, 'start': 'YYYY-MM-DD HH:MM'}, ...]
        """
        try:
            # Fetch data for last 3 days to cover weekends/holidays and ensure enough points
            # We must include TODAY'S data because 4H candles for today (09:00, 13:00) need to be formed.
            candles = self.fetcher.fetch_previous_trading_days(
                instrument_token,
                days=3,
                interval="30minute", # V3 API minutes/30 support confirmed
                include_today=True 
            )
            
            if not candles:
                logger.error("No historical data fetched for 4H aggregation.")
                return []
                
            df = pd.DataFrame(candles)
            if df.empty or 'timestamp' not in df.columns:
                return []
                
            # Convert timestamp to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Remove timezone info to match naive datetime.now()
            if df['timestamp'].dt.tz is not None:
                df['timestamp'] = df['timestamp'].dt.tz_localize(None)
                
            df.set_index('timestamp', inplace=True)
            df.sort_index(inplace=True)
            
            # Resample to 4H starting at 09:00
            # SESSIONS = ["09:00", "13:00", "17:00", "21:00"]
            # 4H blocks centered on these times.
            # Using '4h' offset. Base/Origin is commonly 00:00. 
            # 09:00 is +9h offset.
            
            df_4h = df.resample('4h', offset='9h').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last'
            }).dropna()
            
            # Filter out current forming candle?
            # If we are at 13:01, the 09:00-13:00 candle is "closed".
            # Resample labels usually use the *left* edge (start time).
            # So 09:00 row covers 09:00-13:00.
            
            # If current time is 11:00, 09:00 candle exists but is incomplete.
            # We only want COMPLETED candles.
            # Simple check: Candle End Time < Now.
            
            now = datetime.now()
            completed_candles = []
            
            for index, row in df_4h.iterrows():
                start_time = index
                end_time = start_time + pd.Timedelta(hours=4)
                
                # If the candle's FULL period is in the past, it's completed.
                # Allow a small buffer? No, strict.
                if end_time <= now:
                    completed_candles.append({
                        'high': row['high'],
                        'low': row['low'],
                        'start': start_time
                    })
            
            # Return last N
            return completed_candles[-n:]
            
        except Exception as e:
            logger.error(f"Error fetching last {n} 4H candles: {e}", exc_info=True)
            return []
