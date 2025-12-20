"""
Trading strategies for Bybit bot

This module contains various trading strategies
that can be used with the Bybit API.
"""

import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional, Tuple

from ai_client import AIClient, AIError
from helpers import BybitHelper


def format_price(price: float | None) -> str:
    """
    Format price to show appropriate number of decimal places

    Args:
        price: price value to format

    Returns:
        formatted price string
    """
    if price is None or price == 0:
        return "0.0000"

    # For very small prices, show up to 12 decimal places
    if price < 0.0001:
        formatted = f"{price:.12f}".rstrip("0").rstrip(".")
        # Ensure at least 4 decimal places for consistency
        if "." in formatted and len(formatted.split(".")[1]) < 4:
            return f"{price:.4f}"
        return formatted
    else:
        return f"{price:.4f}"


def check_minimum_order_size(
    helper: BybitHelper, symbol: str, buy_amount: float
) -> bool:
    """
    Check if the order meets minimum size requirements

    Args:
        helper: BybitHelper instance
        symbol: trading symbol (e.g., "WENUSDT")
        buy_amount: amount in USDT to buy

    Returns:
        True if order size is valid, False otherwise
    """
    try:
        # Get instrument info to check minimum order requirements
        instruments_info = helper.get_instrument_info(category="spot", symbol=symbol)

        if instruments_info["retCode"] != 0:
            logging.error(
                f"Failed to get instrument info for {symbol}: {instruments_info['retMsg']}"
            )
            return False

        if not instruments_info["result"]["list"]:
            logging.error(f"No instrument info found for {symbol}")
            return False

        instrument = instruments_info["result"]["list"][0]
        min_order_amt = float(
            instrument.get("lotSizeFilter", {}).get("minOrderAmt", "0")
        )
        min_order_qty = float(
            instrument.get("lotSizeFilter", {}).get("minOrderQty", "0")
        )

        # Get current price to calculate minimum USDT required
        current_price = helper.get_price("spot", symbol)
        min_usdt_required = min_order_qty * current_price

        logging.info(f"Order validation for {symbol}:")
        logging.info(f"  Current price: {format_price(current_price)} USDT")
        logging.info(f"  Your order amount: {buy_amount} USDT")
        logging.info(f"  Minimum order amount: {min_order_amt} USDT")
        logging.info(f"  Minimum order quantity: {min_order_qty} coins")
        logging.info(
            f"  Minimum USDT required for min quantity: {min_usdt_required:.2f} USDT"
        )

        # Check minimum order amount (for quoteCoin orders)
        if min_order_amt > 0 and buy_amount < min_order_amt:
            logging.error(
                f"❌ Order amount {buy_amount} USDT is less than minimum required {min_order_amt} USDT"
            )
            return False

        # Check minimum USDT required for minimum quantity
        if min_usdt_required > buy_amount:
            logging.error(
                f"❌ Order amount {buy_amount} USDT is less than minimum required {min_usdt_required:.2f} USDT for minimum quantity"
            )
            return False

        logging.info("✅ Order size validation passed")
        return True

    except Exception as e:
        logging.error(f"Error checking minimum order size for {symbol}: {str(e)}")
        return False


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


def evaluate_entry(
    decision_mode: str,
    ai_client: Optional[AIClient],
    symbol: str,
    current_price: float,
    quick_price_change: float,
    price_change: float,
    quick_rise_threshold: float,
    price_drop_threshold: float,
) -> Tuple[bool, str]:
    """
    Evaluate entry conditions based on the mode.

    Logic for each mode:

    MODE "rules":
    - Checks if rules are triggered (price change thresholds)
    - AI is not used
    - Backward compatible with existing logic

    MODE "ai":
    - AI makes the decision independently of rules
    - On AI unavailability — fallback to rules
    - Requires ai_client != None

    MODE "combined":
    - Rules are checked first
    - If rules triggered — AI confirmation is requested
    - Buy only if AI confirms
    - On AI unavailability — fallback to rules

    Args:
        decision_mode: Decision mode ("rules", "ai", "combined")
        ai_client: AIClient instance (can be None for rules mode)
        symbol: Trading pair (e.g., "WIFUSDT")
        current_price: Current price in USDT
        quick_price_change: Price change over 1 hour (%)
        price_change: Price change over 3 hours (%)
        quick_rise_threshold: Quick rise threshold (e.g., 3.0)
        price_drop_threshold: Price drop threshold (e.g., -3.0)

    Returns:
        Tuple[bool, str]: (should_buy, decision_source)

        should_buy: True if should buy, False otherwise

        decision_source — string describing the decision source:
        - "rules" — decision made by rules (rules mode)
        - "rules_quick_rise" — quick rise triggered (rules mode)
        - "rules_price_drop" — price drop triggered (rules mode)
        - "ai" — decision made by AI (ai mode)
        - "rules+ai" — rules triggered + AI confirmed (combined mode)
        - "ai_veto" — rules triggered, but AI rejected (combined mode)
        - "rules (ai_unavailable)" — AI unavailable, fallback to rules
        - "hold" — no signal triggered
    """
    # Check if rules are triggered
    quick_rise_triggered = quick_price_change >= quick_rise_threshold
    price_drop_triggered = price_change <= price_drop_threshold
    rules_triggered = quick_rise_triggered or price_drop_triggered

    # Determine trigger reason for logging
    trigger_reason = ""
    if quick_rise_triggered:
        trigger_reason = (
            f"quick rise {quick_price_change:.2f}% >= {quick_rise_threshold}%"
        )
    elif price_drop_triggered:
        trigger_reason = f"price drop {price_change:.2f}% <= {price_drop_threshold}%"

    # ========== MODE: rules ==========
    if decision_mode == "rules":
        if rules_triggered:
            source = "rules_quick_rise" if quick_rise_triggered else "rules_price_drop"
            logging.info(f"[rules] Entry signal: {trigger_reason}")
            return True, source
        return False, "hold"

    # ========== MODE: ai ==========
    if decision_mode == "ai":
        if ai_client is None:
            logging.error(
                "AI client is None in 'ai' mode. "
                "This should not happen - check initialization."
            )
            # Fallback to rules as last resort
            if rules_triggered:
                logging.warning("Falling back to rules due to missing AI client")
                return True, "rules (ai_unavailable)"
            return False, "hold"

        try:
            # Call AI to make decision
            logging.debug(f"[ai] Requesting AI decision for {symbol} @ {current_price}")

            ai_decision = ai_client.should_buy(
                symbol=symbol,
                current_price=current_price,
                change_1h=quick_price_change,
                change_3h=price_change,
            )

            if ai_decision.should_buy:
                logging.info(
                    f"[ai] AI decided to BUY {symbol}: {ai_decision.reasoning}"
                )
                return True, "ai"
            else:
                logging.info(
                    f"[ai] AI decided to HOLD {symbol}: {ai_decision.reasoning}"
                )
                return False, "hold"

        except AIError as e:
            # AI error — fallback to rules
            logging.warning(f"[ai] AI unavailable, falling back to rules: {e}")
            if rules_triggered:
                logging.info(f"[ai] Rules triggered ({trigger_reason}), buying")
                return True, "rules (ai_unavailable)"
            return False, "hold"

    # ========== MODE: combined ==========
    if decision_mode == "combined":
        # Check rules first
        if not rules_triggered:
            # Rules not triggered — don't request AI
            return False, "hold"

        logging.info(f"[combined] Rules triggered: {trigger_reason}")

        # Rules triggered — request AI confirmation
        if ai_client is None:
            logging.warning("[combined] AI client is None, using rules only")
            return True, "rules (ai_unavailable)"

        try:
            logging.debug(
                f"[combined] Requesting AI confirmation for {symbol} @ {current_price}"
            )

            ai_decision = ai_client.should_buy(
                symbol=symbol,
                current_price=current_price,
                change_1h=quick_price_change,
                change_3h=price_change,
            )

            if ai_decision.should_buy:
                logging.info(
                    f"[combined] AI CONFIRMED buy signal: {ai_decision.reasoning}"
                )
                return True, "rules+ai"
            else:
                logging.info(
                    f"[combined] AI VETOED buy signal: {ai_decision.reasoning}"
                )
                return False, "ai_veto"

        except AIError as e:
            # On AI error in combined — fallback to rules
            logging.warning(f"[combined] AI unavailable, using rules: {e}")
            return True, "rules (ai_unavailable)"

    # Unknown mode — safe behavior
    logging.error(f"Unknown decision_mode: {decision_mode}, treating as 'rules'")
    if rules_triggered:
        return True, "rules"
    return False, "hold"


def log_entry_decision(
    symbol: str,
    should_buy: bool,
    decision_source: str,
    current_price: float,
    quick_price_change: float,
    price_change: float,
) -> None:
    """
    Log the entry decision result.

    Args:
        symbol: Trading pair
        should_buy: Decision result
        decision_source: Decision source
        current_price: Current price
        quick_price_change: Change over 1 hour
        price_change: Change over 3 hours
    """
    action = "BUY" if should_buy else "HOLD"
    emoji = "✅" if should_buy else "⏳"

    logging.info(
        f"{emoji} {symbol} Decision: {action} "
        f"(source: {decision_source}, "
        f"price: {format_price(current_price)}, "
        f"1h: {quick_price_change:+.2f}%, "
        f"3h: {price_change:+.2f}%)"
    )


def scan_coin_parallel(
    helper: BybitHelper, coin: str, category: str, hours_period: int, quick_period: int
):
    """
    Scan a single coin for price data (used for parallel execution)

    Args:
        helper: BybitHelper instance
        coin: coin name (e.g., "XRP")
        category: market category
        hours_period: period for long-term price change
        quick_period: period for quick price change

    Returns:
        dict: Coin data including price and changes, or None if error
    """
    symbol = f"{coin}USDT"
    try:
        current_price = helper.get_price(category, symbol)
        price_change = helper.get_price_change(category, symbol, hours=hours_period)
        quick_price_change = helper.get_price_change(
            category, symbol, hours=quick_period
        )

        return {
            "coin": coin,
            "symbol": symbol,
            "price": current_price,
            "price_change": price_change,
            "quick_change": quick_price_change,
            "success": True,
        }
    except Exception as e:
        return {"coin": coin, "symbol": symbol, "error": str(e), "success": False}


def run_trailing_stop_strategy(
    helper: BybitHelper,
    coin: str,
    buy_amount: float,
    check_interval: int = 5,
    decision_mode: str = "rules",
    ai_client: Optional[AIClient] = None,
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
        decision_mode: decision mode - "rules", "ai", or "combined" (default: "rules")
        ai_client: AIClient instance for AI modes (default: None)
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
    logging.info(f"Decision mode: {decision_mode}")
    if ai_client is not None:
        logging.info(f"AI client initialized: model={ai_client.model}")
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
                    f"[{current_time}] {symbol} Price: {format_price(current_price)} USDT "
                    f"(Change over {hours_period}h: {format_price(price_change)}%, "
                    f"over {quick_period}h: {format_price(quick_price_change)}%)"
                )

                # Evaluate entry conditions using unified function
                should_buy, decision_source = evaluate_entry(
                    decision_mode=decision_mode,
                    ai_client=ai_client,
                    symbol=symbol,
                    current_price=current_price,
                    quick_price_change=quick_price_change,
                    price_change=price_change,
                    quick_rise_threshold=quick_rise_threshold,
                    price_drop_threshold=price_drop_threshold,
                )

                if should_buy:
                    # Log the entry signal
                    log_entry_decision(
                        symbol=symbol,
                        should_buy=True,
                        decision_source=decision_source,
                        current_price=current_price,
                        quick_price_change=quick_price_change,
                        price_change=price_change,
                    )

                    # Check minimum order size before placing order
                    if not check_minimum_order_size(helper, symbol, buy_amount):
                        logging.error(
                            f"Cannot place order for {symbol} - minimum order requirements not met"
                        )
                        time.sleep(check_interval)
                        continue

                    logging.info("Placing buy order...")

                    # Get wallet balance before buying
                    balance_before = helper.get_wallet_balance(coin)
                    logging.info(
                        f"Balance before buying: {format_price(balance_before)} {coin}"
                    )

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
                    logging.info(f"Entry triggered by: {decision_source}")

                    # Get wallet balance after buying
                    balance_after = helper.get_wallet_balance(coin)
                    logging.info(
                        f"Balance after buying: {format_price(balance_after)} {coin}"
                    )

                    # Calculate exact amount bought
                    bought_amount = balance_after - balance_before
                    logging.info(
                        f"Exact amount bought: {format_price(bought_amount)} {coin}"
                    )

                    entry_price = current_price
                    trailing_price = current_price
                    position_size = (
                        bought_amount  # Use actual bought amount instead of calculation
                    )
                    trailing_activated = False  # Reset trailing activation
                    logging.info(
                        f"Entered position at price: {format_price(entry_price)} USDT"
                    )
                    logging.info(f"Position size: {format_price(position_size)} {coin}")

                else:
                    logging.info(f" (Waiting for signal, source: {decision_source})")
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
                            f"\n🟢 Minimum profit reached! Profit: {format_price(total_change_from_entry)}% >= {minimum_profit_threshold}%"
                        )
                        logging.info("Trailing stop mechanism activated!")
                    status_msg = f"(Waiting for {minimum_profit_threshold}% profit)"
                else:
                    status_msg = "(Trailing active)"

                logging.info(
                    f"[{current_time}] {symbol} Price: {format_price(current_price)} USDT "
                    f"(From entry: {format_price(total_change_from_entry)}%, "
                    f"From trailing: {format_price(price_change_from_trailing)}%, "
                    f"Change over {monitoring_period}h: {format_price(monitoring_price_change)}%)"
                    f"{status_msg}"
                )

                # Check if we can activate trailing stop
                if (
                    not trailing_activated
                    and total_change_from_entry >= minimum_profit_threshold
                ):
                    trailing_activated = True
                    logging.info(
                        f"\n🟢 Minimum profit reached! Profit: {format_price(total_change_from_entry)}% >= {minimum_profit_threshold}%"
                    )
                    logging.info("Trailing stop mechanism activated!")

                # Update trailing price if conditions are met
                if price_change_from_trailing >= trailing_update_threshold:
                    # Always update trailing if price rises above threshold
                    old_trailing = trailing_price
                    trailing_price = current_price
                    logging.info(
                        f"\nPrice increased by {format_price(price_change_from_trailing)}% from last trailing point."
                    )
                    logging.info(
                        f"Updating trailing point: {format_price(old_trailing)} -> {format_price(trailing_price)} USDT"
                    )
                    logging.info(
                        f"Total profit from entry: {format_price(total_change_from_entry)}%"
                    )

                # Check exit conditions only if trailing is activated
                elif (
                    trailing_activated
                    and price_change_from_trailing <= trailing_drop_threshold
                ):
                    # If price drops below threshold from maximum AND trailing is activated, sell
                    logging.info(
                        f"\n🔴 Price dropped by {abs(price_change_from_trailing):.2f}% from trailing point."
                    )
                    logging.info(
                        f"Final profit: {format_price(total_change_from_entry)}% (≥ {minimum_profit_threshold}%)"
                    )
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

                    # Get the correct decimal places from API
                    try:
                        decimal_places = helper.get_base_precision(category, symbol)
                        logging.info(
                            f"Base precision for {symbol}: {decimal_places} decimals"
                        )
                    except Exception as e:
                        logging.warning(
                            f"Failed to get base precision: {str(e)}. Using default 2 decimals"
                        )
                        decimal_places = 2

                    sell_quantity = helper.round_down(position_size, decimal_places)

                    logging.info(
                        f"Position size to sell: {format_price(position_size)} {coin}"
                    )
                    logging.info(
                        f"Selling quantity: {format_price(sell_quantity)} {coin} (rounded to {decimal_places} decimals)"
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

                    logging.info(
                        f"Closed position at price: {format_price(current_price)} USDT"
                    )
                    logging.info(
                        f"Final profit: {format_price(total_change_from_entry)}%"
                    )
                    entry_price = None
                    trailing_price = None
                    position_size = None
                    trailing_activated = False
                elif not trailing_activated:
                    logging.info(
                        f" (Need {minimum_profit_threshold - total_change_from_entry:.2f}% more for trailing activation)"
                    )
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


def evaluate_whitelist_candidates(
    candidates: list,
    decision_mode: str,
    ai_client: Optional[AIClient],
    quick_rise_threshold: float,
    price_drop_threshold: float,
) -> Optional[dict]:
    """
    Evaluate whitelist candidates and select the best one.

    Logic for each mode:

    MODE "rules":
    - Returns candidate with highest score
    - AI is not used

    MODE "ai":
    - For each candidate with rules signal, calls AI
    - Returns first one for which AI said "buy"
    - If AI unavailable — fallback to rules

    MODE "combined":
    - Selects best by rules (highest score)
    - Requests AI confirmation
    - If AI confirmed — returns candidate
    - If AI rejected — returns None
    - If AI unavailable — returns candidate (fallback)

    Args:
        candidates: List of candidates with price data
        decision_mode: Decision mode
        ai_client: AI client
        quick_rise_threshold: Quick rise threshold
        price_drop_threshold: Price drop threshold

    Returns:
        Best candidate or None
    """
    if not candidates:
        return None

    # Filter candidates where rules triggered
    valid_candidates = []
    for c in candidates:
        quick_change = c.get("quick_change", 0)
        long_change = c.get("long_change", 0)

        # Check rules conditions
        if quick_change >= quick_rise_threshold or long_change <= price_drop_threshold:
            # Calculate score
            score = max(abs(quick_change), abs(long_change))
            c["score"] = score
            c["trigger"] = (
                "quick_rise" if quick_change >= quick_rise_threshold else "price_drop"
            )
            valid_candidates.append(c)

    if not valid_candidates:
        return None

    # Sort by score (best first)
    valid_candidates.sort(key=lambda x: x["score"], reverse=True)

    # ========== MODE: rules ==========
    if decision_mode == "rules":
        best = valid_candidates[0]
        logging.info(f"[rules] Selected {best['symbol']} (score: {best['score']:.2f})")
        best["decision_source"] = "rules"
        return best

    # ========== MODE: ai ==========
    if decision_mode == "ai":
        if ai_client is None:
            logging.warning("[ai] No AI client, falling back to rules")
            best = valid_candidates[0]
            best["decision_source"] = "rules (ai_unavailable)"
            return best

        # Try each candidate
        for candidate in valid_candidates:
            try:
                logging.debug(f"[ai] Checking {candidate['symbol']} with AI")

                ai_decision = ai_client.should_buy(
                    symbol=candidate["symbol"],
                    current_price=candidate["price"],
                    change_1h=candidate["quick_change"],
                    change_3h=candidate["long_change"],
                )

                if ai_decision.should_buy:
                    logging.info(
                        f"[ai] AI approved {candidate['symbol']}: {ai_decision.reasoning}"
                    )
                    candidate["decision_source"] = "ai"
                    return candidate
                else:
                    logging.info(
                        f"[ai] AI rejected {candidate['symbol']}: {ai_decision.reasoning}"
                    )

            except AIError as e:
                logging.warning(f"[ai] AI error for {candidate['symbol']}: {e}")
                continue

        # If AI rejected all — fallback to best by rules
        logging.warning("[ai] AI rejected all candidates, falling back to rules")
        best = valid_candidates[0]
        best["decision_source"] = "rules (ai_unavailable)"
        return best

    # ========== MODE: combined ==========
    if decision_mode == "combined":
        best = valid_candidates[0]

        if ai_client is None:
            logging.warning("[combined] No AI client, using rules only")
            best["decision_source"] = "rules (ai_unavailable)"
            return best

        try:
            logging.debug(f"[combined] Requesting AI confirmation for {best['symbol']}")

            ai_decision = ai_client.should_buy(
                symbol=best["symbol"],
                current_price=best["price"],
                change_1h=best["quick_change"],
                change_3h=best["long_change"],
            )

            if ai_decision.should_buy:
                logging.info(
                    f"[combined] AI confirmed {best['symbol']}: {ai_decision.reasoning}"
                )
                best["decision_source"] = "rules+ai"
                return best
            else:
                logging.info(
                    f"[combined] AI vetoed {best['symbol']}: {ai_decision.reasoning}"
                )
                return None  # AI rejected — don't buy

        except AIError as e:
            logging.warning(f"[combined] AI unavailable, using rules: {e}")
            best["decision_source"] = "rules (ai_unavailable)"
            return best

    # Unknown mode
    logging.error(f"Unknown decision_mode: {decision_mode}")
    best = valid_candidates[0] if valid_candidates else None
    if best:
        best["decision_source"] = "rules"
    return best


def run_trailing_stop_strategy_whitelist(
    helper: BybitHelper,
    coin_whitelist: list,
    buy_amount: float,
    check_interval: int = 5,
    decision_mode: str = "rules",
    ai_client: Optional[AIClient] = None,
):
    """
    Trading strategy with trailing stop for whitelist of coins.

    Algorithm workflow:

    1. Whitelist Scanning Phase:
    - Monitors ALL coins from whitelist simultaneously using parallel execution
    - Checks entry conditions for each coin:
      * Option 1: Price drop of 3% over 3 hours
      * Option 2: Quick rise of 3% over 1 hour
    - As soon as ANY coin meets entry conditions - buys it and switches to single-coin mode
    - Uses ThreadPoolExecutor for fast parallel scanning (up to 10 coins at once)

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
        check_interval: price check interval in seconds (default: 5 for faster scanning)
        decision_mode: decision mode - "rules", "ai", or "combined" (default: "rules")
        ai_client: AIClient instance for AI modes (default: None)
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
    logging.info(f"Decision mode: {decision_mode}")
    if ai_client is not None:
        logging.info(f"AI client initialized: model={ai_client.model}")
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

                # Scan all coins in parallel for faster execution
                with ThreadPoolExecutor(
                    max_workers=min(len(coin_whitelist), 10)
                ) as executor:
                    # Submit all scanning tasks
                    future_to_coin = {
                        executor.submit(
                            scan_coin_parallel,
                            helper,
                            coin,
                            category,
                            hours_period,
                            quick_period,
                        ): coin
                        for coin in coin_whitelist
                    }

                    # Collect all results first to ensure complete scan
                    all_results = []
                    for future in as_completed(future_to_coin):
                        result = future.result()
                        all_results.append(result)

                    # Collect candidates from all results
                    candidates = []
                    for result in all_results:
                        if not result["success"]:
                            logging.warning(
                                f"  Error checking {result['symbol']}: {result.get('error', 'Unknown error')}"
                            )
                            continue

                        candidates.append(
                            {
                                "coin": result["coin"],
                                "symbol": result["symbol"],
                                "price": result["price"],
                                "quick_change": result["quick_change"],
                                "long_change": result["price_change"],
                            }
                        )

                        # Log coin data
                        logging.info(
                            f"  {result['symbol']}: {format_price(result['price'])} USDT "
                            f"({hours_period}h: {format_price(result['price_change'])}%, "
                            f"{quick_period}h: {format_price(result['quick_change'])}%)"
                        )

                # Evaluate and select best candidate using unified function
                best_opportunity = evaluate_whitelist_candidates(
                    candidates=candidates,
                    decision_mode=decision_mode,
                    ai_client=ai_client,
                    quick_rise_threshold=quick_rise_threshold,
                    price_drop_threshold=price_drop_threshold,
                )

                # If we found an opportunity, execute it
                if best_opportunity:
                    coin = best_opportunity["coin"]
                    symbol = best_opportunity["symbol"]
                    current_price = best_opportunity["price"]
                    decision_source = best_opportunity.get("decision_source", "rules")

                    logging.info("\n🎯 ENTRY SIGNAL FOUND!")
                    logging.info(f"Selected coin: {symbol}")
                    logging.info(f"Decision source: {decision_source}")
                    logging.info(f"Price: {format_price(current_price)} USDT")
                    logging.info("Checking order requirements...")

                    # Check minimum order size before placing order
                    if not check_minimum_order_size(helper, symbol, buy_amount):
                        logging.error(
                            f"Cannot place order for {symbol} - minimum order requirements not met"
                        )
                        logging.info("Continuing whitelist scan...")
                        continue

                    logging.info("Placing buy order...")

                    # Get wallet balance before buying
                    balance_before = helper.get_wallet_balance(coin)
                    logging.info(
                        f"Balance before buying: {format_price(balance_before)} {coin}"
                    )

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
                    logging.info(f"Entry triggered by: {decision_source}")

                    # Get wallet balance after buying
                    balance_after = helper.get_wallet_balance(coin)
                    logging.info(
                        f"Balance after buying: {format_price(balance_after)} {coin}"
                    )

                    # Calculate exact amount bought
                    bought_amount = balance_after - balance_before
                    logging.info(
                        f"Exact amount bought: {format_price(bought_amount)} {coin}"
                    )

                    # Set position variables
                    current_coin = coin
                    entry_price = current_price
                    trailing_price = current_price
                    position_size = bought_amount
                    trailing_activated = False

                    logging.info(f"🔄 Switched to single-coin mode: {symbol}")
                    logging.info(f"Entry price: {format_price(entry_price)} USDT")
                    logging.info(f"Position size: {format_price(position_size)} {coin}")

                else:
                    logging.info("  ⏳ No entry signals found. Continuing scan...")

            else:
                # SINGLE-COIN MANAGEMENT PHASE
                symbol = f"{current_coin}USDT"

                # Get current price and changes
                current_price = safe_get_price(helper, category, symbol)
                monitoring_price_change = safe_get_price_change(
                    helper, category, symbol, hours=monitoring_period
                )

                # Calculate position metrics
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

                # Determine status
                if not trailing_activated:
                    if total_change_from_entry >= minimum_profit_threshold:
                        trailing_activated = True
                        logging.info(
                            f"\n🟢 Minimum profit reached! Profit: {format_price(total_change_from_entry)}% >= {minimum_profit_threshold}%"
                        )
                        logging.info("Trailing stop mechanism activated!")
                    status_msg = f"(Waiting for {minimum_profit_threshold}% profit)"
                else:
                    status_msg = "(Trailing active)"

                logging.info(
                    f"[{current_time}] {symbol} Price: {format_price(current_price)} USDT "
                    f"(From entry: {format_price(total_change_from_entry)}%, "
                    f"From trailing: {format_price(price_change_from_trailing)}%, "
                    f"Change over {monitoring_period}h: {format_price(monitoring_price_change)}%)"
                    f"{status_msg}"
                )

                # Check if we can activate trailing stop
                if (
                    not trailing_activated
                    and total_change_from_entry >= minimum_profit_threshold
                ):
                    trailing_activated = True
                    logging.info(
                        f"\n🟢 Minimum profit reached! Profit: {format_price(total_change_from_entry)}% >= {minimum_profit_threshold}%"
                    )
                    logging.info("Trailing stop mechanism activated!")

                # Update trailing price if conditions are met
                if price_change_from_trailing >= trailing_update_threshold:
                    old_trailing = trailing_price
                    trailing_price = current_price
                    logging.info(
                        f"\nPrice increased by {format_price(price_change_from_trailing)}% from last trailing point."
                    )
                    logging.info(
                        f"Updating trailing point: {format_price(old_trailing)} -> {format_price(trailing_price)} USDT"
                    )
                    logging.info(
                        f"Total profit from entry: {format_price(total_change_from_entry)}%"
                    )

                # Check exit conditions only if trailing is activated
                elif (
                    trailing_activated
                    and price_change_from_trailing <= trailing_drop_threshold
                ):
                    logging.info(
                        f"\n🔴 Price dropped by {abs(price_change_from_trailing):.2f}% from trailing point."
                    )
                    logging.info(
                        f"Final profit: {format_price(total_change_from_entry)}% (≥ {minimum_profit_threshold}%)"
                    )
                    logging.info("Placing sell order...")

                    # Use the exact position_size that was calculated after buying
                    if position_size is None or position_size <= 0:
                        logging.error(
                            f"No {current_coin} position available for selling"
                        )
                        # Reset position variables since we can't sell
                        current_coin = None
                        entry_price = None
                        trailing_price = None
                        position_size = None
                        trailing_activated = False
                        continue

                    # Get the correct decimal places from API
                    try:
                        decimal_places = helper.get_base_precision(category, symbol)
                        logging.info(
                            f"Base precision for {symbol}: {decimal_places} decimals"
                        )
                    except Exception as e:
                        logging.warning(
                            f"Failed to get base precision: {str(e)}. Using default 2 decimals"
                        )
                        decimal_places = 2

                    sell_quantity = helper.round_down(position_size, decimal_places)

                    logging.info(
                        f"Position size to sell: {format_price(position_size)} {current_coin}"
                    )
                    logging.info(
                        f"Selling quantity: {format_price(sell_quantity)} {current_coin} (rounded to {decimal_places} decimals)"
                    )

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

                    logging.info(
                        f"Closed position at price: {format_price(current_price)} USDT"
                    )
                    logging.info(
                        f"Final profit: {format_price(total_change_from_entry)}%"
                    )

                    # Reset position variables and return to whitelist scanning
                    current_coin = None
                    entry_price = None
                    trailing_price = None
                    position_size = None
                    trailing_activated = False

                    logging.info("🔄 Returning to whitelist scanning mode...")

                elif not trailing_activated:
                    needed_profit = minimum_profit_threshold - total_change_from_entry
                    logging.info(
                        f" (Need {needed_profit:.2f}% more for trailing activation)"
                    )
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

            logging.warning(
                f"Continuing after error. Attempt {consecutive_errors}/{max_consecutive_errors}"
            )
            time.sleep(check_interval * 2)
            continue
