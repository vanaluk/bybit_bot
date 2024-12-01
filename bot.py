"""
Bybit Trading Bot Utility Script

This module provides utility functions for interacting
with the Bybit cryptocurrency trading platform.
It includes functionality for:
- Retrieving account assets
- Fetching and logging fund transfers
- Handling API requests and authentication

The script uses environment variables for API key and secret authentication.
Requires pybit library and python-dotenv for API interactions and environment management.
"""

import os

import pandas as pd
from dotenv import load_dotenv
from pybit import exceptions
from pybit.unified_trading import HTTP
from helpers import assets, get_transfers, log_limits

pd.set_option("display.max_rows", 500)
pd.set_option("display.max_columns", 500)
pd.set_option("display.width", 1000)

load_dotenv()
API_KEY = os.getenv("BB_API_KEY")
SECRET_KEY = os.getenv("BB_SECRET_KEY")


def main():
    """
    Main function to execute Bybit trading bot operations.

    This function:
    1. Initializes a Bybit HTTP client with API credentials
    2. Retrieves account assets
    3. Fetches and logs fund transfers
    4. Handles potential API request errors

    Raises:
        exceptions.InvalidRequestError: If there's an invalid API request
        exceptions.FailedRequestError: If the API request fails
    """
    cl = HTTP(
        api_key=API_KEY,
        api_secret=SECRET_KEY,
        recv_window=60000,
        return_response_headers=True,
    )

    try:
        if not API_KEY or not SECRET_KEY:
            raise ValueError("API_KEY or SECRET_KEY not found in environment variables")

        assets(cl)
        get_transfers(cl)
    except exceptions.InvalidRequestError as e:
        print("ByBit Request Error", e.status_code, e.message, sep=" | ")
    except exceptions.FailedRequestError as e:
        print("ByBit Request Failed", e.status_code, e.message, sep=" | ")
    except exceptions.UnauthorizedExceptionError as e:
        print("ByBit Authorization Error", str(e), sep=" | ")
    except exceptions.InvalidChannelTypeError as e:
        print("ByBit Channel Error", str(e), sep=" | ")
    except exceptions.TopicMismatchError as e:
        print("ByBit Topic Error", str(e), sep=" | ")
    except (KeyError, ValueError, TypeError) as e:
        print("Data Processing Error", str(e), sep=" | ")
    except (ConnectionError, TimeoutError) as e:
        print("Network Error", str(e), sep=" | ")
    except (OSError, IOError) as e:
        print("File Operation Error", str(e), sep=" | ")
    except RuntimeError as e:
        print("Runtime Error", str(e), sep=" | ")
    except AttributeError as e:
        print("API Response Error", str(e), sep=" | ")
    # trunk-ignore(pylint/W0718)
    except Exception as e:
        print("Unknown Error", str(e), sep=" | ")


if __name__ == "__main__":
    main()
