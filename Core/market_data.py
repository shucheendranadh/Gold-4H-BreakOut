import logging
from datetime import datetime, timedelta
from DataLoader.historical_data_loader import HistoricalDataFetcher

logger = logging.getLogger("GOLD_MARKET")

class MarketData:
    def __init__(self):
        self.fetcher = HistoricalDataFetcher()

    def get_session_high_low(self, instrument_token, start_time_str, end_time_str):
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            from_date = f"{today_str} {start_time_str}:00"
            to_date   = f"{today_str} {end_time_str}:00"

            logger.info(f"Fetching session data for {instrument_token} from {from_date} to {to_date}")
            candles = self.fetcher.fetch_candles_range(instrument_token, from_date, to_date, interval="1minute")

            if not candles:
                logger.error(f"No data returned for {from_date} - {to_date}")
                return None, None

            session_high = max(c['high'] for c in candles)
            session_low  = min(c['low']  for c in candles)

            logger.info(f"Session {start_time_str}-{end_time_str} -> High: {session_high}, Low: {session_low}")
            return session_high, session_low

        except Exception as e:
            logger.error(f"Error executing get_session_high_low: {e}", exc_info=True)
            return None, None

    def get_yesterday_high_low(self, instrument_token):
        try:
            candles = self.fetcher.fetch_previous_trading_days(instrument_token, days=5)
            if not candles:
                return None, None

            candles_sorted = sorted(candles, key=lambda c: c['timestamp'])
            prev = candles_sorted[-1]
            return prev['high'], prev['low']

        except Exception as e:
            logger.error(f"Error fetching Yesterday's High/Low: {e}", exc_info=True)
            return None, None

    def get_last_n_candles_4h(self, instrument_token, n=4):
        try:
            candles = self.fetcher.fetch_previous_trading_days(
                instrument_token, days=3, interval="30minute", include_today=True
            )
            if not candles:
                logger.error("No historical data fetched for 4H aggregation.")
                return []

            buckets = {}
            for c in candles:
                ts_str = c['timestamp']
                try:
                    dt_part = ts_str.split('+')[0].split('.')[0]
                    dt = datetime.strptime(dt_part, "%Y-%m-%dT%H:%M:%S") if 'T' in dt_part \
                         else datetime.strptime(dt_part, "%Y-%m-%d %H:%M:%S")
                except Exception:
                    continue

                h = dt.hour
                if h < 9:
                    prev = dt.date() - timedelta(days=1)
                    bucket_start = datetime(prev.year, prev.month, prev.day, 21, 0)
                elif h < 13:
                    bucket_start = datetime(dt.year, dt.month, dt.day, 9, 0)
                elif h < 17:
                    bucket_start = datetime(dt.year, dt.month, dt.day, 13, 0)
                elif h < 21:
                    bucket_start = datetime(dt.year, dt.month, dt.day, 17, 0)
                else:
                    bucket_start = datetime(dt.year, dt.month, dt.day, 21, 0)

                if bucket_start not in buckets:
                    buckets[bucket_start] = {'high': c['high'], 'low': c['low']}
                else:
                    if c['high'] > buckets[bucket_start]['high']:
                        buckets[bucket_start]['high'] = c['high']
                    if c['low'] < buckets[bucket_start]['low']:
                        buckets[bucket_start]['low'] = c['low']

            now = datetime.now()
            completed = [
                {'high': v['high'], 'low': v['low'], 'start': k}
                for k, v in sorted(buckets.items())
                if k + timedelta(hours=4) <= now
            ]
            return completed[-n:]

        except Exception as e:
            logger.error(f"Error fetching last {n} 4H candles: {e}", exc_info=True)
            return []
