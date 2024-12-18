"""
Trading strategies for Bybit bot

This module contains various trading strategies
that can be used with the Bybit API.
"""

import time
import logging
from datetime import datetime
from helpers import BybitHelper


def run_trailing_stop_strategy(
    helper: BybitHelper, coin: str, buy_amount: float, check_interval: int = 5
):
    """
    Trading strategy with trailing stop and dual entry conditions.

    Algorithm workflow:

    1. Entry Point Search (checks every 5 seconds):
    - Option 1: Price drop of 3% over 3 hours (price_drop_threshold = -3, hours_period = 3)
    - Option 2: Quick rise of 3% over 1 hour (quick_rise_threshold = 3, quick_period = 1)
    - Buys for buy_amount in USDT

    2. After Position Entry:
    - Saves number of coins bought: position_size = buy_amount / current_price
    - Sets initial points:
        * entry_price = entry price
        * trailing_price = entry price

    3. Position Management (monitoring every 5 seconds):
    - Logs display:
        * Change from entry
        * Change from trailing level
        * Change over last hour

    - Trailing Update:
        * If price rises 3% from trailing level (trailing_update_threshold = 3)
        * Moves trailing stop to current price
        * Logs new level and total profit

    - Position Exit:
        * If price falls 1% from trailing level (trailing_drop_threshold = -1)
        * Sells ALL purchased coins (position_size)
        * Logs final profit
        * Resets all position variables

    Current settings features:
    1. Quick trailing stop trigger (just 1% drop)
    2. Significant trailing update (only on 3% rise)
    3. Same thresholds for quick entry and trailing update (3%)
    4. Relatively long period for drop entry (3 hours)

    Algorithm is tuned for:
    - Quick profit taking (sell at -1% from maximum)
    - Protection from false trailing updates (needs +3% rise)
    - Finding both long-term dips (-3% over 3h) and quick movements (+3% over 1h)

    Args:
        helper: BybitHelper instance
        coin: coin name (e.g., "XRP")
        buy_amount: amount in USDT to buy
        check_interval: price check interval in seconds (default: 5)
    """
    symbol = f"{coin}USDT"
    category = "spot"
    # buying
    price_drop_threshold = -3  # price drop threshold for buying
    hours_period = 3  # period for tracking price change for entry
    quick_rise_threshold = 3  # quick price rise threshold for buying
    quick_period = 1  # period for tracking quick rise
    # selling
    trailing_update_threshold = 3  # threshold to update trailing stop (%)
    trailing_drop_threshold = -1  # price drop threshold for trailing stop (%)
    monitoring_period = 1  # period for tracking price change after entry
    entry_price = None  # position entry price
    trailing_price = None  # trailing stop price
    position_size = None  # amount of coins bought

    logging.info(f"Starting algorithm for {symbol}")
    logging.info(
        f"Position entry conditions:\n"
        f"1) Price drop of {abs(price_drop_threshold)}% over {hours_period} hours\n"
        f"2) Quick rise of {quick_rise_threshold}% over {quick_period} hour"
    )

    while True:
        try:
            # Get current price and changes over different periods
            current_price = helper.get_price(category, symbol)
            price_change = helper.get_price_change(category, symbol, hours=hours_period)
            quick_price_change = helper.get_price_change(
                category, symbol, hours=quick_period
            )

            # Format time for output
            current_time = datetime.now().strftime("%H:%M:%S")

            if entry_price is None:
                # If not in position, look for entry opportunity
                logging.info(
                    f"[{current_time}] {symbol} Price: {current_price:.4f} USDT "
                    f"(Change over {hours_period}h: {price_change:.2f}%, "
                    f"over {quick_period}h: {quick_price_change:.2f}%)"
                )

                # Check entry conditions
                if quick_price_change >= quick_rise_threshold:
                    logging.info(
                        f"\nQuick rise! Price increased by {quick_price_change:.2f}% in the last hour. Placing buy order."
                    )
                    r = helper.place_order(
                        category=category,
                        symbol=symbol,
                        side="Buy",
                        order_type="Market",
                        qty=buy_amount,
                        market_unit="quoteCoin",
                    )

                    if r.get("retCode") != 0:
                        error_msg = f"\nError placing buy order: {r.get('retMsg')}"
                        logging.error(error_msg)
                        raise Exception(f"Order placement error: {r.get('retMsg')}")

                    order_id = r.get("result", {}).get("orderId")
                    logging.info(f"Buy order placed successfully. ID: {order_id}")

                    entry_price = current_price
                    trailing_price = current_price
                    position_size = buy_amount / current_price
                    logging.info(f"Entered position at price: {entry_price:.4f} USDT")
                    logging.info(f"Position size: {position_size:.4f} {coin}")

                elif price_change <= price_drop_threshold:
                    logging.info(
                        f"\nPrice dropped by {abs(price_change):.2f}% over {hours_period} hours. Placing buy order."
                    )
                    r = helper.place_order(
                        category=category,
                        symbol=symbol,
                        side="Buy",
                        order_type="Market",
                        qty=buy_amount,
                        market_unit="quoteCoin",
                    )

                    if r.get("retCode") != 0:
                        error_msg = f"\nError placing buy order: {r.get('retMsg')}"
                        logging.error(error_msg)
                        raise Exception(f"Order placement error: {r.get('retMsg')}")

                    order_id = r.get("result", {}).get("orderId")
                    logging.info(f"Buy order placed successfully. ID: {order_id}")

                    entry_price = current_price
                    trailing_price = current_price
                    position_size = buy_amount / current_price
                    logging.info(f"Entered position at price: {entry_price:.4f} USDT")
                    logging.info(f"Position size: {position_size:.4f} {coin}")
                else:
                    logging.info(" (Waiting for signal)")
            else:
                # If in position, check trailing or exit conditions
                price_change_from_trailing = (
                    (current_price - trailing_price) / trailing_price
                ) * 100
                total_change_from_entry = (
                    (current_price - entry_price) / entry_price
                ) * 100

                # Get price change for monitoring period
                monitoring_price_change = helper.get_price_change(
                    category, symbol, hours=monitoring_period
                )

                logging.info(
                    f"[{current_time}] {symbol} Price: {current_price:.4f} USDT "
                    f"(From entry: {total_change_from_entry:.2f}%, "
                    f"From trailing: {price_change_from_trailing:.2f}%, "
                    f"Change over {monitoring_period}h: {monitoring_price_change:.2f}%)"
                )

                if price_change_from_trailing >= trailing_update_threshold:
                    # If price rises above threshold, update trailing
                    old_trailing = trailing_price
                    trailing_price = current_price
                    logging.info(
                        f"\nPrice increased by {price_change_from_trailing:.2f}% from last trailing point."
                    )
                    logging.info(
                        f"Updating trailing point: {old_trailing:.4f} -> {trailing_price:.4f} USDT"
                    )
                    logging.info(f"Total profit from entry: {total_change_from_entry:.2f}%")

                elif price_change_from_trailing <= trailing_drop_threshold:
                    # If price drops below threshold from maximum, sell
                    logging.info(
                        f"\nPrice dropped by {abs(price_change_from_trailing):.2f}% from trailing point. Placing sell order."
                    )
                    r = helper.place_order(
                        category=category,
                        symbol=symbol,
                        side="Sell",
                        order_type="Market",
                        qty=position_size,
                    )

                    if r.get("retCode") != 0:
                        error_msg = f"\nError placing sell order: {r.get('retMsg')}"
                        logging.error(error_msg)
                        raise Exception(f"Order placement error: {r.get('retMsg')}")

                    order_id = r.get("result", {}).get("orderId")
                    logging.info(f"Sell order placed successfully. ID: {order_id}")

                    logging.info(f"Closed position at price: {current_price:.4f} USDT")
                    logging.info(f"Final profit: {total_change_from_entry:.2f}%")
                    entry_price = None
                    trailing_price = None
                    position_size = None
                else:
                    logging.info(" (Monitoring price)")

            time.sleep(check_interval)

        except Exception as e:
            logging.error(f"\nCritical error: {str(e)}")
            logging.error("Stopping program...")
            break
