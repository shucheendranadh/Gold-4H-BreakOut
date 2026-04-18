# Implementation Plan - Trade Transfer (Rollover) Logic

## Goal Description
Implement a mechanism to transfer an active trade from one contract (e.g., expiring monthly future) to the next contract. This involves closing the existing position, opening a new position in the target contract, and ensuring the system correctly resumes management (Stop Loss/Target) of the new position.

## User Review Required
> [!IMPORTANT]
> **Manual Intervention**: The `transfer_trade.py` script will be interactive. It requires the user to confirm the "Target Contract" to ensure we don't accidentally roll into an illiquid contract.

> [!WARNING]
> **State Reset**: Executing a transfer will clear the `trading_state.json`. `main.py` will be updated to detect the "Open Position + Empty State" condition and "Adopt" the orphan trade by placing fresh Stop Loss orders.

## Operational Workflow: Score-Based Execution
This feature is designed as a **Logic-Driven Utility**. 
You simply run the script `transfer_trade.py`. It will **Automatically Execute** the rollover **ONLY IF** the "Next Contract" is better or equal.

**Trigger Condition**:
The script will fetch **Real-Time Data** (refreshing the quotes) to analyze the "Score" (Volume + OI Rank) of the current vs. next month's contract.
- **Rule**: If `Next_Contract_Score >= Current_Contract_Score`, the rollover is recommended/executed.
- **Note**: This uses *Live* market data, not the frozen data from the morning `premarket.py` run.

## Proposed Changes

### Core Logic Updates

#### [MODIFY] [Core/order_manager.py](file:///c:/Algo/GOLD/Core/order_manager.py)
- **Add Method**: `get_position_qty(instrument_token)`
    - Returns the actual integer quantity (positive for Buy, negative for Sell).
    - Returns 0 if no position.

#### [MODIFY] [Core/instrument_manager.py](file:///c:/Algo/GOLD/Core/instrument_manager.py)
- Update `calculate_rank`:
    - **Logic Change**: Modify the sort order. Currently, it prefers Earlier Expiry on tied scores.
    - **New Rule**: If Scores are Equal, prefer the **Later Expiry** (New Month).
    - Change sort key from `(score, -expiry)` to `(score, expiry)`.
    - Return the full scored list to allow other scripts to analyze candidates.

#### [NEW] [transfer_trade.py](file:///c:/Algo/GOLD/transfer_trade.py)
A standalone script that handles the rollover:
1.  **Analyze**:
    - Fetch current active contract and "Next" contract.
    - Compare Scores.
    - If `Next_Score < Current_Score`: Warn user (or exit if auto).
    - If `Next_Score >= Current_Score`: Proceed.
2.  **Execute Exit**:
    - Place **Market Order** to close the existing position (Immediate Exit).
3.  **Execute Entry (Low Slippage)**:
    - active_contract = New Contract.
    - Get Current LTP of New Contract.
    - **Fresh Strategy Application**: Treat this as a *new start* with the active trend.
    - **Quantity Logic**:
        - Check `Old Contract Quantity`.
        - If `Old_Qty == TOTAL_LOTS` (Full Position):
            - Place standard `TOTAL_LOTS` split (Lot 1 OCO, Lot 2 Single).
            - **Lot 1 SL/Target**: New Contract Levels.
            - **Lot 2 TSL**: New Contract Levels.
        - If `Old_Qty == TOTAL_LOTS / 2` (Lot 1 already hit target):
            - **Transfer ONLY Lot 2**.
            - Place **SINGLE GTT** for `TOTAL_LOTS / 2`.
            - **SL**: Use **Lot 2 TSL** formula: `MROUND(max(LTP * 0.985, New_4dLL * 0.9988), 1)`.
    - **Execution**: Call `GTTManager.place_gtts` (or manual place via `om`) with `Entry Price = LTP` and appropriate strategy.
    - Update `trading_state.json` with these new GTTs.
4.  **Handover**:
    - `main.py` will start, see the active GTTs (or triggered GTTs), and resume management.
    - **Benefit**: No need for "Orphan Position" logic adjustments in `main.py`. The system treats it as a valid new trade.

## Verification Plan

### Automated Tests
- None (Live Trading Logic).

### Manual Verification
1.  **Dry Run**:
    - Create a dummy `transfer_trade.py` that mocks the API calls.
    - Verify it updates `premarket_data.json` correctly.
2.  **Logic Check**:
    - Mock `main.py` state detection.
    - Provide it with an "Open Position" return value.
    - Verify it calls `recover_orphan_position`.
    - Verify `recover_orphan_position` calculates correct SL and calls `place_gtt_order`.
