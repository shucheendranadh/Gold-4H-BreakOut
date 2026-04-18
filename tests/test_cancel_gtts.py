import pytest
from unittest.mock import MagicMock, patch
from Core.cancel_gtts import CancelGTTs

@pytest.fixture
def mock_managers():
    with patch('Core.cancel_gtts.StateManager') as MockSM, \
         patch('Core.cancel_gtts.OrderManager') as MockOM:
        
        sm_instance = MockSM.return_value
        om_instance = MockOM.return_value
        yield sm_instance, om_instance

def test_cancel_stored_gtts_success(mock_managers):
    sm, om = mock_managers
    
    # Setup mock state
    initial_state = {
        "gtts": {
            "BUY": {"OCO": "GTT-101", "SINGLE": "GTT-102"},
            "SELL": {"OCO": "GTT-201", "SINGLE": None}
        }
    }
    sm.load_state.return_value = initial_state
    
    # Setup OrderManager to succeed
    om.cancel_gtt_order.return_value = True

    # Run
    canceller = CancelGTTs()
    canceller.cancel_stored_gtts()

    # Verify calls
    # Should call cancel for 101, 102, 201
    assert om.cancel_gtt_order.call_count == 3
    om.cancel_gtt_order.assert_any_call("GTT-101")
    om.cancel_gtt_order.assert_any_call("GTT-102")
    om.cancel_gtt_order.assert_any_call("GTT-201")

    # Verify state update
    # Passed state object is mutable, so we check the one we gave it (or the one saved)
    saved_state = sm.save_state.call_args[0][0]
    assert saved_state['gtts']['BUY']['OCO'] is None
    assert saved_state['gtts']['BUY']['SINGLE'] is None
    assert saved_state['gtts']['SELL']['OCO'] is None
    # originally None remaining None
    assert saved_state['gtts']['SELL']['SINGLE'] is None

def test_cancel_stored_gtts_partial_failure(mock_managers):
    sm, om = mock_managers
    
    initial_state = {
        "gtts": {
            "BUY": {"OCO": "GTT-101"},
            "SELL": {"OCO": "GTT-201"}
        }
    }
    sm.load_state.return_value = initial_state
    
    # Fail first, succeed second
    def side_effect(gtt_id):
        return False if gtt_id == "GTT-101" else True
    
    om.cancel_gtt_order.side_effect = side_effect

    canceller = CancelGTTs()
    canceller.cancel_stored_gtts()

    saved_state = sm.save_state.call_args[0][0]
    
    # 101 Failed -> Should stay
    assert saved_state['gtts']['BUY']['OCO'] == "GTT-101"
    # 201 Success -> Should be None
    assert saved_state['gtts']['SELL']['OCO'] is None

def test_cancel_stored_gtts_empty_state(mock_managers):
    sm, om = mock_managers
    sm.load_state.return_value = {}
    
    canceller = CancelGTTs()
    canceller.cancel_stored_gtts()
    
    assert om.cancel_gtt_order.called is False
    assert sm.save_state.called is False
