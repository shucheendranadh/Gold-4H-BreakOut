
import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from config import UPSTOX_ACCESS_TOKEN, MARKET_START_TIME
from DataLoader.historical_data_loader import HistoricalDataFetcher

# Setup Logging
import logging
logging.basicConfig(level=logging.INFO)

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)
    
    avg_gain = gain.rolling(window=period, min_periods=period).mean() # Use simple mean for initial
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    
    # We will use simple SMA RSI for estimation if Wilder is complex to debug one-shot
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_adx_simple(high, low, close, period=14):
    # Simplified ATR
    tr1 = abs(high - low)
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    
    # DM
    up = high - high.shift(1)
    down = low.shift(1) - low
    
    plus_dm = np.where((up > down) & (up > 0), up, 0)
    minus_dm = np.where((down > up) & (down > 0), down, 0)
    
    plus_dm = pd.Series(plus_dm, index=high.index)
    minus_dm = pd.Series(minus_dm, index=high.index)
    
    p_di = 100 * (plus_dm.rolling(period).mean() / atr)
    m_di = 100 * (minus_dm.rolling(period).mean() / atr)
    
    dx = 100 * abs(p_di - m_di) / (p_di + m_di)
    adx = dx.rolling(period).mean()
    
    return adx, p_di, m_di

def check_indicators():
    fetcher = HistoricalDataFetcher()
    instrument_token = "MCX_FO|472784" 
    
    print("\n--- FETCHING DATA FOR FEB 01-12 (Extended) ---")
    candles = fetcher.fetch_candles_range(
        instrument_token, 
        "2026-02-01", 
        "2026-02-12", 
        interval="30minute" 
    )
    
    if not candles:
        print("No candles returned.")
        return

    df = pd.DataFrame(candles)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    if df['timestamp'].dt.tz is not None:
        df['timestamp'] = df['timestamp'].dt.tz_localize(None)
        
    df = df.set_index('timestamp').sort_index()
    
    print(f"Total 30min Candles: {len(df)}")
    
    # Resample to 4H
    df_4h = df.resample('4h', offset='9h').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last'
    }).dropna()
    
    print(f"Total 4H Candles: {len(df_4h)}")
    
    # Calculate Indicators
    df_4h['rsi'] = calculate_rsi(df_4h['close'])
    adx, pdi, mdi = calculate_adx_simple(df_4h['high'], df_4h['low'], df_4h['close'])
    df_4h['adx'] = adx
    df_4h['plus_di'] = pdi
    df_4h['minus_di'] = mdi
    
    print("\n--- 4H DATA TAIL ---")
    print(df_4h.tail(10))
    
    target_date = "2026-02-10"
    print(f"\n--- DATA FOR {target_date} ---")
    print(df_4h[df_4h.index.astype(str).str.contains(target_date)])

if __name__ == "__main__":
    check_indicators()
