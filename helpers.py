"""
Helper functions for trading on Bybit

This module contains helper functions for interacting with the Bybit API,
including functions for getting account information, logging transfers,
and monitoring API limits.
"""

import pandas as pd
from pandas import DataFrame
from pybit.unified_trading import HTTP
import time


class BybitHelper:
    """
    Helper class for working with Bybit API
    """

    def __init__(self, client: HTTP | None = None):
        """
        Initialize helper

        Args:
            client (HTTP, optional): Bybit HTTP client. Defaults to None
        """
        self.client = client

    @staticmethod
    def log_limits(headers: dict):
        """
        Log API request limits.

        Args:
            headers (dict): API response headers containing limit information
        """
        # print(
        #     f"Limits {headers.get('X-Bapi-Limit-Status')} / {headers.get('X-Bapi-Limit')}"
        # )
        pass

    def assets(self):
        """
        Get balances for UNIFIED trading account.

        Note: This method shows balances only for UNIFIED account and does not
        show full wallet balances. Copy trading, funding, and inverse
        account details are not included.

        Returns:
            dict: Account asset information
        """
        if not self.client:
            raise ValueError("HTTP client not initialized")

        response = self.client.get_wallet_balance(accountType="UNIFIED")
        
        # Handle different response formats from the API
        if isinstance(response, tuple):
            if len(response) == 3:
                r, _, h = response
            elif len(response) == 2:
                r, _ = response
                h = None
            else:
                r = response[0]
                h = None
        else:
            r = response
            h = None

        r = r.get("result", {}).get("list", [])[0]

        total_balance = float(r.get("totalWalletBalance", "0.0"))
        coins = [
            f"{float(c.get('walletBalance', '0.0')):>12.6f} {c.get('coin'):>12}"
            for c in r.get("coin", [])
        ]

        print("\n".join(coins))
        print(f"---\nTotal: {total_balance:>18.2f}\n")

        # self.log_limits(h)

    def get_transfers(self):
        """
        Get and log fund transfer records for the account.

        This function retrieves transfer transactions without pagination.
        Creates a DataFrame with transfer information and sorts
        transactions by timestamp in descending order.

        Returns:
            pandas.DataFrame: DataFrame containing transfer transaction details
        """
        if not self.client:
            raise ValueError("HTTP client not initialized")

        response = self.client.get_transaction_log()
        
        # Handle different response formats from the API
        if isinstance(response, tuple):
            if len(response) == 3:
                r, _, h = response
            elif len(response) == 2:
                r, _ = response
                h = None
            else:
                r = response[0]
                h = None
        else:
            r = response
            h = None

        df = DataFrame(
            [
                {
                    "currency": e.get("currency"),
                    "type": e.get("type"),
                    "change": e.get("change"),
                    "cashBalance": e.get("cashBalance"),
                    "transactionTime": int(e.get("transactionTime")),
                }
                for e in r.get("result", {}).get("list", [])
                if e.get("type").startswith("TRANSFER")
            ]
        )

        df["transactionTime"] = pd.to_datetime(df["transactionTime"], unit="ms")
        df.sort_values(by=["transactionTime"], inplace=True, ascending=False)
        print(df)

        # self.log_limits(h)

    def get_assets(self, coin: str) -> float:
        """
        Get available balance for a specific coin on the account

        Args:
            coin (str): Coin name (e.g. "BTC", "ETH", "USDT")

        Returns:
            float: Available balance for withdrawal

        Raises:
            ValueError: If client is not initialized or coin name is empty
            RuntimeError: If API response has unexpected format
        """
        if not self.client:
            raise ValueError("HTTP client not initialized")
        if not coin:
            raise ValueError("Coin name not specified")

        try:
            # API может возвращать разные форматы ответа
            api_result = self.client.get_wallet_balance(accountType="UNIFIED")
            
            # Обработка различных форматов ответа API
            if isinstance(api_result, tuple):
                if len(api_result) == 3:
                    response, _, headers = api_result
                elif len(api_result) == 2:
                    response, _ = api_result
                    headers = None
                else:
                    response = api_result[0]
                    headers = None
            else:
                response = api_result
                headers = None
                
            if not response:
                raise RuntimeError("Empty response from API")

            # Get list of coins from response
            account_data = response.get("result", {}).get("list", [])
            if not account_data:
                return 0.0

            # Get coin information
            coins_data = account_data[0].get("coin", [])
            if not coins_data:
                return 0.0

            # Create a dictionary with coin balances
            balances = {
                asset.get("coin"): float(asset.get("availableToWithdraw", "0.0"))
                for asset in coins_data
                if asset.get("coin")  # Check if coin name exists
            }

            # Log API limits
            # self.log_limits(headers)

            # Return balance for requested coin or 0.0 if coin not found
            return self.round_down(balances.get(coin, 0.0), 3)

        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unexpected API response format: {str(e)}")
        except ValueError as e:
            raise RuntimeError(f"Value conversion error: {str(e)}")

    def place_order(
        self,
        category: str,
        symbol: str,
        side: str,
        order_type: str,
        qty: float,
        market_unit: str = "quoteCoin",
    ) -> dict:
        """
        Place an order

        Args:
            category (str): Market category (e.g. "linear", "spot")
            symbol (str): Trading pair symbol (e.g. "BTCUSDT")
            side (str): Order side ("Buy" or "Sell")
            order_type (str): Order type (e.g. "Market", "Limit")
            qty (float): Order quantity
            market_unit (str, optional): Unit for market orders. Defaults to "quoteCoin"

        Returns:
            dict: Order placement result

        Raises:
            ValueError: If client is not initialized or order parameters are invalid
            RuntimeError: If order placement fails
        """
        if not self.client:
            raise ValueError("HTTP client not initialized")
        if not all([category, symbol, side, order_type]):
            raise ValueError("Order parameters not specified")
        if qty <= 0:
            raise ValueError("Quantity must be greater than 0")
        if side not in ["Buy", "Sell"]:
            raise ValueError('Invalid order side. Use "Buy" or "Sell"')

        try:
            # Get minimum order quantity
            api_result = self.client.get_instruments_info(
                category=category, symbol=symbol
            )
            
            # Handle different response formats from the API
            if isinstance(api_result, tuple):
                if len(api_result) == 3:
                    instrument_info, _, _ = api_result
                elif len(api_result) == 2:
                    instrument_info, _ = api_result
                else:
                    instrument_info = api_result[0]
            else:
                instrument_info = api_result
            lot_size_filter = (
                instrument_info.get("result", {})
                .get("list", [])[0]
                .get("lotSizeFilter", {})
            )
            min_order_qty = float(lot_size_filter.get("minOrderQty", "0.0"))

            # Check minimum order quantity
            if qty < min_order_qty:
                raise ValueError(
                    f"Quantity {qty} is less than minimum allowed {min_order_qty}"
                )

            api_result = self.client.place_order(
                category=category,
                symbol=symbol,
                side=side,
                orderType=order_type,
                qty=qty,
                marketUnit=market_unit,
            )
            
            # Handle different response formats from the API
            if isinstance(api_result, tuple):
                if len(api_result) == 3:
                    response, _, headers = api_result
                elif len(api_result) == 2:
                    response, _ = api_result
                    headers = None
                else:
                    response = api_result[0]
                    headers = None
            else:
                response = api_result
                headers = None

            # self.log_limits(headers)
            return response

        except Exception as e:
            raise RuntimeError(f"Order placement failed: {str(e)}")

    def get_instrument_info(self, category: str, symbol: str) -> dict:
        """
        Get instrument information

        Args:
            category (str): Market category (e.g. "spot", "linear")
            symbol (str): Trading pair symbol (e.g. "BTCUSDT")

        Returns:
            dict: Instrument information

        Raises:
            ValueError: If client is not initialized
            RuntimeError: If instrument information retrieval fails
        """
        if not self.client:
            raise ValueError("HTTP client not initialized")

        try:
            api_result = self.client.get_instruments_info(
                category=category,
                symbol=symbol
            )
            
            # Handle different response formats from the API
            if isinstance(api_result, tuple):
                if len(api_result) == 3:
                    response, _, headers = api_result
                elif len(api_result) == 2:
                    response, _ = api_result
                    headers = None
                else:
                    response = api_result[0]
                    headers = None
            else:
                response = api_result
                headers = None
            # self.log_limits(headers)
            return response
        except Exception as e:
            raise RuntimeError(f"Instrument information retrieval failed: {str(e)}")

    def get_price(self, category: str, symbol: str) -> float:
        """
        Get current price for a symbol

        Args:
            category: Market category (spot, linear, inverse)
            symbol: Trading pair symbol (e.g. BTCUSDT)

        Returns:
            float: Current price
        """
        if not self.client:
            raise ValueError("HTTP client not initialized")

        api_result = self.client.get_tickers(category=category, symbol=symbol)
        
        # Handle different response formats from the API
        if isinstance(api_result, tuple):
            if len(api_result) == 3:
                r, _, h = api_result
            elif len(api_result) == 2:
                r, _ = api_result
                h = None
            else:
                r = api_result[0]
                h = None
        else:
            r = api_result
            h = None
        # self.log_limits(h)

        return float(r.get("result", {}).get("list", [{}])[0].get("lastPrice", "0"))

    def get_price_change(self, category: str, symbol: str, hours: int = 1) -> float:
        """
        Get price change percentage over specified period

        Args:
            category: Market category (spot, linear, inverse)
            symbol: Trading pair symbol (e.g. BTCUSDT)
            hours: Number of hours to calculate change over

        Returns:
            float: Price change percentage
        """
        if not self.client:
            raise ValueError("HTTP client not initialized")

        # Get current price
        current_price = self.get_price(category, symbol)

        # Get klines data
        interval = "60"  # 1 hour intervals
        limit = hours  # Number of candles to get
        api_result = self.client.get_kline(
            category=category,
            symbol=symbol,
            interval=interval,
            limit=limit,
        )
        
        # Handle different response formats from the API
        if isinstance(api_result, tuple):
            if len(api_result) == 3:
                r, _, h = api_result
            elif len(api_result) == 2:
                r, _ = api_result
                h = None
            else:
                r = api_result[0]
                h = None
        else:
            r = api_result
            h = None
        # self.log_limits(h)

        # Get price from hours ago
        old_price = float(r.get("result", {}).get("list", [[0]])[0][1])  # Open price

        # Calculate percentage change
        if old_price == 0:
            return 0
        return ((current_price - old_price) / old_price) * 100

    def round_down(self, value: float, decimals: int) -> float:
        """
        Remove excess from float

        Args:
            value (float): Number to process
            decimals (int): Number of decimal places

        Returns:
            float: Processed number
        """
        multiplier = 10**decimals
        return float(int(value * multiplier)) / multiplier
