import pytest
from unittest.mock import MagicMock, patch
from Core.signal_engine import SignalEngine
from datetime import datetime

@pytest.fixture
def signal_engine():
    with patch('Core.signal_engine.MarketData') as MockMD:
        engine = SignalEngine()
        engine.md = MockMD.return_value
        yield engine

def test_session_boundary_emission(signal_engine):
    # Setup
    signal_engine.sessions = ["09:00", "13:00", "17:00"]
    # Mock time to 13:00:01
    mock_now = datetime.strptime("2025-01-01 13:00:01", "%Y-%m-%d %H:%M:%S")
    
    with patch('Core.signal_engine.datetime') as mock_dt:
        mock_dt.now.return_value = mock_now
        mock_dt.strftime.side_effect = lambda fmt: mock_now.strftime(fmt)
        
        # Mock Market Data
        signal_engine.md.get_session_high_low.return_value = (1000, 900) # High, Low
        
        # Action
        actions = signal_engine.check_schedule("TEST_TOKEN", state={})
        
        # Verify
        assert len(actions) == 1
        event = actions[0]
        assert event['event'] == 'SESSION_BOUNDARY'
        assert event['high'] == 1000
        assert event['low'] == 900
        assert event['session_index'] == 1
        assert event['prev_start'] == "09:00"
        assert event['prev_end'] == "13:00"

def test_generate_restorative_plan(signal_engine):
    # Mock time to 14:00 (After 13:00 session closed)
    mock_now = datetime.strptime("2025-01-01 14:00:00", "%Y-%m-%d %H:%M:%S")
    
    with patch('Core.signal_engine.datetime') as mock_dt:
        mock_dt.now.return_value = mock_now
        
        # Expect call for 09:00-13:00
        signal_engine.md.get_session_high_low.return_value = (1005, 995)
        
        plan, _ = signal_engine.generate_restorative_plan("TEST")
        
        signal_engine.md.get_session_high_low.assert_called_with("TEST", "09:00", "13:00")
        assert plan['BUY']['entry'] > 995
