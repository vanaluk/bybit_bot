# Bybit Trading Bot

A trading bot for the Bybit cryptocurrency exchange with support for various trading strategies.

## Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

1. Create a `.env` file in the project root directory
2. Add your Bybit API keys to it:
```
API_KEY=your_api_key
SECRET_KEY=your_secret_key
```

## Running the Bot

To start the bot, run:
```bash
python bot.py <buy_amount> <coin>
```

For example, to trade XRP with a buy amount of 100 USDT:
```bash
python bot.py 100 XRP
```

Parameters:
- `buy_amount`: Amount in USDT to buy
- `coin`: Cryptocurrency to trade (e.g., XRP, BTC, ETH)

## Current Features

Currently implemented Trailing Stop strategy that:
- Monitors price changes of selected cryptocurrency
- Enters position when price drops by specified percentage or shows rapid growth
- Uses trailing stop to secure profits
- Has configurable stop-loss and take-profit parameters
- Supports custom buy amount and cryptocurrency selection

## Logs

The bot creates log files for each trading session in the `logs` directory. Log files are named using the following format:
```
logs/bybit_bot_{coin}_{buy_amount}_{timestamp}.log
```

For example:
```
logs/bybit_bot_XRP_100_20231225_120000.log
```

These logs contain detailed information about:
- Trading decisions and executed orders
- Price movements and strategy triggers
- API interactions and responses
- Errors and warnings

## Development Plans

Future plans include:
- Adding new trading strategies
- Improving existing trailing stop strategy
- Adding support for multiple simultaneous strategies
- Expanding testing and trade analysis functionality
- Adding more configuration options for strategies
