"""
Test functions for checking Bybit API functionality

This module contains functions for testing connection
and basic operations with Bybit API.
"""

import logging
from helpers import BybitHelper


def test_connection(helper: BybitHelper):
    """
    Test connection and display balance and price information

    Args:
        helper: BybitHelper instance
    """
    logging.info("1. Get all balance")
    helper.assets()
    logging.info("----------------")

    logging.info("2. Get available coin balance (XRP)")
    avbl = helper.get_wallet_balance("XRP")
    logging.info(str(avbl))
    logging.info("----------------")

    logging.info("3. Get price (XRPUSDT)")
    r = helper.get_instrument_info(category="spot", symbol="XRPUSDT")
    logging.info(str(r))
    logging.info("----------------")


def test_place_order(helper: BybitHelper):
    """
    Test order placement - buy XRP for USDT then sell all XRP
    
    Args:
        helper: BybitHelper instance
    """
    import time
    
    buy_amount_usdt = 20  # Buy XRP for 20 USDT (above minimum order value)
    symbol = "XRPUSDT"
    category = "spot"
    
    # Step 1: Place buy order (buy XRP for USDT amount)
    logging.info(f"4. Place BUY order - {buy_amount_usdt} USDT worth of XRP ({symbol})")
    buy_response = helper.place_order(
        category=category,
        symbol=symbol,
        side="Buy",
        order_type="Market",
        qty=buy_amount_usdt,
        market_unit="quoteCoin",  # Changed to quoteCoin to buy for USDT amount
    )
    logging.info(f"Buy order response: {buy_response}")
    
    if buy_response.get("retCode") != 0:
        logging.error(f"Buy order failed: {buy_response.get('retMsg')}")
        return
    
    buy_order_id = buy_response.get("result", {}).get("orderId")
    logging.info(f"Buy order placed successfully. ID: {buy_order_id}")
    logging.info("----------------")
    
    # Step 2: Wait a moment for market order to be processed
    logging.info("Market order placed, waiting for processing...")
    time.sleep(3)  # Market orders are usually filled instantly, just wait a bit for system to update
    
    # Check if order was filled by looking at order history
    try:
        if helper.client:
            # Get order history to confirm execution
            history_response = helper.client.get_order_history(
                category=category,
                symbol=symbol,
                orderId=buy_order_id
            )
            
            # Handle different response formats
            if isinstance(history_response, tuple):
                history_data = history_response[0]
            else:
                history_data = history_response
            
            orders = history_data.get("result", {}).get("list", [])
            if orders:
                order_status = orders[0].get("orderStatus", "")
                if order_status == "Filled":
                    logging.info("Buy order has been filled successfully!")
                else:
                    logging.info(f"Buy order status: {order_status}")
            else:
                logging.info("Buy order completed (market orders fill instantly)")
                
    except Exception as e:
        logging.info(f"Could not check order history: {str(e)}")
        logging.info("Assuming market order was filled (market orders typically fill instantly)")
    
    logging.info("----------------")
    
    # Step 3: Get actual XRP balance after purchase
    logging.info("Getting actual XRP balance after purchase...")
    actual_xrp_balance = helper.get_wallet_balance("XRP")
    logging.info(f"Actual XRP wallet balance: {actual_xrp_balance}")
    
    if actual_xrp_balance <= 0:
        logging.error("No XRP balance available for selling")
        return
    
    # Round quantity to proper decimal places for XRP (usually 1-2 decimal places)
    sell_quantity = helper.round_down(actual_xrp_balance, 1)  # Round to 1 decimal place for XRP
    logging.info(f"Rounded sell quantity: {sell_quantity} XRP")
    
    if sell_quantity <= 0:
        logging.error("Rounded sell quantity is 0 or negative")
        return
    
    # Step 4: Place sell order with actual balance
    logging.info(f"5. Place SELL order - {sell_quantity} XRP ({symbol})")
    sell_response = helper.place_order(
        category=category,
        symbol=symbol,
        side="Sell",
        order_type="Market",
        qty=sell_quantity,
        market_unit="baseCoin",
    )
    logging.info(f"Sell order response: {sell_response}")
    
    if sell_response.get("retCode") != 0:
        logging.error(f"Sell order failed: {sell_response.get('retMsg')}")
        return
    
    sell_order_id = sell_response.get("result", {}).get("orderId")
    logging.info(f"Sell order placed successfully. ID: {sell_order_id}")
    logging.info("----------------")
