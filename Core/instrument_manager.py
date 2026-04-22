import logging
import requests
import json
import os
from config import UPSTOX_MARKET_QUOTE_URL, UPSTOX_ACCESS_TOKEN, DATA_FILENAME
from DataLoader.mcx_instrument_loader import download_and_process_instruments

logger = logging.getLogger("GOLD_MAIN")

class InstrumentManager:
    def __init__(self):
        pass

    def fetch_instruments(self):
        """
        Loads instruments from local file if exists, otherwise downloads them.
        """
        if os.path.exists(DATA_FILENAME):
            try:
                with open(DATA_FILENAME, 'r') as f:
                    data = json.load(f)
                    logger.info(f"Loaded {len(data)} instruments from {DATA_FILENAME}")
                    return data
            except Exception as e:
                logger.error(f"Error loading {DATA_FILENAME}: {e}. Downloading fresh.")
        
        return download_and_process_instruments()

    def filter_gold_ten_fut(self, instruments):
        """
        Filters instruments for 'GOLDTEN' asset symbol and 'FUT' instrument type.
        """
        filtered_instruments = []
        if not instruments:
            return filtered_instruments

        for inst in instruments:
            asset_symbol = inst.get("asset_symbol", "").upper()
            instrument_type = inst.get("instrument_type", "").upper()
            
            if asset_symbol == "GOLDTEN" and instrument_type == "FUT":
                filtered_instruments.append(inst)
                
        return filtered_instruments

    def get_market_quotes(self, instrument_keys):
        """
        Fetches full market quotes for the given instrument keys.
        """
        if not UPSTOX_ACCESS_TOKEN or UPSTOX_ACCESS_TOKEN == "YOUR_ACCESS_TOKEN_HERE":
            logger.error("UPSTOX_ACCESS_TOKEN is not set in config.py. Cannot fetch market quotes.")
            return None

        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {UPSTOX_ACCESS_TOKEN}'
        }
        
        # Construct comma-separated string of instrument keys
        keys_str = ",".join(instrument_keys)
        # Use params for proper encoding
        params = {'instrument_key': keys_str}
        
        try:
            response = requests.get(UPSTOX_MARKET_QUOTE_URL, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            if data.get("status") == "success":
                return data.get("data", {})
            else:
                logger.error(f"API Error: {data}")
                return None
        except Exception as e:
            logger.error(f"Failed to fetch market quotes: {e}")
            return None

    def calculate_rank(self, candidates, quotes):
        """
        Calculates the best contract based on Volume and OI ranking.
        Returns the best instrument dictionary from candidates.
        """
        if not candidates or not quotes:
            return None

        # Create a map of instrument_key -> expiry
        expiry_map = {}
        for cand in candidates:
            k = cand.get("instrument_key")
            e = cand.get("expiry")
            if k and e:
                try:
                    expiry_map[k] = int(e)
                except ValueError:
                    expiry_map[k] = float('inf')

        logger.info(f"Available Quote Keys: {list(quotes.keys())}")
        
        scored_candidates = []
        
        # Iterate through quotes directly to inspect data
        for q_key, q_data in quotes.items():
            q_vol = q_data.get('volume', 0)
            q_oi = q_data.get('oi', 0)
            q_symbol = q_data.get('symbol', "")
            # Note: Some APIs return 'instrument_token' or use the key itself.
            # We'll use the key from the loop if needed.
            q_inst = q_data.get('instrument_token', q_key) 
            
            # Get expiry, default to high value if not found
            # Try q_key first, then q_inst (instrument_token) which matches candidates 'instrument_key'
            q_expiry = expiry_map.get(q_key, expiry_map.get(q_inst, float('inf')))

            logger.info(f"Quote Data - Key: {q_key} | Vol: {q_vol} | OI: {q_oi} | Expiry: {q_expiry}")
            scored_candidates.append({
                "symbol": q_symbol,
                "instrument_token": q_inst,
                "volume": q_vol,
                "oi": q_oi,
                "expiry": q_expiry,
                "vol_rank": 0,
                "oi_rank": 0,
                "total_score": 0
            })
        
        if not scored_candidates:
            return None

        # Rank by Volume (Higher is better)
        scored_candidates.sort(key=lambda x: x["volume"], reverse=True)
        for i, item in enumerate(scored_candidates):
            # Rank 1 gets N points, Rank N gets 1 point
            item["vol_rank"] = len(scored_candidates) - i

        # Rank by OI (Higher is better)
        scored_candidates.sort(key=lambda x: x["oi"], reverse=True)
        for i, item in enumerate(scored_candidates):
            item["oi_rank"] = len(scored_candidates) - i

        # Calculate Total Score
        for item in scored_candidates:
            item["total_score"] = item["vol_rank"] + item["oi_rank"]
            logger.info(f"Contract: {item['symbol']} | Vol: {item['volume']} (Rank {item['vol_rank']}) | OI: {item['oi']} (Rank {item['oi_rank']}) | Total: {item['total_score']} | Expiry: {item['expiry']}")

        # Sort by:
        # 1. Total Score (DESC)
        # 2. Expiry (ASC) -> Earlier expiry is better. We use -expiry for DESC sort.
        # 3. Volume (DESC) -> Higher volume is better.
        scored_candidates.sort(key=lambda x: (x["total_score"], -x["expiry"], x["volume"]), reverse=True)

        best_candidate = scored_candidates[0]["instrument_token"]
        return best_candidate

    def get_active_contract(self):
        """
        Identifies the active contract from a list of instruments.
        Sorts by expiry and compares Volume/OI for all candidates.
        """
        instruments = self.fetch_instruments()
        filtered_instruments = self.filter_gold_ten_fut(instruments)
        del instruments  # release full MCX list (~MB) from memory

        if not filtered_instruments:
            logger.warning("No GOLDTEN FUT instruments found.")
            return None

        # Sort by expiry
        try:
            filtered_instruments.sort(key=lambda x: int(x.get("expiry", float('inf'))))
        except Exception as e:
            logger.warning(f"Error sorting by expiry: {e}")
            return None

        # Use only the nearest 2 instrument candidate
        candidates = filtered_instruments[:2]
        
        logger.info("Nearest Contract selected for analysis:")
        instrument_keys = []
        
        for inst in candidates:
            tk = inst.get("instrument_key")
            s = inst.get("trading_symbol")
            e = inst.get("expiry")
            if tk:
                instrument_keys.append(tk)
            logger.info(f"  Symbol: {s}, Expiry: {e}, Key: {tk}")

        if not instrument_keys:
            logger.warning("No instrument keys found.")
            return None

        logger.info("Fetching Market Quotes for Active Contract...")
        quotes = self.get_market_quotes(instrument_keys)
        
        if not quotes:
            logger.warning("No market quotes returned.")
            return None
            
        logger.debug(f"Quotes Keys: {list(quotes.keys())}")

        # Calculate Rank
        best_contract = self.calculate_rank(candidates, quotes)

        if best_contract:
            logger.info(f"ACTIVE CONTRACT IDENTIFIED: {best_contract}")
            return best_contract
        else:
            logger.warning("Could not determine active contract from quotes.")
            return None
