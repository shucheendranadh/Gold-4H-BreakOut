# Gold Trading System Flowchart

This document outlines the execution flow of the integrated Gold Trading Bot, including Advanced Monitoring and Rollover capabilities.

```mermaid
graph TD
    Start([Execute main.py]) --> LoadState[Load trading_state.json]
    LoadState --> CheckGTT{GTT IDs Exist?}

    %% Path A: Maintenance
    CheckGTT -- Yes --> StaleCheck{Is State Stale?}
    StaleCheck -- Yes --> Cleanup[Cancel Prev. Day GTTs & Reset State]
    Cleanup --> DayOpenQuote
    StaleCheck -- No --> ActiveCheck{Active GTTs?}
    ActiveCheck -- No --> Cleanup
    ActiveCheck -- Yes --> Maintenance[Daily Maintenance Phase]
    Maintenance --> DetectTrigger{New Trigger?}
    DetectTrigger -- Yes --> UpdateState[Update triggered_side & entry_price]
    UpdateState --> CancelOpposite[Cancel Opposite Side GTTs]
    CancelOpposite --> CheckTarget{Lot 1 Target Hit?}
    DetectTrigger -- No --> CheckTarget
    
    CheckTarget -- Yes --> TrailSL[Calculate & Update Lot 2 TSL]
    CheckTarget -- No --> ExitM[Exit: Maintenance Complete]
    TrailSL --> ExitM

    %% Path B: New Trade Placement
    CheckGTT -- No --> DayOpenQuote[Fetch Day Open via Quote API]
    DayOpenQuote --> GapCheck{Gap Detected?}
    GapCheck -- Yes --> Range915[Wait 9:15 & Calculate Range]
    Range915 --> GenPlan[Generate Trade Plan]
    GapCheck -- No --> GenPlan
    
    GenPlan --> AdvMonitor{Advanced Filters Enabled?}
    
    %% Advanced Monitoring Loop
    AdvMonitor -- Yes --> MonitorStart[Start Monitoring Loop]
    MonitorStart --> FetchData[Fetch COMEX, USDINR, MCX]
    FetchData --> Score[Calculate Confidence Score]
    Score --> Momentum{Hourly Momentum OK?}
    Momentum -- Yes --> CheckLevel{COMEX Breakout?}
    Momentum -- No --> Wait[Wait Interval]
    CheckLevel -- No --> Wait
    Wait --> FetchData
    CheckLevel -- Yes --> Slippage{Check Slippage}
    Slippage -- OK --> PlaceGTTs
    
    AdvMonitor -- No --> PlaceGTTs
    
    PlaceGTTs[Place Split GTT Orders]
    PlaceGTTs --> SaveState[Save GTT IDs to trading_state.json]
    SaveState --> ExitP[Exit: Placement Complete]
    
    %% Rollover Process (Separate Script)
    subgraph "Manual Rollover Utility"
    RollStart([Execute transfer_trade.py]) --> Compare[Compare Contract Scores]
    Compare --> Decision{New Score >= Old?}
    Decision -- Yes --> CloseOld[Market Exit: Old Contract]
    CloseOld --> OpenNew[LTP Entry: New Contract]
    OpenNew --> PlaceNewGTTs[Place GTTs on New Contract]
    PlaceNewGTTs --> UpdateStateRoll[Update trading_state.json]
    end

    subgraph "Main Execution Cycle"
    Maintenance
    DayOpenQuote
    MonitorStart
    end
```

## Phase Descriptions

### 1. Maintenance Phase (Startup/Monitoring)
Performed every time the script runs if existing GTT orders are found.
- **Stale Cleanup**: Checks if orders are from a previous day. If valid/active, they are kept; otherwise, cleaned up.
- **Trigger Detection**: Checks if the market hit our entry levels.
- **Cross-Cancellation**: Cancels the opposite side (Buy/Sell) if a trade is triggered.
- **Trailing SL**: If **Lot 1 Target** is hit, moves the Stop Loss for **Lot 2** using technical levels.

### 2. Analysis & Placement Phase
Performed if no active orders exist.
- **Quote-Based Open**: Fetches reliable open price.
- **Gap Handling**: 
    - **Gap Up**: Open > Previous Day Close.
    - **Gap Down**: Open < Previous Day Close.
    - If Gap detected, waits for 09:15 range breakout.
- **Advanced Gatekeeper**: 
    - **Comex Filter**: Checks International Gold Trend.
    - **Confidence Score**: Combines USDINR, COMEX, and Technicals.
    - **Momentum Check**: Validates MCX Hourly Candles and Volume/OI.
- **Split Entry**: Places OCO (Lot 1) and Single (Lot 2) GTTs.

### 3. Rollover Utility (Manual)
Run `transfer_trade.py` when expiry is near.
- **Score Analysis**: Compares Volume/OI of Current vs. Next contract.
- **Execution**: 
    - Closes old position (Market).
    - Opens new position (Market/LTP GTT).
    - **Dynamic Sizing**: Transfers only remaining lots (e.g., if Lot 1 exited, only transfers Lot 2).
