import json
import os
import uuid
import logging
from datetime import datetime
from config import INITIAL_PAPER_CAPITAL

logger = logging.getLogger("GOLD_MARKET")

class PaperExchange:
    def __init__(self, orders_file="Data/paper_orders.json", pnl_file="Data/paper_pnl.json"):
        self.orders_file = orders_file
        self.pnl_file = pnl_file
        self._orders_mem = None
        self._orders_mtime = None  # mtime-based invalidation across instances
        self._ensure_files()
        
    def _ensure_files(self):
        """Ensures data files exist."""
        os.makedirs(os.path.dirname(self.orders_file), exist_ok=True)
        
        if not os.path.exists(self.orders_file):
            with open(self.orders_file, 'w') as f:
                json.dump([], f)
                
        if not os.path.exists(self.pnl_file):
            with open(self.pnl_file, 'w') as f:
                json.dump({
                    "initial_capital": INITIAL_PAPER_CAPITAL,
                    "current_balance": INITIAL_PAPER_CAPITAL,
                    "realized_pnl": 0.0,
                    "trades": []
                }, f)

    def _load_orders(self):
        try:
            mtime = os.path.getmtime(self.orders_file)
            if self._orders_mem is not None and mtime == self._orders_mtime:
                return self._orders_mem
            with open(self.orders_file, 'r') as f:
                self._orders_mem = json.load(f)
            self._orders_mtime = mtime
        except Exception:
            self._orders_mem = []
        return self._orders_mem

    def _save_orders(self, orders):
        self._orders_mem = orders
        with open(self.orders_file, 'w') as f:
            json.dump(orders, f, indent=4)
        try:
            self._orders_mtime = os.path.getmtime(self.orders_file)
        except Exception:
            self._orders_mtime = None

    def _load_pnl(self):
        try:
            with open(self.pnl_file, 'r') as f:
                return json.load(f)
        except: return {}

    def get_net_position_qty(self):
        """
        Calculates the net position quantity from active paper orders.
        Returns:
            int: Net quantity (Positive for BUY, Negative for SELL).
        """
        orders = self._load_orders()
        net_qty = 0
        
        for order in orders:
            # Consider only ACTIVE orders as open positions
            # PENDING means not yet filled (no position)
            # CLOSED means position closed
            if order.get("status") == "ACTIVE":
                qty = int(order.get("qty", 0))
                side = order.get("side", "BUY")
                
                if side == "BUY":
                    net_qty += qty
                else:
                    net_qty -= qty
                    
        return net_qty

    def _save_pnl(self, pnl_data):
        with open(self.pnl_file, 'w') as f:
            json.dump(pnl_data, f, indent=4)

    # --- Order Placement ---
    def place_order(self, order_details):
        """
        Simulates placing a GTT order.
        Returns a virtual order ID.
        """
        orders = self._load_orders()
        
        # Calculate Trigger Price from Details (GTT structure simulation)
        # order_details expectation:
        # { 'transaction_type': 'BUY', 'quantity': 1, 'entry_price': ..., 'stop_loss': ..., 'target': ... }
        
        entry_price = float(order_details.get('entry_price'))
        sl_price = float(order_details.get('stop_loss', 0.0))
        target_price = order_details.get('target')
        if target_price == 'OPEN' or target_price is None:
            target_price = 0.0 # Open target
        else:
            target_price = float(target_price)

        virtual_id = f"PAPER-GTT-{uuid.uuid4().hex[:8].upper()}"
        
        new_order = {
            "id": virtual_id,
            "status": "PENDING", # PENDING -> ACTIVE -> CLOSED
            "side": order_details.get('transaction_type'),
            "qty": order_details.get('quantity'),
            "entry_price": entry_price,
            "sl_price": sl_price,
            "target_price": target_price,
            "placed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "filled_at": None,
            "closed_at": None,
            "exit_reason": None,
            "exit_price": 0.0,
            "pnl": 0.0
        }
        
        orders.append(new_order)
        self._save_orders(orders)
        logger.info(f"[PAPER] GTT Placed: {virtual_id} | {new_order['side']} @ {entry_price} | SL: {sl_price} | TGT: {target_price}")
        return virtual_id

    def modify_order(self, order_id, new_sl=None):
        """Simulates modifying an order (e.g., Trailing SL)."""
        orders = self._load_orders()
        for order in orders:
            if order['id'] == order_id and order['status'] in ["PENDING", "ACTIVE"]:
                if new_sl:
                    old_sl = order['sl_price']
                    order['sl_price'] = float(new_sl)
                    logger.info(f"[PAPER] Order {order_id} Modified. SL: {old_sl} -> {new_sl}")
                    self._save_orders(orders)
                    return True
        return False

    def cancel_order(self, order_id):
        """Simulates cancelling an order."""
        orders = self._load_orders()
        # Filter out cancelled
        new_orders = [o for o in orders if o['id'] != order_id]
        
        if len(new_orders) < len(orders):
            logger.info(f"[PAPER] Order Cancelled: {order_id}")
            self._save_orders(new_orders)
            return True
        return False

    def get_order_details(self, order_id):
        """Mock response simulating Upstox API response structure for GTT."""
        orders = self._load_orders()
        order = next((o for o in orders if o['id'] == order_id), None)
        if not order:
            return None
        
        # Construct simplified Upstox-like rule structure for compatibility
        status_map = {
            "PENDING": "active", 
            "ACTIVE": "triggered", # Upstox 'triggered' means entry hit? Assume yes.
            "CLOSED": "completed"
        }
        
        # We need to mimic the 'rules' array so PositionManager can read it.
        # For CLOSED orders, only the exit rule that actually triggered is COMPLETED;
        # all other rules are CANCELLED (not ACTIVE — that would fool is_gtt_active).
        is_closed = order['status'] == "CLOSED"

        def rule_status(strategy):
            if not is_closed:
                # PENDING/ACTIVE: entry is COMPLETED once filled, rest are ACTIVE (pending)
                if strategy == "ENTRY":
                    return "COMPLETED" if order['status'] == "ACTIVE" else "ACTIVE"
                return "ACTIVE"
            # CLOSED: the exit trigger is COMPLETED, everything else is CANCELLED
            if strategy == "ENTRY":
                return "COMPLETED"
            if strategy == "STOPLOSS":
                return "COMPLETED" if order['exit_reason'] == "STOPLOSS" else "CANCELLED"
            if strategy == "TARGET":
                return "COMPLETED" if order['exit_reason'] == "TARGET" else "CANCELLED"
            return "CANCELLED"

        rules = [
            {"strategy": "ENTRY",    "status": rule_status("ENTRY"),    "trigger_price": order['entry_price']},
            {"strategy": "STOPLOSS", "status": rule_status("STOPLOSS"), "trigger_price": order['sl_price']},
        ]

        if order['target_price'] > 0:
            rules.append({
                "strategy": "TARGET",
                "status": rule_status("TARGET"),
                "trigger_price": order['target_price']
            })
            
        return {
            "gtt_order_id": order['id'],
            "status": status_map.get(order['status'], "active"),
            "rules": rules
        }

    # --- Market Simulation ---
    def monitor(self, current_ltp):
        """
        Core Simulation Loop. Check triggers against LTP.
        """
        if not current_ltp: return

        orders = self._load_orders()
        updated = False
        
        for order in orders:
            status = order['status']
            side = order['side']
            
            # 1. PENDING -> ACTIVE (Entry Hit)
            if status == "PENDING":
                triggered = False
                if side == "BUY":
                    # DEBUG LOG
                    # logger.debug(f"Checking BUY Trigger: LTP {current_ltp} >= Entry {order['entry_price']}?")
                    if current_ltp >= order['entry_price']:
                        logger.info(f"Trigger Condition Met: LTP {current_ltp} >= Entry {order['entry_price']}")
                        triggered = True 

                elif side == "SELL" and current_ltp <= order['entry_price']:
                    triggered = True
                     
                if triggered:
                    order['status'] = "ACTIVE"
                    order['filled_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    logger.info(f"[PAPER] ⚡ TRADE TRIGGERED: {order['id']} ({side}) filled at {current_ltp}")
                    updated = True
                    continue # Move to next order

            # 2. ACTIVE -> CLOSED (SL or Target Hit)
            if status == "ACTIVE":
                exit_reason = None
                
                # Check SL
                sl_hit = False
                if side == "BUY" and current_ltp <= order['sl_price']:
                    sl_hit = True
                elif side == "SELL" and current_ltp >= order['sl_price']:
                    sl_hit = True
                    
                if sl_hit:
                    exit_reason = "STOPLOSS"
                    
                # Check Target
                tgt_hit = False
                if not exit_reason and order['target_price'] > 0:
                    if side == "BUY" and current_ltp >= order['target_price']:
                        tgt_hit = True
                    elif side == "SELL" and current_ltp <= order['target_price']:
                        tgt_hit = True
                
                if tgt_hit:
                    exit_reason = "TARGET"
                    
                if exit_reason:
                    self._close_order(order, current_ltp, exit_reason)
                    updated = True

        if updated:
            self._save_orders(orders)

    def _close_order(self, order, exit_price, reason):
        order['status'] = "CLOSED"
        order['closed_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        order['exit_reason'] = reason
        order['exit_price'] = exit_price
        
        # Calculate PnL
        qty = order['qty']
        entry = order['entry_price']
        
        if order['side'] == "BUY":
            pnl = (exit_price - entry) * qty
        else:
            pnl = (entry - exit_price) * qty
            
        # Update Order
        order['pnl'] = round(pnl, 2)
        
        # Update Account
        pnl_data = self._load_pnl()
        pnl_data['realized_pnl'] = pnl_data.get('realized_pnl', 0.0) + pnl
        pnl_data['current_balance'] = pnl_data.get('current_balance', 0.0) + pnl
        pnl_data['trades'].append({
            "id": order['id'],
            "side": order['side'],
            "pnl": order['pnl'],
            "reason": reason,
            "date": order['closed_at']
        })
        self._save_pnl(pnl_data)
        
        logger.info(f"[PAPER] 💰 TRADE CLOSED: {order['id']} | Reason: {reason} | P&L: {order['pnl']} | Bal: {pnl_data['current_balance']}")
