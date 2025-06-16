"""
Trading strategies for Bybit bot

This module contains various trading strategies
that can be used with the Bybit API.
"""

import logging
import random
import time
from datetime import datetime

from helpers import BybitHelper


def retry_on_error(max_retries=3, delay=5):
    """
    Decorator for retrying operations on error

    Args:
        max_retries: maximum number of retry attempts
        delay: delay between retries in seconds
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries == max_retries:
                        logging.error(
                            f"Maximum retry attempts reached ({max_retries}). Last error: {str(e)}"
                        )
                        raise
                    wait_time = delay + random.uniform(0, 2)  # Add random jitter
                    logging.warning(
                        f"Error executing {func.__name__}: {str(e)}. Retry {retries}/{max_retries} in {wait_time:.1f} sec..."
                    )
                    time.sleep(wait_time)
            return None

        return wrapper

    return decorator


@retry_on_error(max_retries=3, delay=5)
def safe_get_price(helper: BybitHelper, category: str, symbol: str) -> float:
    """Safe price retrieval with retry mechanism"""
    return helper.get_price(category, symbol)


@retry_on_error(max_retries=3, delay=5)
def safe_get_price_change(
    helper: BybitHelper, category: str, symbol: str, hours: int
) -> float:
    """Safe price change retrieval with retry mechanism"""
    return helper.get_price_change(category, symbol, hours)


@retry_on_error(max_retries=3, delay=5)
def safe_place_order(helper: BybitHelper, **kwargs):
    """Safe order placement with retry mechanism"""
    return helper.place_order(**kwargs)


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

    - Minimum Profit Protection:
        * Won't sell until profit reaches minimum_profit_threshold (2%)
        * Before reaching minimum profit, only updates trailing upward

    - Trailing Update (only after minimum profit reached):
        * If price rises 3% from trailing level (trailing_update_threshold = 3)
        * Moves trailing stop to current price
        * Logs new level and total profit

    - Position Exit (only after minimum profit reached):
        * If price falls 1% from trailing level (trailing_drop_threshold = -1)
        * Sells ALL purchased coins (position_size)
        * Logs final profit
        * Resets all position variables

    Current settings features:
    1. Minimum profit protection (won't sell in loss)
    2. Quick trailing stop trigger (just 1% drop after reaching minimum profit)
    3. Significant trailing update (only on 3% rise)
    4. Same thresholds for quick entry and trailing update (3%)
    5. Relatively long period for drop entry (3 hours)

    Algorithm is tuned for:
    - Avoiding losses (minimum profit protection)
    - Quick profit taking after reaching minimum threshold
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
    minimum_profit_threshold = 2  # minimum profit before activating trailing stop (%)
    trailing_update_threshold = 3  # threshold to update trailing stop (%)
    trailing_drop_threshold = -1  # price drop threshold for trailing stop (%)
    monitoring_period = 1  # period for tracking price change after entry
    entry_price = None  # position entry price
    trailing_price = None  # trailing stop price
    position_size = None  # amount of coins bought
    trailing_activated = False  # whether trailing stop is activated

    logging.info(f"Starting algorithm for {symbol}")
    logging.info(
        f"Position entry conditions:\n"
        f"1) Price drop of {abs(price_drop_threshold)}% over {hours_period} hours\n"
        f"2) Quick rise of {quick_rise_threshold}% over {quick_period} hour"
    )
    logging.info(
        f"Position management:\n"
        f"- Minimum profit before trailing: {minimum_profit_threshold}%\n"
        f"- Trailing update threshold: {trailing_update_threshold}%\n"
        f"- Trailing drop threshold: {trailing_drop_threshold}%"
    )

    consecutive_errors = 0
    max_consecutive_errors = 5

    while True:
        try:
            # Get current price and changes over different periods
            current_price = safe_get_price(helper, category, symbol)
            price_change = safe_get_price_change(
                helper, category, symbol, hours=hours_period
            )
            quick_price_change = safe_get_price_change(
                helper, category, symbol, hours=quick_period
            )

            # Reset error counter on successful execution
            consecutive_errors = 0

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

                    # Get wallet balance before buying
                    balance_before = helper.get_wallet_balance(coin)
                    logging.info(f"Balance before buying: {balance_before:.8f} {coin}")

                    r = safe_place_order(
                        helper,
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

                    # Get wallet balance after buying
                    balance_after = helper.get_wallet_balance(coin)
                    logging.info(f"Balance after buying: {balance_after:.8f} {coin}")

                    # Calculate exact amount bought
                    bought_amount = balance_after - balance_before
                    logging.info(f"Exact amount bought: {bought_amount:.8f} {coin}")

                    entry_price = current_price
                    trailing_price = current_price
                    position_size = (
                        bought_amount  # Use actual bought amount instead of calculation
                    )
                    trailing_activated = False  # Reset trailing activation
                    logging.info(f"Entered position at price: {entry_price:.4f} USDT")
                    logging.info(f"Position size: {position_size:.8f} {coin}")

                elif price_change <= price_drop_threshold:
                    logging.info(
                        f"\nPrice dropped by {abs(price_change):.2f}% over {hours_period} hours. Placing buy order."
                    )

                    # Get wallet balance before buying
                    balance_before = helper.get_wallet_balance(coin)
                    logging.info(f"Balance before buying: {balance_before:.8f} {coin}")

                    r = safe_place_order(
                        helper,
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

                    # Get wallet balance after buying
                    balance_after = helper.get_wallet_balance(coin)
                    logging.info(f"Balance after buying: {balance_after:.8f} {coin}")

                    # Calculate exact amount bought
                    bought_amount = balance_after - balance_before
                    logging.info(f"Exact amount bought: {bought_amount:.8f} {coin}")

                    entry_price = current_price
                    trailing_price = current_price
                    position_size = (
                        bought_amount  # Use actual bought amount instead of calculation
                    )
                    trailing_activated = False  # Reset trailing activation
                    logging.info(f"Entered position at price: {entry_price:.4f} USDT")
                    logging.info(f"Position size: {position_size:.8f} {coin}")
                else:
                    logging.info(" (Waiting for signal)")
            else:
                # If in position, check trailing or exit conditions
                price_change_from_trailing = (
                    ((current_price - trailing_price) / trailing_price) * 100
                    if trailing_price is not None
                    else 0.0
                )
                total_change_from_entry = (
                    ((current_price - entry_price) / entry_price) * 100
                    if entry_price is not None
                    else 0.0
                )

                # Get price change for monitoring period
                monitoring_price_change = safe_get_price_change(
                    helper, category, symbol, hours=monitoring_period
                )

                # Determine status
                if not trailing_activated:
                    if total_change_from_entry >= minimum_profit_threshold:
                        trailing_activated = True
                        logging.info(
                            f"\n🟢 Minimum profit reached! Profit: {total_change_from_entry:.2f}% >= {minimum_profit_threshold}%"
                        )
                        logging.info("Trailing stop mechanism activated!")
                    status_msg = f"(Waiting for {minimum_profit_threshold}% profit)"
                else:
                    status_msg = "(Trailing active)"

                logging.info(
                    f"[{current_time}] {symbol} Price: {current_price:.4f} USDT "
                    f"(From entry: {total_change_from_entry:.2f}%, "
                    f"From trailing: {price_change_from_trailing:.2f}%, "
                    f"Change over {monitoring_period}h: {monitoring_price_change:.2f}%) {status_msg}"
                )

                # Check if we can activate trailing stop
                if not trailing_activated and total_change_from_entry >= minimum_profit_threshold:
                    trailing_activated = True
                    logging.info(
                        f"\n🟢 Minimum profit reached! Profit: {total_change_from_entry:.2f}% >= {minimum_profit_threshold}%"
                    )
                    logging.info("Trailing stop mechanism activated!")

                # Update trailing price if conditions are met
                if price_change_from_trailing >= trailing_update_threshold:
                    # Always update trailing if price rises above threshold
                    old_trailing = trailing_price
                    trailing_price = current_price
                    logging.info(
                        f"\nPrice increased by {price_change_from_trailing:.2f}% from last trailing point."
                    )
                    logging.info(
                        f"Updating trailing point: {old_trailing:.4f} -> {trailing_price:.4f} USDT"
                    )
                    logging.info(
                        f"Total profit from entry: {total_change_from_entry:.2f}%"
                    )

                # Check exit conditions only if trailing is activated
                elif trailing_activated and price_change_from_trailing <= trailing_drop_threshold:
                    # If price drops below threshold from maximum AND trailing is activated, sell
                    logging.info(
                        f"\n🔴 Price dropped by {abs(price_change_from_trailing):.2f}% from trailing point."
                    )
                    logging.info(f"Final profit: {total_change_from_entry:.2f}% (≥ {minimum_profit_threshold}%)")
                    logging.info("Placing sell order.")

                    # Use the exact position_size that was calculated after buying
                    if position_size is None or position_size <= 0:
                        logging.error(f"No {coin} position available for selling")
                        # Reset position variables since we can't sell
                        entry_price = None
                        trailing_price = None
                        position_size = None
                        trailing_activated = False
                        continue

                    # Round quantity to proper decimal places based on coin type
                    if coin in ["BTC", "ETH"]:
                        decimal_places = 6  # High-value coins need more precision
                    elif coin in ["XRP", "ADA", "DOGE", "TRX"]:
                        decimal_places = 1  # Low-value coins typically use 1 decimal
                    else:
                        decimal_places = 2  # Default for most coins

                    sell_quantity = helper.round_down(position_size, decimal_places)

                    logging.info(f"Position size to sell: {position_size:.8f} {coin}")
                    logging.info(
                        f"Selling quantity: {sell_quantity} {coin} (rounded to {decimal_places} decimals)"
                    )

                    r = safe_place_order(
                        helper,
                        category=category,
                        symbol=symbol,
                        side="Sell",
                        order_type="Market",
                        qty=sell_quantity,
                        market_unit="baseCoin",
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
                    trailing_activated = False
                elif not trailing_activated:
                    logging.info(f" (Need {minimum_profit_threshold - total_change_from_entry:.2f}% more for trailing activation)")
                else:
                    logging.info(" (Monitoring price)")

            time.sleep(check_interval)

        except Exception as e:
            consecutive_errors += 1
            logging.error(f"\nError executing strategy: {str(e)}")

            if consecutive_errors >= max_consecutive_errors:
                logging.error(
                    f"Maximum consecutive errors reached ({max_consecutive_errors}). Restarting strategy..."
                )
                # Reset all position variables
                entry_price = None
                trailing_price = None
                position_size = None
                trailing_activated = False
                consecutive_errors = 0
                time.sleep(30)  # Wait 30 seconds before restart
                continue

            logging.warning(
                f"Continuing after error. Attempt {consecutive_errors}/{max_consecutive_errors}"
            )
            time.sleep(check_interval * 2)  # Increase wait interval on error
            continue


def run_trailing_stop_strategy_whitelist(
    helper: BybitHelper,
    coin_whitelist: list,
    buy_amount: float,
    check_interval: int = 10
):
    """
    Trading strategy with trailing stop for whitelist of coins.

    Algorithm workflow:

    1. Whitelist Scanning Phase:
    - Monitors ALL coins from whitelist simultaneously
    - Checks entry conditions for each coin:
      * Option 1: Price drop of 3% over 3 hours
      * Option 2: Quick rise of 3% over 1 hour
    - As soon as ANY coin meets entry conditions - buys it and switches to single-coin mode

    2. Single-Coin Management Phase:
    - Works exactly like run_trailing_stop_strategy for the selected coin
    - Minimum profit protection (2% before trailing activation)
    - Trailing stop mechanism after reaching minimum profit
    - Exits when trailing stop is triggered

    3. Return to Whitelist Phase:
    - After closing position, returns to scanning all whitelist coins
    - Cycle repeats

    Args:
        helper: BybitHelper instance
        coin_whitelist: list of coin names (e.g., ["XRP", "ETH", "BTC"])
        buy_amount: amount in USDT to buy
        check_interval: price check interval in seconds (default: 10 for whitelist scanning)
    """
    category = "spot"

    # Entry conditions
    price_drop_threshold = -3
    hours_period = 3
    quick_rise_threshold = 3
    quick_period = 1

    # Position management
    minimum_profit_threshold = 2
    trailing_update_threshold = 3
    trailing_drop_threshold = -1
    monitoring_period = 1

    # Position variables
    current_coin = None
    entry_price = None
    trailing_price = None
    position_size = None
    trailing_activated = False

    logging.info(f"Starting whitelist algorithm for coins: {coin_whitelist}")
    logging.info(f"Buy amount: {buy_amount} USDT")
    logging.info(
        f"Entry conditions:\n"
        f"1) Price drop of {abs(price_drop_threshold)}% over {hours_period} hours\n"
        f"2) Quick rise of {quick_rise_threshold}% over {quick_period} hour"
    )
    logging.info(
        f"Position management:\n"
        f"- Minimum profit before trailing: {minimum_profit_threshold}%\n"
        f"- Trailing update threshold: {trailing_update_threshold}%\n"
        f"- Trailing drop threshold: {trailing_drop_threshold}%"
    )

    consecutive_errors = 0
    max_consecutive_errors = 5

    while True:
        try:
            current_time = datetime.now().strftime("%H:%M:%S")

            if current_coin is None:
                # WHITELIST SCANNING PHASE
                logging.info(f"\n[{current_time}] 🔍 Scanning whitelist coins...")

                best_opportunity = None
                best_score = 0

                # Check all coins in whitelist
                for coin in coin_whitelist:
                    symbol = f"{coin}USDT"

                    try:
                        # Get price data for this coin
                        current_price = safe_get_price(helper, category, symbol)
                        price_change = safe_get_price_change(helper, category, symbol, hours=hours_period)
                        quick_price_change = safe_get_price_change(helper, category, symbol, hours=quick_period)

                        logging.info(
                            f"  {symbol}: {current_price:.4f} USDT "
                            f"({hours_period}h: {price_change:.2f}%, {quick_period}h: {quick_price_change:.2f}%)"
                        )

                        # Check entry conditions and calculate priority score
                        score = 0
                        reason = ""

                        if quick_price_change >= quick_rise_threshold:
                            score = abs(quick_price_change)  # Higher rise = higher priority
                            reason = f"Quick rise {quick_price_change:.2f}%"
                        elif price_change <= price_drop_threshold:
                            score = abs(price_change)  # Bigger drop = higher priority
                            reason = f"Price drop {price_change:.2f}%"

                        if score > best_score:
                            best_score = score
                            best_opportunity = {
                                'coin': coin,
                                'symbol': symbol,
                                'price': current_price,
                                'reason': reason,
                                'quick_change': quick_price_change,
                                'long_change': price_change
                            }

                    except Exception as e:
                        logging.warning(f"  Error checking {symbol}: {str(e)}")
                        continue

                # If we found an opportunity, execute it
                if best_opportunity:
                    coin = best_opportunity['coin']
                    symbol = best_opportunity['symbol']
                    current_price = best_opportunity['price']
                    reason = best_opportunity['reason']

                    logging.info("\n🎯 ENTRY SIGNAL FOUND!")
                    logging.info(f"Selected coin: {symbol}")
                    logging.info(f"Reason: {reason}")
                    logging.info(f"Price: {current_price:.4f} USDT")
                    logging.info("Placing buy order...")

                    # Get wallet balance before buying
                    balance_before = helper.get_wallet_balance(coin)
                    logging.info(f"Balance before buying: {balance_before:.8f} {coin}")

                    # Place buy order
                    r = safe_place_order(
                        helper,
                        category=category,
                        symbol=symbol,
                        side="Buy",
                        order_type="Market",
                        qty=buy_amount,
                        market_unit="quoteCoin",
                    )

                    if r.get("retCode") != 0:
                        error_msg = f"Error placing buy order: {r.get('retMsg')}"
                        logging.error(error_msg)
                        raise Exception(f"Order placement error: {r.get('retMsg')}")

                    order_id = r.get("result", {}).get("orderId")
                    logging.info(f"✅ Buy order placed successfully. ID: {order_id}")

                    # Get wallet balance after buying
                    balance_after = helper.get_wallet_balance(coin)
                    logging.info(f"Balance after buying: {balance_after:.8f} {coin}")

                    # Calculate exact amount bought
                    bought_amount = balance_after - balance_before
                    logging.info(f"Exact amount bought: {bought_amount:.8f} {coin}")

                    # Set position variables
                    current_coin = coin
                    entry_price = current_price
                    trailing_price = current_price
                    position_size = bought_amount
                    trailing_activated = False

                    logging.info(f"🔄 Switched to single-coin mode: {symbol}")
                    logging.info(f"Entry price: {entry_price:.4f} USDT")
                    logging.info(f"Position size: {position_size:.8f} {coin}")

                else:
                    logging.info("  ⏳ No entry signals found. Continuing scan...")

            else:
                # SINGLE-COIN MANAGEMENT PHASE
                symbol = f"{current_coin}USDT"

                # Get current price and changes
                current_price = safe_get_price(helper, category, symbol)
                monitoring_price_change = safe_get_price_change(helper, category, symbol, hours=monitoring_period)

                # Calculate position metrics
                price_change_from_trailing = (
                    ((current_price - trailing_price) / trailing_price) * 100
                    if trailing_price is not None else 0.0
                )
                total_change_from_entry = (
                    ((current_price - entry_price) / entry_price) * 100
                    if entry_price is not None else 0.0
                )

                # Determine status
                if not trailing_activated:
                    if total_change_from_entry >= minimum_profit_threshold:
                        trailing_activated = True
                        logging.info(
                            f"\n🟢 Minimum profit reached! Profit: {total_change_from_entry:.2f}% >= {minimum_profit_threshold}%"
                        )
                        logging.info("Trailing stop mechanism activated!")
                    status_msg = f"(Waiting for {minimum_profit_threshold}% profit)"
                else:
                    status_msg = "(Trailing active)"

                logging.info(
                    f"[{current_time}] {symbol} Price: {current_price:.4f} USDT "
                    f"(From entry: {total_change_from_entry:.2f}%, "
                    f"From trailing: {price_change_from_trailing:.2f}%, "
                    f"Change over {monitoring_period}h: {monitoring_price_change:.2f}%) {status_msg}"
                )

                # Check if we can activate trailing stop
                if not trailing_activated and total_change_from_entry >= minimum_profit_threshold:
                    trailing_activated = True
                    logging.info(
                        f"\n🟢 Minimum profit reached! Profit: {total_change_from_entry:.2f}% >= {minimum_profit_threshold}%"
                    )
                    logging.info("Trailing stop mechanism activated!")

                # Update trailing price if conditions are met
                if price_change_from_trailing >= trailing_update_threshold:
                    old_trailing = trailing_price
                    trailing_price = current_price
                    logging.info(
                        f"\nPrice increased by {price_change_from_trailing:.2f}% from last trailing point."
                    )
                    logging.info(
                        f"Updating trailing point: {old_trailing:.4f} -> {trailing_price:.4f} USDT"
                    )
                    logging.info(f"Total profit from entry: {total_change_from_entry:.2f}%")

                # Check exit conditions only if trailing is activated
                elif trailing_activated and price_change_from_trailing <= trailing_drop_threshold:
                    logging.info(
                        f"\n🔴 Price dropped by {abs(price_change_from_trailing):.2f}% from trailing point."
                    )
                    logging.info(f"Final profit: {total_change_from_entry:.2f}% (≥ {minimum_profit_threshold}%)")
                    logging.info("Placing sell order...")

                    # Use the exact position_size that was calculated after buying
                    if position_size is None or position_size <= 0:
                        logging.error(f"No {current_coin} position available for selling")
                        # Reset position variables since we can't sell
                        current_coin = None
                        entry_price = None
                        trailing_price = None
                        position_size = None
                        trailing_activated = False
                        continue

                    # Determine decimal places for rounding
                    if current_coin in ["BTC", "ETH"]:
                        decimal_places = 6
                    elif current_coin in ["XRP", "ADA", "DOGE", "TRX"]:
                        decimal_places = 1
                    else:
                        decimal_places = 2

                    sell_quantity = helper.round_down(position_size, decimal_places)

                    logging.info(f"Position size to sell: {position_size:.8f} {current_coin}")
                    logging.info(f"Selling quantity: {sell_quantity} {current_coin}")

                    # Place sell order
                    r = safe_place_order(
                        helper,
                        category=category,
                        symbol=symbol,
                        side="Sell",
                        order_type="Market",
                        qty=sell_quantity,
                        market_unit="baseCoin",
                    )

                    if r.get("retCode") != 0:
                        error_msg = f"Error placing sell order: {r.get('retMsg')}"
                        logging.error(error_msg)
                        raise Exception(f"Order placement error: {r.get('retMsg')}")

                    order_id = r.get("result", {}).get("orderId")
                    logging.info(f"✅ Sell order placed successfully. ID: {order_id}")

                    logging.info(f"Closed position at price: {current_price:.4f} USDT")
                    logging.info(f"Final profit: {total_change_from_entry:.2f}%")

                    # Reset position variables and return to whitelist scanning
                    current_coin = None
                    entry_price = None
                    trailing_price = None
                    position_size = None
                    trailing_activated = False

                    logging.info("🔄 Returning to whitelist scanning mode...")

                elif not trailing_activated:
                    needed_profit = minimum_profit_threshold - total_change_from_entry
                    logging.info(f" (Need {needed_profit:.2f}% more for trailing activation)")
                else:
                    logging.info(" (Monitoring price)")

            # Reset error counter on successful execution
            consecutive_errors = 0

            # Use different intervals for different phases
            sleep_interval = 5 if current_coin else check_interval
            time.sleep(sleep_interval)

        except Exception as e:
            consecutive_errors += 1
            logging.error(f"\nError executing whitelist strategy: {str(e)}")

            if consecutive_errors >= max_consecutive_errors:
                logging.error(
                    f"Maximum consecutive errors reached ({max_consecutive_errors}). Restarting strategy..."
                )
                # Reset all position variables
                current_coin = None
                entry_price = None
                trailing_price = None
                position_size = None
                trailing_activated = False
                consecutive_errors = 0
                time.sleep(30)
                continue

            logging.warning(f"Continuing after error. Attempt {consecutive_errors}/{max_consecutive_errors}")
            time.sleep(check_interval * 2)
            continue
