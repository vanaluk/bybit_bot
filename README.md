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

### Whitelist Configuration (Optional)

For whitelist mode, create a `whitelist.txt` file in the project root directory with comma-separated cryptocurrency names:

```
XRP,WEN,POPCAT,SOL,DOGE,LINK,DOT,MEW,SOLO,LADYS,PEPE,TOKEN,PENDLE,FLOKI,TON,INJ,MEME,FLOW
```

The bot will scan all coins in the whitelist and select the best trading opportunity based on the configured strategy.

## Running the Bot

The bot supports two modes of operation:

### Single-coin mode
To trade a specific cryptocurrency:
```bash
python bot.py <buy_amount> <coin>
```

For example, to trade XRP with a buy amount of 100 USDT:
```bash
python bot.py 100 XRP
```

### Whitelist mode
To scan multiple cryptocurrencies from a whitelist and trade the best opportunity:
```bash
python bot.py <buy_amount>
```

For example, to trade with 100 USDT using the whitelist:
```bash
python bot.py 100
```

For whitelist mode, you need to configure the `whitelist.txt` file (see configuration section below).

Parameters:
- `buy_amount`: Amount in USDT to buy
- `coin`: Cryptocurrency to trade (e.g., XRP, BTC, ETH) - only for single-coin mode

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

## Testing

The bot includes comprehensive testing functionality to verify API connectivity and trading operations.

### Running Tests

To run tests and verify your API configuration:

```bash
python bot_test.py [coin]
```

Examples:
```bash
python bot_test.py          # Test with XRP (default)
python bot_test.py BTC      # Test with Bitcoin
python bot_test.py ETH      # Test with Ethereum
```

### Test Functions

The testing suite includes:

1. **Connection Test** (`test_connection`):
   - Verifies API authentication
   - Displays account balance information
   - Shows current price for specified cryptocurrency
   - Tests basic API functionality

2. **Order Placement Test** (`test_place_order`):
   - Tests buy order placement (market order)
   - Tests sell order placement
   - Verifies order execution and balance updates
   - **Warning**: This test places real orders with real money!

### Test Output

Tests generate detailed logs showing:
- API connection status
- Account balance information
- Current cryptocurrency prices
- Order placement results (if enabled)
- Any errors or warnings

Test logs are saved with the prefix `TEST_` in the filename for easy identification.

### Important Notes

- Tests require valid API keys in your `.env` file
- The `test_place_order` function is commented out by default for safety
- Only enable order testing if you understand it will use real funds
- Test with small amounts first

## Development Plans

Future plans include:
- Adding new trading strategies
- Improving existing trailing stop strategy
- Adding support for multiple simultaneous strategies
- Expanding testing and trade analysis functionality
- Adding more configuration options for strategies
