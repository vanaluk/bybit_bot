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
import argparse
from dotenv import load_dotenv
from pybit import exceptions
from pybit.unified_trading import HTTP
from helpers import BybitHelper
from tests import test_connection
from strategies import run_trailing_stop_strategy, run_trailing_stop_strategy_whitelist
from logger import setup_logger
from ai_config import validate_ai_config
from ai_client import AIClient

load_dotenv()

API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
WHITELIST_FILE = "whitelist.txt"


def create_argument_parser() -> argparse.ArgumentParser:
    """
    Create command line argument parser.
    Integrates new --mode parameter with existing positional arguments.
    """
    parser = argparse.ArgumentParser(
        description="Bybit Trading Bot with AI integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python bot.py 100 WIF                    # Single-coin, rules mode (default)
  python bot.py 100 WIF --mode ai          # Single-coin, AI mode
  python bot.py 100 WIF --mode combined    # Single-coin, combined mode
  python bot.py 100                        # Whitelist, rules mode
  python bot.py 100 --mode ai              # Whitelist with AI

Environment:
  DECISION_MODE       Default mode (overridden by --mode)
  ANTHROPIC_API_KEY   API key for ai/combined modes
        """
    )
    parser.add_argument(
        "buy_amount",
        type=float,
        help="Purchase amount in USDT"
    )
    parser.add_argument(
        "coin",
        nargs="?",
        default=None,
        help="Coin (e.g., WIF). Not specified in whitelist mode"
    )
    parser.add_argument(
        "--mode",
        choices=["rules", "ai", "combined"],
        default=None,
        help="Decision mode: rules (default), ai, combined"
    )
    return parser


def get_decision_mode(args: argparse.Namespace) -> str:
    """
    Determine decision mode with priority:
    CLI (--mode) > .env (DECISION_MODE) > default ("rules")

    Args:
        args: Parsed command line arguments

    Returns:
        Mode string: "rules", "ai" or "combined"
    """
    valid_modes = ["rules", "ai", "combined"]

    # 1. CLI parameter priority
    if args.mode is not None:
        logging.info(f"Decision mode: {args.mode} (from CLI)")
        return args.mode  # Already validated by argparse

    # 2. Check .env
    env_mode = os.getenv("DECISION_MODE", "").strip().lower()
    if env_mode:
        if env_mode not in valid_modes:
            logging.error(
                f"Invalid DECISION_MODE in .env: '{env_mode}'. "
                f"Valid values: {', '.join(valid_modes)}"
            )
            sys.exit(1)
        logging.info(f"Decision mode: {env_mode} (from .env)")
        return env_mode

    # 3. Default value
    logging.info("Decision mode: rules (default)")
    return "rules"


def init_ai_client(mode: str) -> 'AIClient | None':
    """
    Initialize AI client if required for the mode.

    Args:
        mode: Operating mode

    Returns:
        AIClient or None for rules mode
    """
    if mode == "rules":
        return None

    # Configuration validation
    error = validate_ai_config(mode)
    if error:
        logging.error(error)
        sys.exit(1)

    # Get configuration
    from ai_config import get_ai_config
    config = get_ai_config()

    # Create client
    try:
        client = AIClient(
            api_key=config["api_key"],
            model=config["model"],
            timeout=config["timeout"],
            max_retries=config["max_retries"],
            check_interval=config["check_interval"]
        )
        return client
    except Exception as e:
        logging.error(f"Failed to initialize AI client: {e}")
        sys.exit(1)


def print_usage():
    """Prints script usage information"""
    print("Usage:")
    print("  Single-coin mode: python bot.py <buy_amount> <coin> [--mode MODE]")
    print("  Whitelist mode:   python bot.py <buy_amount> [--mode MODE]")
    print()
    print("Arguments:")
    print("  buy_amount          Purchase amount in USDT")
    print("  coin                Coin (e.g., WIF)")
    print()
    print("Options:")
    print("  --mode              Decision mode:")
    print("                        rules    - rules only (default)")
    print("                        ai       - AI only")
    print("                        combined - rules + AI confirmation")
    print()
    print("Examples:")
    print("  python bot.py 100 WIF              # Trade WIF, rules mode")
    print("  python bot.py 100 WIF --mode ai    # Trade WIF, AI mode")
    print("  python bot.py 100 --mode combined  # Whitelist, combined mode")
    print()
    print("Environment:")
    print("  DECISION_MODE       Default mode (overridden by --mode)")
    print("  ANTHROPIC_API_KEY   API key for ai/combined modes")
    print()
    print("For whitelist mode, create 'whitelist.txt' with comma-separated coin names:")
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
    """
    load_dotenv()

    # Parse arguments with argparse
    parser = create_argument_parser()

    # Check minimum number of arguments
    if len(sys.argv) < 2:
        parser.print_help()
        sys.exit(1)

    try:
        args = parser.parse_args()
    except SystemExit:
        sys.exit(1)

    # Validate buy_amount
    if args.buy_amount <= 0:
        print("Error: buy_amount must be positive")
        sys.exit(1)

    buy_amount = args.buy_amount

    # Determine mode (CLI > .env > default)
    decision_mode = get_decision_mode(args)

    # Initialize AI client if needed
    ai_client = init_ai_client(decision_mode)

    # Determine operating mode (single-coin or whitelist)
    if args.coin is not None:
        # Single-coin mode
        coin = args.coin.upper()
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
            logging.info(f"Decision mode: {decision_mode}")

            # Test connection and display information
            test_connection(helper, coin)

            # Start trading algorithm for single coin
            run_trailing_stop_strategy(
                helper, coin, buy_amount,
                decision_mode=decision_mode,
                ai_client=ai_client
            )

        else:
            # Whitelist mode
            logging.info(f"Starting whitelist mode with {len(coin_whitelist)} coins: {', '.join(coin_whitelist)}")
            logging.info(f"Decision mode: {decision_mode}")

            # Test connection with first coin from whitelist
            test_connection(helper, coin_whitelist[0])

            # Start trading algorithm for whitelist
            run_trailing_stop_strategy_whitelist(
                helper, coin_whitelist, buy_amount,
                decision_mode=decision_mode,
                ai_client=ai_client
            )

    except exceptions.InvalidRequestError as e:
        logging.error(f"ByBit request error | {e.status_code} | {e.message}")
    except exceptions.FailedRequestError as e:
        logging.error(f"Execution error | {e.status_code} | {e.message}")
    except Exception as e:
        logging.error(f"Execution error | {str(e)}")


if __name__ == "__main__":
    main()
