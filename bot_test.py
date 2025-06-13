"""
Test runner for Bybit API functionality

This module runs tests by importing functions from tests.py
"""

import os
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


def main():
    """
    Main test function
    """
    # Set up logging
    setup_logger("TEST", 0)
    
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
        test_connection(helper)
        
        # Uncomment to test order placement (be careful!)
        test_place_order(helper)
    else:
        logging.warning("API keys not found - skipping authenticated tests")


if __name__ == "__main__":
    main()
