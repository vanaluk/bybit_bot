"""
Test functions for checking Bybit API functionality

This module contains functions for testing connection
and basic operations with Bybit API.
"""

import logging
from helpers import BybitHelper


def test_connection(helper: BybitHelper, coin="XRP"):
    """
    Test connection and display balance and price information

    Args:
        helper: BybitHelper instance
        coin: coin name (e.g., "XRP", "ETH3L") - defaults to "XRP" if not provided
    """
    logging.info("1. Get all balance")
    helper.assets()
    logging.info("----------------")

    logging.info(f"2. Get available coin balance ({coin})")
    avbl = helper.get_wallet_balance(coin)
    logging.info(str(avbl))
    logging.info("----------------")

    symbol = f"{coin}USDT"
    logging.info(f"3. Get price ({symbol})")
    r = helper.get_instrument_info(category="spot", symbol=symbol)
    logging.info(str(r))
    logging.info("----------------")


def test_place_order(helper: BybitHelper, coin="XRP"):
    """
    Test order placement - buy coin for USDT then sell all coin
    
    Args:
        helper: BybitHelper instance
        coin: coin name (e.g., "XRP", "ETH3L") - defaults to "XRP" if not provided
    """
    import time
    
    buy_amount_usdt = 20  # Buy coin for 20 USDT (above minimum order value)
    symbol = f"{coin}USDT"
    category = "spot"
    
    # Step 1: Place buy order (buy coin for USDT amount)
    logging.info(f"4. Place BUY order - {buy_amount_usdt} USDT worth of {coin} ({symbol})")
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
    
    # Step 3: Get actual coin balance after purchase
    logging.info(f"Getting actual {coin} balance after purchase...")
    actual_coin_balance = helper.get_wallet_balance(coin)
    logging.info(f"Actual {coin} wallet balance: {actual_coin_balance}")
    
    if actual_coin_balance <= 0:
        logging.error(f"No {coin} balance available for selling")
        return
    
    # Round quantity to proper decimal places based on coin type
    if coin in ["BTC", "ETH"]:
        decimal_places = 6  # High-value coins need more precision
    elif coin in ["XRP", "ADA", "DOGE", "TRX"]:
        decimal_places = 1  # Low-value coins typically use 1 decimal
    else:
        decimal_places = 2  # Default for most coins
        
    sell_quantity = helper.round_down(actual_coin_balance, decimal_places)
    logging.info(f"Rounded sell quantity: {sell_quantity} {coin}")
    
    if sell_quantity <= 0:
        logging.error("Rounded sell quantity is 0 or negative")
        return
    
    # Step 4: Place sell order with actual balance
    logging.info(f"5. Place SELL order - {sell_quantity} {coin} ({symbol})")
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
