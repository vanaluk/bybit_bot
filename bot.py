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
"""

import os
import sys
import logging
from dotenv import load_dotenv
from pybit import exceptions
from pybit.unified_trading import HTTP
from helpers import BybitHelper
from tests import test_connection
from strategies import run_trailing_stop_strategy
from logger import setup_logger

load_dotenv()

API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")


def print_usage():
    """Prints script usage information"""
    print("Usage: python bot.py <buy_amount> <coin>")
    print("Example: python bot.py 100 XRP")
    sys.exit(1)


def main():
    """
    Main function for executing Bybit trading bot operations.

    This function:
    1. Initializes Bybit HTTP client with API credentials
    2. Gets account asset information
    3. Gets and logs fund transfers
    4. Handles possible API request errors

    Exceptions:
        exceptions.InvalidRequestError: If there's an error in API request
        exceptions.FailedRequestError: If API request fails
    """
    # Check command line arguments
    if len(sys.argv) != 3:
        print_usage()

    try:
        buy_amount = float(sys.argv[1])
        coin = sys.argv[2].upper()
    except ValueError:
        print("Error: buy_amount must be a number")
        print_usage()

    # Set up logging
    setup_logger(coin, buy_amount)

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

        # Test connection and display information
        test_connection(helper, coin)

        # Start trading algorithm
        run_trailing_stop_strategy(helper, coin, buy_amount)

    except exceptions.InvalidRequestError as e:
        logging.error(f"ByBit request error | {e.status_code} | {e.message}")
    except exceptions.FailedRequestError as e:
        logging.error(f"Execution error | {e.status_code} | {e.message}")
    except Exception as e:
        logging.error(f"Execution error | {str(e)}")


if __name__ == "__main__":
    main()
