# Bybit Trading Bot

A trading bot for the Bybit cryptocurrency exchange with support for various trading strategies.

## Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

1. Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

2. Edit `.env` and add your Bybit API keys:
```
API_KEY=your_api_key
SECRET_KEY=your_secret_key
```

For AI integration, also add your Anthropic API key (see AI Integration section below).

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

### Examples with Decision Modes

**Rules mode (default)** — uses only price-based rules:
```bash
# Single-coin
python bot.py 100 WIF

# Whitelist
python bot.py 100
```

**AI mode** — AI makes all entry decisions:
```bash
# Single-coin with AI
python bot.py 100 WIF --mode ai

# Whitelist with AI
python bot.py 100 --mode ai
```

**Combined mode** — rules trigger first, then AI confirms:
```bash
# Single-coin with AI confirmation
python bot.py 100 WIF --mode combined

# Whitelist with AI confirmation
python bot.py 100 --mode combined
```

### Parameters
- `buy_amount`: Amount in USDT to buy
- `coin`: Cryptocurrency to trade (e.g., XRP, BTC, ETH) - only for single-coin mode
- `--mode`: Decision mode - `rules` (default), `ai`, or `combined` (see AI Integration section)

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

## AI Integration

The bot supports AI-powered trading decisions using Anthropic Claude.

### Decision Modes

| Mode | Description |
|------|-------------|
| `rules` | Original rule-based logic (price thresholds). Default mode. |
| `ai` | AI makes all entry decisions. Falls back to rules on error. |
| `combined` | Rules must trigger first, then AI confirms/vetoes the signal. |

### Setup

1. Get an API key from [Anthropic Console](https://console.anthropic.com/)

2. Add to your `.env` file:
   ```env
   ANTHROPIC_API_KEY=sk-ant-your-key-here
   DECISION_MODE=combined  # or 'ai' or 'rules'
   ```

3. Run with desired mode:
   ```bash
   # Use mode from .env
   python bot.py 100 WIF

   # Override with command line
   python bot.py 100 WIF --mode ai
   python bot.py 100 --whitelist --mode combined
   ```

### Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | - | Required for ai/combined modes |
| `DECISION_MODE` | `rules` | Default decision mode |
| `AI_MODEL` | `claude-sonnet-4-20250514` | Anthropic model to use |
| `AI_TIMEOUT` | `30` | Request timeout in seconds |
| `AI_CHECK_INTERVAL` | `60` | Minimum seconds between AI calls |
| `AI_MAX_RETRIES` | `3` | Max retry attempts on error |

### How It Works

#### AI Mode
```
Price data → AI analyzes → Buy/Hold decision
                ↓ (on error)
           Falls back to rules
```

#### Combined Mode
```
Price data → Rules check → No signal → Hold
                ↓
           Signal triggered → AI confirmation → Buy/Hold
                                    ↓ (on error)
                               Falls back to rules
```

### Cost Considerations

- Each AI call uses approximately 200-400 tokens
- Caching prevents redundant calls when price changes < 0.5%
- Minimum interval between calls is configurable (default: 60s)
- Combined mode only calls AI when rules trigger (most cost-efficient)

### Monitoring

Check logs for AI activity:
```
INFO - AI decision for WIFUSDT: buy (reasoning: Strong momentum...)
INFO - Using cached AI decision for WIFUSDT: hold
WARNING - Rate limited by Anthropic API, waiting 30.0s
```

### Troubleshooting

| Issue | Solution |
|-------|----------|
| "ANTHROPIC_API_KEY not found" | Add key to .env file |
| "Rate limited" | Increase AI_CHECK_INTERVAL |
| "Failed after X attempts" | Check network, increase AI_MAX_RETRIES |
| AI always says "hold" | Review AI prompt, check market conditions |

## Project Structure

```
bybit_bot/
├── bot.py              # Entry point, argument parsing
├── helpers.py          # Bybit API wrapper
├── strategies.py       # Trading strategies
├── ai_client.py        # AI client for Anthropic API
├── ai_config.py        # AI configuration and prompts
├── logger.py           # Logging configuration
├── tests.py            # Unit tests
├── whitelist.txt       # Coin whitelist
├── requirements.txt    # Python dependencies
├── .env                # Configuration (not in git)
├── .env.example        # Configuration template
└── logs/               # Log files
```

## Development Plans

Future plans include:
- Adding new trading strategies
- Improving existing trailing stop strategy
- Adding support for multiple simultaneous strategies
- Expanding testing and trade analysis functionality
- Adding more configuration options for strategies
