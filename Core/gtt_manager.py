import logging
from datetime import datetime
from config import TOTAL_LOTS, ENABLE_GTT, ENABLE_PAPER_TRADING
from Core.order_manager import OrderManager
from Core.state_manager import StateManager

logger = logging.getLogger("GOLD_MARKET")

class GTTManager:
    def __init__(self):
        self.om = OrderManager()
        self.sm = StateManager()

    def place_gtts(self, active_contract, plan, session_name):
        """
        Places GTT orders based on the generated trade plan.
        Respects the ENABLE_GTT feature flag.
        """
        if not ENABLE_GTT and not ENABLE_PAPER_TRADING:
            logger.info("GTT placement is DISABLED via config (ENABLE_GTT=False). Skipping placement.")
            # Save state to prevent infinite loop
            skipped_state = {
                "instrument": active_contract,
                "gtts": {
                    "BUY": {"OCO": "SKIPPED", "SINGLE": "SKIPPED"},
                    "SELL": {"OCO": "SKIPPED", "SINGLE": "SKIPPED"}
                },
                "triggered_side": None,
                "entry_price": None,
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self.sm.save_state(skipped_state)
            return False

        # Imports inside method to avoid circular dependency if any
        from Core.registry import TradeRegistry
        registry = TradeRegistry()

        # Initialize state for GTTs
        trading_state = {
            "instrument": active_contract,
            "gtts": {
                "BUY": {"OCO": None, "SINGLE": None},
                "SELL": {"OCO": None, "SINGLE": None}
            },
            "triggered_side": None,
            "entry_price": None,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # Calculate Quantities
        if TOTAL_LOTS == 1:
            logger.info("Single Lot Mode: Placing only OCO orders.")
            oco_qty = 1
            single_qty = 0
        else:
            oco_qty = TOTAL_LOTS // 2
            single_qty = TOTAL_LOTS // 2
            logger.info(f"Multi-Lot Mode: Splitting {TOTAL_LOTS} lots -> OCO: {oco_qty}, SINGLE: {single_qty}")

        if oco_qty < 1:
             logger.error(f"Calculated OCO Quantity is 0 (Total: {TOTAL_LOTS}). Cannot place orders.")
             return False

        placed_any = False
        
        placed_orders_log = []

        # Place BUY side GTTs
        b = plan.get('BUY')
        if b and b.get('entry'):
            logger.info(f"Placing BUY side GTTs...")
            
            # Lot 1: Entry + SL 1 + Target 1 (OCO)
            gtt_id = self.om.place_gtt_order(
                instrument_token=active_contract,
                transaction_type="BUY",
                quantity=oco_qty,
                entry_price=b['entry'],
                stop_loss=b['sl_1'],
                target=b.get('target_1'), 
                type="MULTIPLE"
            )
            trading_state["gtts"]["BUY"]["OCO"] = gtt_id
            if gtt_id: 
                placed_orders_log.append({"side": "BUY", "type": "OCO", "id": gtt_id, "params": b})

            # Lot 2: Entry + SL 2 (SINGLE - Trailing)
            if single_qty > 0:
                gtt_id = self.om.place_gtt_order(
                    instrument_token=active_contract,
                    transaction_type="BUY",
                    quantity=single_qty,
                    entry_price=b['entry'],
                    stop_loss=b['sl_2'], # Use SL 2
                    type="MULTIPLE"
                )
                trading_state["gtts"]["BUY"]["SINGLE"] = gtt_id
                if gtt_id:
                    placed_orders_log.append({"side": "BUY", "type": "SINGLE", "id": gtt_id, "params": b})
            
            placed_any = True

        # Place SELL side GTTs
        s = plan.get('SELL')
        if s and s.get('entry'):
            logger.info(f"Placing SELL side GTTs...")
            
            # Lot 1: Entry + SL 1 + Target 1 (OCO)
            gtt_id = self.om.place_gtt_order(
                instrument_token=active_contract,
                transaction_type="SELL",
                quantity=oco_qty,
                entry_price=s['entry'],
                stop_loss=s['sl_1'],
                target=s.get('target_1'),
                type="MULTIPLE"
            )
            trading_state["gtts"]["SELL"]["OCO"] = gtt_id
            if gtt_id:
                placed_orders_log.append({"side": "SELL", "type": "OCO", "id": gtt_id, "params": s})
            
            # Lot 2: Entry + SL 2 (SINGLE - Trailing)
            if single_qty > 0:
                gtt_id = self.om.place_gtt_order(
                    instrument_token=active_contract,
                    transaction_type="SELL",
                    quantity=single_qty,
                    entry_price=s['entry'],
                    stop_loss=s['sl_2'], # Use SL 2
                    type="MULTIPLE"
                )
                trading_state["gtts"]["SELL"]["SINGLE"] = gtt_id
                if gtt_id:
                    placed_orders_log.append({"side": "SELL", "type": "SINGLE", "id": gtt_id, "params": s})

            placed_any = True

        if placed_any:
            self.sm.save_state(trading_state)
            registry.log_trade("PLACE_GTT", {
                "session": session_name,
                "orders": placed_orders_log,
                "plan": plan
            })
            logger.info("GTT orders placed and state saved.")
            return True
        else:
            logger.warning("No entry levels found in trade plan. No GTTs placed.")
            return False

    def cancel_all_gtts(self):
        """
        Cancels all active GTTs (cleans up previous session).
        """
        logger.info("Canceling ALL Active GTTs...")
        self.om.cancel_all_gtts()
        
        # Log to registry
        from Core.registry import TradeRegistry
        registry = TradeRegistry()
        registry.log_trade("CANCEL_ALL", {"reason": "Session Transition"})
        
        # Clear State
        self.sm.clear_state()

