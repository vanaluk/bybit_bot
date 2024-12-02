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
    avbl = helper.get_assets("XRP")
    logging.info(str(avbl))
    logging.info("----------------")

    logging.info("3. Get price (XRPUSDT)")
    r = helper.get_instrument_info(category="spot", symbol="XRPUSDT")
    logging.info(str(r))
    logging.info("----------------")


def test_place_order(helper: BybitHelper):
    """
    Test order placement
    
    Args:
        helper: BybitHelper instance
    """
    # Place order
    qty = 10  # amount in XRP
    logging.info(f"4. Place order XRP - {qty} XRP (XRPUSDT)")
    r = helper.place_order(
        category="spot",
        symbol="XRPUSDT",
        side="Sell",
        order_type="Market",
        qty=qty,
        market_unit="baseCoin",
    )
    logging.info(str(r))
    logging.info("----------------")
