import pytest
from unittest.mock import MagicMock, patch
import time
from Core.signal_engine import SignalEngine
from Core.gtt_manager import GTTManager
from Core.guardian import Guardian
from Core.position_manager import PositionManager
from Core.cancel_gtts import CancelGTTs
from Core.state_manager import StateManager

# We will test the LOGIC inside main loop by extracting it or mocking dependencies
# Since main() has a while loop, we will mock time and throw StopIteration to exit

@patch("main.SignalEngine")
@patch("main.Guardian")
@patch("main.PositionManager")
@patch("main.GTTManager")
@patch("main.CancelGTTs")
@patch("main.StateManager")
@patch("main.InstrumentManager")
def test_main_workflow(MockIM, MockSM, MockCancel, MockGTT, MockPM, MockGuardian, MockSE):
    # Setup Mocks
    im = MockIM.return_value
    im.get_active_contract.return_value = "TEST_TOKEN"
    
    se = MockSE.return_value
    guardian = MockGuardian.return_value
    pm = MockPM.return_value
    gtt = MockGTT.return_value
    cancel = MockCancel.return_value
    sm = MockSM.return_value

    # We import main to run it, but we need to break the loop
    from main import main
    
    # Strategy: We will mock time.time() to advance and trigger conditions
    # We will also mock time.sleep() to raise an exception to exit the loop eventually?
    # Or better, we mock datetime.now() to eventually hit SESSION_END_TIME.
    
    start_time = time.time()
    
    # Mock sequence for time.time()
    # 1. Start
    # 2. Guardian Check Time (Trigger Guardian)
    # 3. Maintenance Time (Trigger Maintenance + Session Boundary)
    # 4. End
    
    # We need to control the loop execution.
    # main.py uses:
    # current_ts = time.time()
    # guardian check > GUARDIAN_CHECK_INTERVAL
    # maintenance check > 5
    
    # Let's mock time.time to return incrementing values
    # GUARDIAN_CHECK_INTERVAL is 60 (default? let's assume imports from config)
    
    with patch("main.time.time", side_effect=[
        start_time,          # Init
        start_time + 10,     # Loop 1: Maintenance (5s passed)
        start_time + 70,     # Loop 2: Guardian (60s passed)
        start_time + 80,     # Loop 3: Maintenance again
        start_time + 100,    # ...
    ]) as mock_time, \
    patch("main.datetime") as mock_dt, \
    patch("main.time.sleep", side_effect=[None, None, None, KeyboardInterrupt]): # Run 3 loops then Stop
        
        # Setup Datetime for session check
        mock_dt.now.return_value.strftime.return_value = "10:00" # Active Time
        
        # Loop 1: Normal Maintenance
        # Expect pm.handle_daily_maintenance
        
        # Loop 2: Guardian Check triggers (Time + 70 > Time + 60)
        # We want `guardian.check_for_crash` to be called.
        
        # Loop 3: Session Boundary Event
        # We make se.check_schedule return an event
        se.check_schedule.side_effect = [
            [], # Loop 1
            [], # Loop 2
            [{ "event": "SESSION_BOUNDARY", "session_name": "S2", "high": 100, "low": 90 }] # Loop 3
        ]
        
        try:
            main()
        except KeyboardInterrupt:
            pass
            
        # Assertions
        
        # 1. Guardian Check
        assert guardian.check_for_crash.called, "Guardian check should have run"
        
        # 2. Session Boundary Logic Fork
        # Since state had "triggered_side", we expect update_trailing_sl_from_session
        pm.update_trailing_sl_from_session.assert_called_with(high=100, low=90)
        
        # 3. Verify NOT cancelling/placing GTTs
        assert not cancel.cancel_stored_gtts.called, "Should NOT cancel GTTs if trade active"
        assert not gtt.place_gtts.called, "Should NOT place GTTs if trade active"

def test_main_workflow_rotate_gtts_if_no_trade():
    """Test the other fork: No Active Trade -> Rotate GTTs"""
    with patch("main.SignalEngine") as MockSE, \
         patch("main.Guardian") as MockGuard, \
         patch("main.PositionManager") as MockPM, \
         patch("main.GTTManager") as MockGTT, \
         patch("main.CancelGTTs") as MockCancel, \
         patch("main.StateManager") as MockSM, \
         patch("main.InstrumentManager") as MockIM, \
         patch("main.time.time", side_effect=[0, 10, 20]) as mock_time, \
         patch("main.datetime") as mock_dt, \
         patch("main.time.sleep", side_effect=[None, KeyboardInterrupt]):
         
        # Setup
        se = MockSE.return_value
        sm = MockSM.return_value
        gtt = MockGTT.return_value
        cancel = MockCancel.return_value
        MockIM.return_value.get_active_contract.return_value = "TEST"
        mock_dt.now.return_value.strftime.return_value = "10:00"
        
        # Signal emits Session Boundary
        se.check_schedule.return_value = [{ 
            "event": "SESSION_BOUNDARY", 
            "session_name": "S2", 
            "high": 100, "low": 90 
        }]
        se.calculate_levels_with_buffers.return_value = {
            "BUY": {"entry": 1, "sl": 0}, "SELL": {"entry": 2, "sl": 3}
        }
        
        # State: Empty/No Trigger
        sm.load_state.return_value = {} 
        
        from main import main
        try:
            main()
        except KeyboardInterrupt:
            pass
            
        # Assertions
        assert cancel.cancel_stored_gtts.called, "Should Cancel Old GTTs"
        assert gtt.place_gtts.called, "Should Place New GTTs"
        assert not MockPM.return_value.update_trailing_sl_from_session.called
