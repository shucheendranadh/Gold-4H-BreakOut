
import logging
import sys
from Core.paper_exchange import PaperExchange

# Config Logging
logging.basicConfig(level=logging.INFO)

def test_paper_position_logic():
    print("Testing Paper Exchange Net Position Logic...")
    pe = PaperExchange(orders_file="Data/test_orders.json", pnl_file="Data/test_pnl.json")
    
    # 1. Start with clean slate
    pe._save_orders([])
    qty = pe.get_net_position_qty()
    print(f"Initial Qty (Should be 0): {qty}")
    assert qty == 0
    
    # 2. Add an ACTIVE BUY Order
    pe.place_order({
        "transaction_type": "BUY",
        "quantity": 1,
        "entry_price": 50000,
        "stop_loss": 49000,
        "target": 51000
    })
    
    # Manually activate it
    orders = pe._load_orders()
    orders[0]['status'] = "ACTIVE"
    pe._save_orders(orders)
    
    qty = pe.get_net_position_qty()
    print(f"Qty after 1 BUY Active (Should be 1): {qty}")
    assert qty == 1
    
    # 3. Add an ACTIVE SELL Order (Hedge?)
    pe.place_order({
        "transaction_type": "SELL",
        "quantity": 2, # 2 Lots
        "entry_price": 50000,
        "stop_loss": 51000,
        "target": 49000
    })
    
    # Manually activate it
    orders = pe._load_orders()
    orders[1]['status'] = "ACTIVE"
    pe._save_orders(orders)
    
    qty = pe.get_net_position_qty()
    print(f"Qty after 1 BUY + 2 SELL Active (Should be -1): {qty}")
    assert qty == -1 # 1 - 2 = -1
    
    print("SUCCESS: Paper Position Logic Verified.")

    # Cleanup
    import os
    try:
        os.remove("Data/test_orders.json")
        os.remove("Data/test_pnl.json")
    except: pass

if __name__ == "__main__":
    test_paper_position_logic()
