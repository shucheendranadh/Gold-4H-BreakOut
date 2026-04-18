import pytest
from unittest.mock import MagicMock, patch
from Core.position_manager import PositionManager

@pytest.fixture
def pm_setup():
    with patch('Core.position_manager.StateManager') as MockSM, \
         patch('Core.position_manager.OrderManager') as MockOM:
        pm = PositionManager()
        pm.sm = MockSM.return_value
        pm.om = MockOM.return_value
        yield pm, pm.sm, pm.om

def test_update_tsl_buy_side(pm_setup):
    pm, sm, om = pm_setup
    
    # State: Triggered BUY, Lot 2 ID present
    sm.load_state.return_value = {
        "triggered_side": "BUY",
        "gtts": {"BUY": {"OCO": "OCO-1", "SINGLE": "GTT-2"}}
    }
    
    # Lot 1 Target Hit
    om.get_gtt_order_details.side_effect = lambda id: {
        "rules": [
           # OCO Rules
           {"strategy": "TARGET", "status": "COMPLETED"} 
           if id == "OCO-1" else 
           # Lot 2 Rules
           {"strategy": "STOPLOSS", "trigger_price": 990}
        ]
    }
    om.modify_gtt_order.return_value = True
    
    high = 1050
    low = 1000 # Session Low
    
    # Run
    pm.update_trailing_sl_from_session(high, low)
    
    # Expected SL: Low (1000) - Buffer (0.15%)
    # 1000 * 0.9985 = 998.5 -> rounded
    from config import SL_BUFFER_PCT
    expected_sl = int(low * (1 - SL_BUFFER_PCT)) 
    
    om.modify_gtt_order.assert_called_with("GTT-2", new_sl=expected_sl)

def test_update_tsl_skips_if_target_not_hit(pm_setup):
    pm, sm, om = pm_setup
    
    sm.load_state.return_value = {
        "triggered_side": "BUY",
        "gtts": {"BUY": {"OCO": "OCO-1", "SINGLE": "GTT-2"}}
    }
    
    # Lot 1 Target Pending
    om.get_gtt_order_details.return_value = {
        "rules": [{"strategy": "TARGET", "status": "PENDING"}]
    }
    
    pm.update_trailing_sl_from_session(1050, 1000)
    
    assert om.modify_gtt_order.called is False
