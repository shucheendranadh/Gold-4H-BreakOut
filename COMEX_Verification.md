# COMEX Gold Verification Plan

This document outlines the strategy for verifying MCX Gold breakout signals against international Gold (COMEX) momentum to filter out currency-driven volatility.

## Objective
Only place/keep MCX GTT orders active if the COMEX Gold market is showing synchronized momentum. This protects against "fake" breakouts caused purely by USDINR fluctuations.

## Configuration & Control
The system respects a feature flag in `config.py`:
- `ENABLE_COMEX_FILTER = True/False`: If set to `False`, the bot will skip the monitoring loop and place MCX GTTs immediately as per standard logic.

## Core Logic
- **Volatility-Based Gatekeeping**: MCX trades are "Armed" (both Buy and Sell GTTs placed) as soon as COMEX LTP breaks its 4-day consolidation range.
- **Trigger Condition**: If `COMEX LTP > COMEX 4-day High` OR `COMEX LTP < COMEX 4-day Low` -> **Place ALL MCX GTTs**.
- **Sticky Orders**: Once MCX GTTs are placed for the day, they remain active until triggered or the daily maintenance cleanup.

## Technical Implementation

### 1. Data Fetching
A new module `DataLoader/comex_loader.py` will fetch `GC=F` (Gold Continuous Futures) data from Yahoo Finance. This fetcher is only called if `ENABLE_COMEX_FILTER` is `True`.

```python
# API Endpoint
url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1d&range=5d"
```

### 2. Signal Validation (Volatility Trigger)
The script will run in a monitoring loop:
1. **Continuous Check**: Fetch latest COMEX LTP every 60 seconds (or on every run).
2. **Full Arming**: 
    - At the moment `COMEX LTP` breaks the 4-day High OR Low -> **Place both MCX Buy & Sell GTTs**.
3. **No Disarming**: After the "Gate" is opened by COMEX volatility, the orders stay pending at the exchange regardless of COMEX price action for the rest of the day.

## Logging & Transparency
All COMEX checks will be logged in `Logs/GOLD_MARKET.log` with clear labels:
- `COMEX Status: SYNCED (Both Bullish)`
- `COMEX Status: DIVERGENT (MCX Bullish / COMEX Neutral) -> TRADE SKIPPED.`

## Implementation Status
- [ ] Create `comex_loader.py`
- [ ] Integrate with `main.py`
- [ ] Add momentum validation logic
