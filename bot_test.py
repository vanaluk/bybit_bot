"""
Test runner for Bybit API functionality

This module runs tests by importing functions from tests.py
"""

import os
import sys
import logging
from dotenv import load_dotenv
from pybit.unified_trading import HTTP
from helpers import BybitHelper
from logger import setup_logger
from tests import test_connection, test_place_order

load_dotenv()

API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")


def test_orderbook():
    """
    Test getting orderbook data without authentication
    """
    cl = HTTP()
    r = cl.get_orderbook(category="spot", symbol="BTCUSDT")
    print("Orderbook test:")
    print(r)
    print("----------------")


def print_usage():
    """Prints script usage information"""
    print("Usage: python bot_test.py [coin]")
    print("Example: python bot_test.py XRP")
    print("If no coin is specified, XRP will be used as default")


def main():
    """
    Main test function
    """
    # Parse command line arguments
    coin = "XRP"  # Default coin
    if len(sys.argv) > 1:
        coin = sys.argv[1].upper()
        logging.info(f"Using coin: {coin}")
    
    # Set up logging
    setup_logger(f"TEST_{coin}", 0)
    
    # Test orderbook without auth
    test_orderbook()
    
    # Test with authentication if keys are available
    if API_KEY and SECRET_KEY:
        client = HTTP(
            api_key=API_KEY,
            api_secret=SECRET_KEY,
            recv_window=60000,
            return_response_headers=True,
        )
        
        helper = BybitHelper(client)
        
        # Test connection and basic operations
        test_connection(helper, coin)
        
        # Uncomment to test order placement (be careful!)
        # If you want to test order placement, uncomment the following line
        # test_place_order(helper, coin)  # Make sure test_place_order is updated to handle the coin parameter
    else:
        logging.warning("API keys not found - skipping authenticated tests")


if __name__ == "__main__":
    main()
