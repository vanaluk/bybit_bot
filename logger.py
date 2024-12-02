"""
Bot operations logging module

Provides functionality for logging both to console
and to file with timestamps.
"""

import logging
import os
from datetime import datetime


def setup_logger(coin: str, buy_amount: float):
    """
    Sets up logger for writing to file and console output

    Args:
        coin: Cryptocurrency name
        buy_amount: Amount to buy
    """
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Form log filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"logs/bot_{coin}_{buy_amount}_{timestamp}.log"

    # Configure logging format
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Create file handler
    file_handler = logging.FileHandler(log_filename)
    file_handler.setFormatter(formatter)

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Log startup
    logging.info(f"Starting bot for {coin} with buy amount {buy_amount} USDT")
    logging.info(f"Log file: {log_filename}")

    return logger
