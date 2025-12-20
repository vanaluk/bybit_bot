"""
AI Configuration Module

Contains constants, prompts, and validation functions
for AI integration in the trading bot.
"""

import os
from typing import Optional

# === Default constants ===
DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_TIMEOUT = 30  # seconds
DEFAULT_CHECK_INTERVAL = 60  # seconds
DEFAULT_MAX_RETRIES = 3
PRICE_CHANGE_THRESHOLD = 0.5  # % for caching

# === Valid modes ===
VALID_MODES = ["rules", "ai", "combined"]

# === System prompt for AI ===
SYSTEM_PROMPT = """You are a cryptocurrency trading assistant. Your task is to analyze price data and decide whether to buy a cryptocurrency.

You will receive:
- Symbol: the cryptocurrency trading pair (e.g., BTCUSDT)
- Current price in USDT
- Price change over the last 1 hour (percentage)
- Price change over the last 3 hours (percentage)

Based on this data, you must decide:
- "buy" - if conditions are favorable for entering a position
- "hold" - if you recommend waiting

Consider these factors:
1. A drop of 3% or more over 3 hours may indicate a buying opportunity (potential rebound)
2. A quick rise of 3% or more over 1 hour may indicate momentum worth following
3. High volatility (large swings in short periods) may suggest waiting for stabilization

Respond ONLY with a valid JSON object in this exact format:
{
  "decision": "buy" or "hold",
  "reasoning": "Brief explanation of your decision in 1-2 sentences"
}

Do not include any other text outside the JSON object."""

# === User prompt template ===
USER_PROMPT_TEMPLATE = """Analyze this cryptocurrency data and decide whether to buy:

Symbol: {symbol}
Current price: {current_price} USDT
Price change (1 hour): {change_1h:+.2f}%
Price change (3 hours): {change_3h:+.2f}%

Provide your decision in JSON format."""


def get_ai_config() -> dict:
    """
    Read AI configuration from environment variables.
    
    Returns:
        dict: AI configuration with fields:
            - api_key: str | None
            - model: str
            - timeout: int
            - check_interval: int
            - max_retries: int
    """
    return {
        "api_key": os.getenv("ANTHROPIC_API_KEY"),
        "model": os.getenv("AI_MODEL", DEFAULT_MODEL),
        "timeout": int(os.getenv("AI_TIMEOUT", str(DEFAULT_TIMEOUT))),
        "check_interval": int(os.getenv("AI_CHECK_INTERVAL", str(DEFAULT_CHECK_INTERVAL))),
        "max_retries": int(os.getenv("AI_MAX_RETRIES", str(DEFAULT_MAX_RETRIES))),
    }


def validate_ai_config(mode: str) -> Optional[str]:
    """
    Validate AI configuration for the given mode.
    
    Args:
        mode: Operating mode ("rules", "ai", "combined")
        
    Returns:
        None if configuration is valid, otherwise error message string
    """
    if mode not in VALID_MODES:
        return f"Invalid mode: '{mode}'. Valid modes: {', '.join(VALID_MODES)}"
    
    # AI is not required for rules mode
    if mode == "rules":
        return None
    
    # API key is required for ai and combined modes
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return f"ANTHROPIC_API_KEY not found in .env. Required for mode: {mode}"
    
    # Optional key format validation
    if not api_key.startswith("sk-ant-"):
        # Warning only, not an error
        import logging
        logging.warning(
            "ANTHROPIC_API_KEY doesn't match expected format (sk-ant-...). "
            "Verify the key is correct."
        )
    
    return None


def format_user_prompt(symbol: str, current_price: float, 
                       change_1h: float, change_3h: float) -> str:
    """
    Format user prompt with data.
    
    Args:
        symbol: Trading pair (e.g., "WIFUSDT")
        current_price: Current price in USDT
        change_1h: Price change over 1 hour (%)
        change_3h: Price change over 3 hours (%)
        
    Returns:
        Formatted prompt
    """
    return USER_PROMPT_TEMPLATE.format(
        symbol=symbol,
        current_price=current_price,
        change_1h=change_1h,
        change_3h=change_3h
    )
