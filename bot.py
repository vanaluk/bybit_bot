"""
Bybit Trading Bot Utility

This module provides utilities for interacting
with the Bybit trading platform.
Includes functionality for:
- Getting account asset information
- Getting and logging fund transfers
- Handling API requests and authentication

Script uses environment variables for API key and secret.
Requires pybit and python-dotenv libraries for API interaction and environment management.

Supports two modes:
1. Single-coin mode: python bot.py <buy_amount> <coin>
2. Whitelist mode: python bot.py <buy_amount>
"""

import os
import sys
import logging
from dotenv import load_dotenv
from pybit import exceptions
from pybit.unified_trading import HTTP
from helpers import BybitHelper
from tests import test_connection
from strategies import run_trailing_stop_strategy, run_trailing_stop_strategy_whitelist
from logger import setup_logger

load_dotenv()

API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
WHITELIST_FILE = "whitelist.txt"


def print_usage():
    """Prints script usage information"""
    print("Usage:")
    print("  Single-coin mode: python bot.py <buy_amount> <coin>")
    print("  Whitelist mode:   python bot.py <buy_amount>")
    print()
    print("Examples:")
    print("  python bot.py 100 WIF     # Trade only WIF")
    print("  python bot.py 100         # Trade coins from whitelist.txt")
    print()
    print("For whitelist mode, create a 'whitelist.txt' file with comma-separated coin names:")
    print("  XRP,ETH,BTC,ADA,DOGE")
    sys.exit(1)


def load_whitelist():
    """
    Load coin whitelist from file.

    Returns:
        list: List of coin names from whitelist file

    Raises:
        FileNotFoundError: If whitelist.txt doesn't exist
        ValueError: If whitelist file is empty or invalid
    """
    if not os.path.exists(WHITELIST_FILE):
        raise FileNotFoundError(
            f"Whitelist file '{WHITELIST_FILE}' not found. "
            f"Create it with comma-separated coin names (e.g., 'XRP,ETH,BTC')"
        )

    with open(WHITELIST_FILE, 'r', encoding='utf-8') as f:
        content = f.read().strip()

    if not content:
        raise ValueError(f"Whitelist file '{WHITELIST_FILE}' is empty")

    # Parse coins and clean them up
    coins = [coin.strip().upper() for coin in content.split(',')]
    coins = [coin for coin in coins if coin and coin.isalpha()]  # Remove empty strings and invalid symbols

    if not coins:
        # More detailed error message based on content
        if ',' in content:
            raise ValueError(
                f"No valid coins found in '{WHITELIST_FILE}'. "
                f"File contains only empty values, spaces, or invalid symbols. "
                f"Example of valid format: 'XRP,ETH,BTC'"
            )
        else:
            raise ValueError(
                f"No valid coins found in '{WHITELIST_FILE}'. "
                f"File should contain comma-separated coin names. "
                f"Example: 'XRP,ETH,BTC'"
            )

    return coins


def main():
    """
    Main function for executing Bybit trading bot operations.

    This function supports two modes:
    1. Single-coin mode: Trades one specific coin
    2. Whitelist mode: Scans multiple coins from whitelist and trades the best opportunity

    Command line arguments:
    - Single-coin: python bot.py <buy_amount> <coin>
    - Whitelist: python bot.py <buy_amount>

    Exceptions:
        exceptions.InvalidRequestError: If there's an error in API request
        exceptions.FailedRequestError: If API request fails
    """
    # Check command line arguments
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print_usage()

    try:
        buy_amount = float(sys.argv[1])
        if buy_amount <= 0:
            raise ValueError("buy_amount must be positive")
    except ValueError as e:
        if "could not convert" in str(e):
            print("Error: buy_amount must be a number")
        else:
            print(f"Error: {str(e)}")
        print_usage()

    # Determine mode based on number of arguments
    if len(sys.argv) == 3:
        # Single-coin mode
        coin = sys.argv[2].upper()
        mode = "single"
        logging_identifier = coin
    else:
        # Whitelist mode
        try:
            coin_whitelist = load_whitelist()
            mode = "whitelist"
            logging_identifier = "WHITELIST"
            print(f"Loaded whitelist: {', '.join(coin_whitelist)}")
        except (FileNotFoundError, ValueError) as e:
            print(f"Error loading whitelist: {str(e)}")
            sys.exit(1)

    # Set up logging
    setup_logger(logging_identifier, buy_amount)

    try:
        if not API_KEY or not SECRET_KEY:
            raise ValueError("API_KEY or SECRET_KEY not found in environment variables")

        client = HTTP(
            api_key=API_KEY,
            api_secret=SECRET_KEY,
            recv_window=60000,
            return_response_headers=True,
        )

        helper = BybitHelper(client)

        if mode == "single":
            # Single-coin mode
            logging.info(f"Starting single-coin mode for {coin}")

            # Test connection and display information
            test_connection(helper, coin)

            # Start trading algorithm for single coin
            run_trailing_stop_strategy(helper, coin, buy_amount)

        else:
            # Whitelist mode
            logging.info(f"Starting whitelist mode with {len(coin_whitelist)} coins: {', '.join(coin_whitelist)}")

            # Test connection with first coin from whitelist
            test_connection(helper, coin_whitelist[0])

            # Start trading algorithm for whitelist
            run_trailing_stop_strategy_whitelist(helper, coin_whitelist, buy_amount)

    except exceptions.InvalidRequestError as e:
        logging.error(f"ByBit request error | {e.status_code} | {e.message}")
    except exceptions.FailedRequestError as e:
        logging.error(f"Execution error | {e.status_code} | {e.message}")
    except Exception as e:
        logging.error(f"Execution error | {str(e)}")


if __name__ == "__main__":
    main()
