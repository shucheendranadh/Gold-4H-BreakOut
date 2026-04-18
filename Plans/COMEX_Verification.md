# COMEX Gold Verification Plan

This document outlines the strategy for verifying MCX Gold breakout signals against international Gold (COMEX) momentum to filter out currency-driven volatility.

## Objective
Only place/keep MCX GTT orders active if the COMEX Gold market is showing synchronized momentum. This protects against "fake" breakouts caused purely by USDINR fluctuations.

## Core Logic
- **Buy Alignment**: MCX Buy Entry is valid ONLY IF `COMEX Price > COMEX 4-day High`.
- **Sell Alignment**: MCX Sell Entry is valid ONLY IF `COMEX Price < COMEX 4-day Low`.

## Technical Implementation

### 1. Data Fetching
A new module `DataLoader/comex_loader.py` will fetch `GC=F` (Gold Continuous Futures) data from Yahoo Finance.

```python
# API Endpoint
url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1d&range=5d"
```

### 2. Signal Validation
In `main.py`, before placing GTTs:
1. Fetch latest COMEX Price and calculated 4dHH/4dLL.
2. Compare MCX Trade Plan side with COMEX momentum.
3. If momentum is divergent (e.g., MCX Buy but COMEX below 4dHH), log the divergence and skip the trade.

## Logging & Transparency
All COMEX checks will be logged in `Logs/GOLD_MARKET.log` with clear labels:
- `COMEX Status: SYNCED (Both Bullish)`
- `COMEX Status: DIVERGENT (MCX Bullish / COMEX Neutral) -> TRADE SKIPPED.`

## Implementation Status
- [ ] Create `comex_loader.py`
- [ ] Integrate with `main.py`
- [ ] Add momentum validation logic
