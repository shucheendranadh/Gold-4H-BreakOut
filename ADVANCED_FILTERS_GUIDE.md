# Advanced Filters & Confidence Scoring Guide

This document explains the technical logic behind the Advanced Filters and Confidence Scoring system for Gold Trading. This system runs as a "Shadow Monitor" (`advanced_monitor.py`) to provide high-level confirmation without interfering with the primary trading bot.

## 1. Core Philosophy

The system uses three layers of verification to calculate a **Confidence Score (0-100%)** for both **Buy** and **Sell** directions.

1.  **Macro Layer (COMEX Gold)**: The primary trend driver.
2.  **Currency Layer (USDINR)**: The secondary driver that can either amplify or dampen MCX movements.
3.  **Execution Layer (MCX Technicals)**: Specific price action and structure on the local exchange.

---

## 2. Confidence Scoring Logic

### A. Buy Confidence (Long Bias)
Calculated based on the following weights (Total 100%):

| Layer | Component | Weight | Condition |
| :--- | :--- | :--- | :--- |
| **COMEX** (45%) | Trend | 15% | Price > 20 EMA AND Price > 50 EMA |
| | Structure | 10% | Series of Higher Highs and Higher Lows |
| | Breakout | 10% | Price > Previous Day High (PDH) |
| | Momentum | 5% | RSI (14) between 55 and 70 |
| | VWAP | 5% | Price > Previous Week VWAP |
| **USDINR** (25%) | Trend | 15% | Price > 20 EMA |
| | Momentum | 10% | Trending Up or Stable during COMEX Bullishness |
| **MCX** (30%) | Support | 10% | Price > 50 EMA |
| | Entry | 10% | Pullback to 20 EMA + Bullish Confirmation |
| | Breakout | 10% | Breakout of recent Swing High |

### B. Sell Confidence (Short Bias)
Calculated based on the following weights (Total 100%):

| Layer | Component | Weight | Condition |
| :--- | :--- | :--- | :--- |
| **COMEX** (45%) | Trend | 15% | Price < 20 EMA AND Price < 50 EMA |
| | Structure | 10% | Series of Lower Highs and Lower Lows |
| | Breakdown | 10% | Price < Previous Day Low (PDL) |
| | Weakness | 5% | RSI (14) < 45 or RSI Divergence |
| | VWAP | 5% | Price < Previous Week VWAP |
| **USDINR** (25%) | Trend | 15% | Price < 20 EMA |
| | Momentum | 10% | Trending Down |
| **MCX** (30%) | Resistance | 10% | Price < 50 EMA |
| | Entry | 10% | Pullback to 20 EMA + Bearish Rejection |
| | Breakdown | 10% | Breakdown of recent Swing Low |

---

## 3. How to Use

1.  **Run the Monitor**:
    ```bash
    python advanced_monitor.py
    ```
2.  **Observe Logs**: The monitor will output the current Buy/Sell confidence levels every interval.
3.  **Thresholds**:
    - **Score > 75%**: Strong Trend (High Confidence).
    - **Score 50-75%**: Conservative Trend (Watch for volatility).
    - **Score < 50%**: Neutral or Mixed signals (Wait for alignment).

---

## 4. Technical Setup

- **Indicator Windows**: EMAs (20, 50), RSI (14), VWAP (Weekly).
- **Timeframes**: 4H or Daily for Trend; 15-min to 1H for MCX Execution patterns.
- **Data Sources**: Yahoo Finance (COMEX, USDINR) and Upstox (MCX).
