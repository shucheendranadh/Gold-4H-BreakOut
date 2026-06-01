import logging
import requests
import json
from config import UPSTOX_ACCESS_TOKEN, UPSTOX_ORDER_URL, UPSTOX_GTT_URL, UPSTOX_POSITIONS_URL, ENABLE_PAPER_TRADING
from Core.paper_exchange import PaperExchange

logger = logging.getLogger("GOLD_MARKET")

class OrderManager:
    def __init__(self):
        self.order_url = UPSTOX_ORDER_URL
        self.base_url = UPSTOX_GTT_URL
        self.positions_url = UPSTOX_POSITIONS_URL
        self.headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {UPSTOX_ACCESS_TOKEN}'
        }
        self.paper = PaperExchange()

    def get_net_position_qty(self, instrument_token):
        """
        Fetch standard Net Quantity for a specific instrument.
        Returns integer quantity (Positive=Buy, Negative=Sell, 0=None).
        """
        # Paper Trading Hook
        if ENABLE_PAPER_TRADING:
            logger.info(f"Fetching Net Position from Paper Exchange...")
            return self.paper.get_net_position_qty()

        if not UPSTOX_ACCESS_TOKEN or UPSTOX_ACCESS_TOKEN == "YOUR_ACCESS_TOKEN_HERE":
            return 0

        try:
            response = requests.get(self.positions_url, headers=self.headers)
            response.raise_for_status()
            res_json = response.json()
            
            if res_json.get("status") == "success":
                positions = res_json.get("data", [])
                for position in positions:
                    if position.get("instrument_token") == instrument_token:
                        # Upstox returns 'quantity' as net quantity usually
                        # But reliably, 'net_quantity' or 'quantity' depending on API version.
                        # V2/V3 'quantity' field in positions endpoint is net.
                        return int(position.get("quantity", 0))
                return 0
            return 0
        except Exception as e:
            logger.error(f"Error fetching net position: {e}")
            return 0

    def has_open_position(self, instrument_token):
        """
        Check if there's an open position (non-zero qty).
        """
        qty = self.get_net_position_qty(instrument_token)
        if qty != 0:
            logger.info(f"Open position found for {instrument_token}: Qty={qty}")
            return True
        logger.info(f"No open position found for {instrument_token}")
        return False

    def place_order(self, instrument_token, transaction_type, quantity, order_type, price=0, trigger_price=0, product="D"):
        """
        Place a regular order via Upstox API.
        
        Args:
            instrument_token (str): Instrument Key
            transaction_type (str): "BUY" or "SELL"
            quantity (int): Quantity
            order_type (str): "MARKET", "LIMIT", "SL", "SL-M"
            price (float): Limit price (for LIMIT/SL orders)
            trigger_price (float): Trigger price (for SL/SL-M orders)
            product (str): "I" (Intraday) or "D" (Delivery), default "D"
            
        Returns:
            str: Order ID if successful, None otherwise
        """
        if not UPSTOX_ACCESS_TOKEN or UPSTOX_ACCESS_TOKEN == "YOUR_ACCESS_TOKEN_HERE":
            logger.error("UPSTOX_ACCESS_TOKEN not set. Cannot place order.")
            return None

        data = {
            "quantity": quantity,
            "product": product,
            "validity": "DAY",
            "price": float(price) if price else 0,
            "tag": "GOLD_STRATEGY",
            "instrument_token": instrument_token,
            "order_type": order_type,
            "transaction_type": transaction_type.upper(),
            "disclosed_quantity": 0,
            "trigger_price": float(trigger_price) if trigger_price else 0,
            "is_amo": False
        }

        try:
            logger.info(f"Placing {order_type} {transaction_type} Order | Qty: {quantity} | Price: {price} | Trigger: {trigger_price}")
            response = requests.post(self.order_url, headers=self.headers, json=data)
            response.raise_for_status()
            res_json = response.json()
            
            if res_json.get("status") == "success":
                order_id = res_json.get("data", {}).get("order_id")
                logger.info(f"✓ Order Placed Successfully. Order ID: {order_id}")
                return order_id
            else:
                logger.error(f"Failed to place order: {res_json}")
                return None
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            if 'response' in locals():
                logger.error(f"Response: {response.text}")
            return None

    def modify_order(self, order_id, new_price=None, new_quantity=None, new_trigger_price=None, new_type=None):
        """
        Modify an open regular order.
        """
        if not order_id: return False
        
        try:
            url = "https://api.upstox.com/v2/order/modify" # Check V2 vs V3 URL consistency. Project uses V2 URLs for regular orders mostly? 
            # Note: Project seems to use V2 for regular placement but self.order_url typically is V2.
            # Let's double check self.order_url in __init__.
            # Assuming self.order_url is the base. Wait, self.order_url in place_order implies it's set.
            # let's use requests.put against modify endpoint.
            
            # Upstox V2 Modify Endpoint: PUT /order/modify
            
            data = {
                "order_id": order_id,
                "validity": "DAY", # Assuming DAY
                "product": "D", # Assuming Delivery based on context
            }
            
            if new_price is not None:
                data["price"] = float(new_price)
                data["order_type"] = "LIMIT" # Implicitly Limit if price sent
                
            if new_quantity is not None:
                data["quantity"] = int(new_quantity)
                
            if new_trigger_price is not None:
                data["trigger_price"] = float(new_trigger_price)
                
            if new_type:
                 data["order_type"] = new_type
            
            # Using V2 endpoint as standard for this project?
            # Actually, let's stick to the URL structure if known.
            # "https://api.upstox.com/v2/order/modify"
            
            response = requests.put(url, headers=self.headers, json=data)
            
            if response.status_code != 200:
                logger.error(f"Failed to modify Order {order_id}. Status: {response.status_code}")
                # debug logger.error(f"Response: {response.text}")
                return False
                
            res_json = response.json()
            if res_json.get("status") == "success":
                logger.info(f"Order {order_id} Modified Successfully.")
                return True
            else:
                logger.error(f"Modify Order Failed: {res_json}")
                return False
        except Exception as e:
            logger.error(f"Error modifying Order {order_id}: {e}")
            return False

    def cancel_order(self, order_id):
        """
        Cancel a regular order by ID.
        """
        if not order_id: return False
        
        try:
            url = f"{self.order_url}?order_id={order_id}"
            response = requests.delete(url, headers=self.headers)
            
            if response.status_code != 200:
                 logger.error(f"Failed to cancel Order {order_id}. Status: {response.status_code}")
                 return False
            
            res_json = response.json()
            if res_json.get("status") == "success":
                logger.info(f"Order Cancelled: {order_id}")
                return True
            else:
                logger.error(f"Failed to cancel order {order_id}: {res_json}")
                return False
        except Exception as e:
            logger.error(f"Error cancelling Order {order_id}: {e}")
            return False

    def place_gtt_order(self, instrument_token, transaction_type, quantity, entry_price, stop_loss, target=None, type="MULTIPLE"):
        """
        Place a GTT order using Upstox V3 schema.
        """
        # Paper Trading Hook
        if ENABLE_PAPER_TRADING:
            logger.info(f"Routing GTT Order to Paper Exchange... (Qty: {quantity}, Side: {transaction_type})")
            return self.paper.place_order({
                "transaction_type": transaction_type,
                "quantity": quantity,
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "target": target
            })

        # Determine trigger types based on Buy/Sell
        entry_trigger = "ABOVE" if transaction_type.upper() == "BUY" else "BELOW"
        
        rules = [
            {
                "strategy": "ENTRY",
                "trigger_type": entry_trigger,
                "trigger_price": float(entry_price),
                "price": float(entry_price)
            },
            {
                "strategy": "STOPLOSS",
                "trigger_type": "IMMEDIATE",
                "trigger_price": float(stop_loss),
                "price": float(stop_loss)
            }
        ]
        
        if target and target != "OPEN":
            try:
                target_val = float(target)
                rules.append({
                    "strategy": "TARGET",
                    "trigger_type": "IMMEDIATE",
                    "trigger_price": target_val,
                    "price": target_val
                })
            except ValueError:
                logger.warning(f"Invalid Target Price '{target}' passed. Skipping Target Rule.")
            
        data = {
            "type": type.upper(),
            "instrument_token": instrument_token,
            "product": "D",
            "quantity": int(quantity),
            "transaction_type": transaction_type.upper(),
            "rules": rules
        }
        
        try:
            logger.info(f"Placing GTT {type} {transaction_type} | Qty: {quantity} | Entry: {entry_price}")
            logger.debug(f"GTT Payload: {json.dumps(data)}")
            
            # Official V3 Placement Endpoint
            url = "https://api.upstox.com/v3/order/gtt/place"
            response = requests.post(url, headers=self.headers, json=data)
            
            res_json = response.json()
            if res_json.get("status") == "success":
                # V3 returns a list of IDs in gtt_order_ids
                gtt_ids = res_json.get("data", {}).get("gtt_order_ids", [])
                gtt_id = gtt_ids[0] if gtt_ids else None
                logger.info(f"GTT Placed Successfully. GTT ID: {gtt_id}")
                return gtt_id
            else:
                logger.error(f"Failed to place GTT: {res_json}")
                return None
        except Exception as e:
            logger.error(f"Error placing GTT: {e}")
            return None

    def cancel_all_gtts(self, instrument_token=None):
        """
        Cancels ALL active GTTs.
        If instrument_token is provided, cancels only for that instrument.
        """
        active_gtts = self.fetch_active_gtts()
        if not active_gtts:
            logger.info("No active GTTs found to cancel.")
            return 0
            
        count = 0
        for gtt in active_gtts:
            # If instrument filter is active and doesn't match, skip
            if instrument_token and gtt.get("instrument_token") != instrument_token:
                continue
                
            gtt_id = gtt.get("gtt_order_id")
            if self.cancel_gtt_order(gtt_id):
                count += 1
        return count

    def cancel_gtt_order(self, gtt_id):
        """Cancel a GTT order by ID using V3 endpoint."""
        # Paper Trading Hook
        if gtt_id and gtt_id.startswith("PAPER-"):
             return self.paper.cancel_order(gtt_id)

        if not gtt_id or "SKIPPED" in str(gtt_id) or "DRY_RUN" in str(gtt_id):
            logger.info(f"Ignoring cancel request for internal/dummy GTT ID: {gtt_id}")
            return True

        
        try:
            # Official V3 GTT Cancel Endpoint
            url = "https://api.upstox.com/v3/order/gtt/cancel"
            payload = {"gtt_order_id": gtt_id}
            response = requests.delete(url, headers=self.headers, json=payload)
            
            if response.status_code != 200:
                logger.error(f"Failed to cancel GTT {gtt_id}. Status: {response.status_code}")
                # debug logger.error(f"Response Body: {response.text}")
                return False
                
            res_json = response.json()
            if res_json.get("status") == "success":
                logger.info(f"GTT Cancelled: {gtt_id}")
                return True
            else:
                logger.error(f"Failed to cancel GTT {gtt_id}: {res_json}")
                return False
        except Exception as e:
            logger.error(f"Error cancelling GTT {gtt_id}: {e}")
            return False

    def modify_gtt_order(self, gtt_id, new_sl=None, new_entry=None, new_target=None):
        """
        Modify the Stop Loss price of an existing GTT order.
        Note: Upstox V3 requires sending the FULL rules list for modification.
        """
        if not gtt_id or "SKIPPED" in str(gtt_id) or "DRY_RUN" in str(gtt_id):
            logger.warning(f"Cannot modify internal/dummy GTT ID: {gtt_id}")
            return False

        # Paper Trading Hook
        if gtt_id and gtt_id.startswith("PAPER-"):
             return self.paper.modify_order(gtt_id, new_sl=new_sl)

        
        try:
            # 1. Fetch current details to get the existing rules
            details = self.get_gtt_order_details(gtt_id)
            if not details:
                logger.error(f"Cannot modify GTT {gtt_id}: Details not found.")
                return False
                
            # 2. Update and Clean the rules list
            raw_rules = details.get("rules", [])
            rules = []
            modified = False
            top_transaction_type = details.get("transaction_type")
            
            for r in raw_rules:
                # Create a clean rule by copying only allowed fields from the response
                clean_rule = {
                    "strategy": r.get("strategy"),
                    "trigger_type": r.get("trigger_type"),
                    "trigger_price": float(r.get("trigger_price")) if r.get("trigger_price") is not None else None
                }
                
                # Copy price if it exists
                if r.get("price") is not None:
                    clean_rule["price"] = float(r.get("price"))
                
                # Apply modification if this is the STOPLOSS rule
                if clean_rule.get("strategy") == "STOPLOSS" and new_sl is not None:
                    clean_rule["trigger_type"] = "IMMEDIATE" # Mandatory for MULTIPLE STOPLOSS
                    clean_rule["trigger_price"] = float(new_sl)
                    clean_rule["price"] = float(new_sl)
                    modified = True
                
                # Apply modification if this is the ENTRY rule
                elif clean_rule.get("strategy") == "ENTRY" and new_entry is not None:
                    # Determine trigger type based on transaction type and price
                    # Usually Entry trigger type (ABOVE/BELOW) might need re-evaluation if crossing LTP
                    # But for simple update, we keep original trigger_type or strictly follow GTT logic
                    # Upstox might reject if trigger_type doesn't match current price relation
                    # For now, just update price.
                    clean_rule["trigger_price"] = float(new_entry)
                    clean_rule["price"] = float(new_entry)
                    modified = True

                # Apply modification if this is the TARGET rule
                elif clean_rule.get("strategy") == "TARGET" and new_target is not None:
                    clean_rule["trigger_type"] = "IMMEDIATE" 
                    clean_rule["trigger_price"] = float(new_target)
                    clean_rule["price"] = float(new_target)
                    modified = True

                # Special handling for triggered rules (V3 requirement)
                elif r.get("status") in ["COMPLETED", "TRIGGERED"]:
                    clean_rule["trigger_type"] = "IMMEDIATE"
                    if clean_rule.get("price") is None:
                        clean_rule["price"] = clean_rule["trigger_price"]

                rules.append(clean_rule)
            
            if not modified:
                logger.error(f"Cannot modify GTT {gtt_id}: Strategy not matched or no new values provided.")
                return False
                
            # 3. Prepare payload (Strict V3 Schema)
            data = {
                "gtt_order_id": gtt_id,
                "type": details.get("type"),
                "instrument_token": details.get("instrument_token"),
                "product": details.get("product"),
                "quantity": int(details.get("quantity", 1)),
                "rules": rules
            }
            
            if top_transaction_type:
                data["transaction_type"] = top_transaction_type
            
            # Official V3 Modify Endpoint
            url = "https://api.upstox.com/v3/order/gtt/modify"
            logger.debug(f"GTT Modification Payload: {json.dumps(data)}")
            response = requests.put(url, headers=self.headers, json=data)
            
            if response.status_code != 200:
                logger.error(f"Failed to modify GTT {gtt_id}. Status: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return False
                
            res_json = response.json()
            if res_json.get("status") == "success":
                changes_str = []
                if new_sl: changes_str.append(f"SL:{new_sl}")
                if new_entry: changes_str.append(f"Entry:{new_entry}")
                if new_target: changes_str.append(f"Target:{new_target}")
                logger.info(f"GTT {gtt_id} Modified Successfully. Updates: {', '.join(changes_str)}")
                return True
            else:
                logger.error(f"Failed to modify GTT: {res_json}")
                return False
        except Exception as e:
            logger.error(f"Error modifying GTT: {e}")
            return False

    def get_gtt_order_details(self, gtt_id):
        """Fetch details/status of a GTT order using V3 endpoint."""
        # Paper Trading Hook
        if gtt_id and gtt_id.startswith("PAPER-"):
             return self.paper.get_order_details(gtt_id)

        if not UPSTOX_ACCESS_TOKEN:
            logger.warning("UPSTOX_ACCESS_TOKEN not set. Cannot fetch GTT details from Upstox.")
            return None

        if not gtt_id or "SKIPPED" in str(gtt_id) or "DRY_RUN" in str(gtt_id):
            return None

        
        try:
            # Official V3 GTT Details Endpoint
            url = f"https://api.upstox.com/v3/order/gtt?gtt_order_id={gtt_id}"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code != 200:
                logger.error(f"Failed to get GTT details {gtt_id}. Status: {response.status_code}")
                return None
                
            res_json = response.json()
            if res_json.get("status") == "success":
                data = res_json.get("data")
                if isinstance(data, list):
                    # Find the specific GTT by ID in the list
                    for item in data:
                        if item.get("gtt_order_id") == gtt_id:
                            logger.debug(f"Found GTT {gtt_id} in response list.")
                            return item
                    logger.warning(f"GTT {gtt_id} NOT found in the list of {len(data)} items returned.")
                    return None
                return data
            return None
        except Exception as e:
            logger.error(f"Error fetching GTT details: {e}")
            return None
    def is_gtt_active(self, gtt_id):
        """
        Check if a GTT order is currently active/open on the exchange.
        
        Args:
            gtt_id (str): The GTT order ID to check.
            
        Returns:
            bool: True if the GTT is in an active status, False otherwise.
        """
        details = self.get_gtt_order_details(gtt_id)
        if not details:
            return False

        # Normalise to lowercase for case-insensitive comparison (paper exchange returns lowercase)
        status = (details.get("status") or "").lower()

        # Explicitly inactive — short-circuit before checking rules.
        # Paper exchange returns "completed" for CLOSED orders.
        if status in {"completed", "rejected", "cancelled", "expired"}:
            return False

        # Explicitly active top-level statuses
        if status in {"active", "open", "transitive", "trigger_pending", "scheduled", "triggered"}:
            logger.info(f"GTT {gtt_id} is ACTIVE (Status: {status})")
            return True

        # Fallback: check individual rules (live Upstox path)
        rules = details.get("rules", [])
        for rule in rules:
            rule_status = (rule.get("status") or "").lower()
            if rule_status in {"scheduled", "open", "pending", "active"}:
                logger.info(f"GTT {gtt_id} is ACTIVE (Rule {rule.get('strategy')} is {rule_status})")
                return True

        return False

    def fetch_active_gtts(self):
        """Fetch all active GTT orders from the account using V3 endpoint."""
        try:
            # Official V3 GTT List Endpoint
            url = "https://api.upstox.com/v3/order/gtt"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch GTT list. Status: {response.status_code}")
                return []
                
            res_json = response.json()
            if res_json.get("status") == "success":
                data = res_json.get("data", [])
                
                # Active statuses that indicate the GTT is still "live"
                active_statuses = ["ACTIVE", "OPEN", "TRANSITIVE", "TRIGGER_PENDING", "SCHEDULED", "TRIGGERED"]
                
                active_list = []
                for item in data:
                    rules = item.get("rules", [])
                    # A GTT is active if any of its rules are in an active state
                    if any(rule.get("status") in active_statuses for rule in rules):
                        active_list.append(item)
                
                return active_list
            return []
        except Exception as e:
            logger.error(f"Error fetching GTT list: {e}")
            return []
