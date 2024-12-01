"""
Bybit Trading Helper Functions

This module contains utility functions for interacting with the Bybit API,
including functions for retrieving account information, logging transfers,
and monitoring API limits.
"""

import pandas as pd
from pandas import DataFrame
from pybit.unified_trading import HTTP


def log_limits(headers: dict):
    """
    Log API request limits.

    Args:
        headers (dict): API response headers containing limit information
    """
    print(
        f"Limits  {headers.get('X-Bapi-Limit-Status')} / {headers.get('X-Bapi-Limit')}"
    )


def assets(cl: HTTP):
    """
    Retrieve account balances for the UNIFIED trading account.

    Note: This method shows balances for the UNIFIED account and does not
    display full wallet balances. Copy trading, funding, and inverse
    account details are not included.

    Args:
        cl (HTTP): Bybit HTTP client with authentication credentials

    Returns:
        dict: Account assets information
    """
    r, _, h = cl.get_wallet_balance(accountType="UNIFIED")
    r = r.get("result", {}).get("list", [])[0]

    total_balance = float(r.get("totalWalletBalance", "0.0"))
    coins = [
        f"{float(c.get('walletBalance', '0.0')):>12.6f} {c.get('coin'):>12}"
        for c in r.get("coin", [])
    ]

    print("\n".join(coins))
    print(f"---\nTotal: {total_balance:>18.2f}\n")

    log_limits(h)


def get_transfers(cl: HTTP):
    """
    Retrieve and log fund transfer records for the account.

    This function fetches transfer transactions without pagination.
    It creates a DataFrame with transfer-related information and sorts
    the transactions by timestamp in descending order.

    Args:
        cl (HTTP): Bybit HTTP client with authentication credentials

    Returns:
        pandas.DataFrame: A DataFrame containing transfer transaction details
    """
    r, _, h = cl.get_transaction_log()

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

    log_limits(h)