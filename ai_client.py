"""
AI Client Module

Provides integration with Anthropic Claude API
for making trading decisions.
"""

import json
import logging
import time
from dataclasses import dataclass
from typing import Optional

import anthropic

from ai_config import (
    DEFAULT_CHECK_INTERVAL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT,
    PRICE_CHANGE_THRESHOLD,
    SYSTEM_PROMPT,
    format_user_prompt,
)


class AIError(Exception):
    """Exception for AI errors"""

    pass


@dataclass
class AIDecision:
    """AI decision result about buying"""

    decision: str  # "buy" or "hold"
    reasoning: str  # decision reasoning
    raw_response: Optional[str] = None  # raw response for debugging

    @property
    def should_buy(self) -> bool:
        """Convert decision to bool"""
        return self.decision.lower() == "buy"


@dataclass
class AIClientState:
    """
    Internal state of the AI client.
    Used for caching and rate limiting.
    """

    last_call_time: float = 0.0  # time of last successful call
    last_price: float = 0.0  # price at last call
    last_symbol: str = ""  # symbol at last call
    consecutive_errors: int = 0  # consecutive errors counter
    current_interval: int = 60  # current interval between calls


class AIClient:
    """
    Client for interacting with Anthropic Claude API.

    Attributes:
        api_key: Anthropic API key
        model: Claude model to use
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts
        check_interval: Interval between AI calls in seconds
        state: Internal client state
    """

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        check_interval: int = DEFAULT_CHECK_INTERVAL,
    ):
        """
        Initialize the AI client.

        Args:
            api_key: Anthropic API key
            model: Claude model (default claude-sonnet-4-20250514)
            timeout: Request timeout in seconds (default 30)
            max_retries: Maximum retry attempts (default 3)
            check_interval: Interval between calls in seconds (default 60)

        Raises:
            AIError: On client initialization error
        """
        if not api_key:
            raise AIError("API key is required")

        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.default_interval = check_interval

        # Parameters for exponential backoff
        self.base_delay = 2.0  # Base delay in seconds
        self.max_delay = 60.0  # Maximum delay in seconds

        # Price change threshold for caching
        self.price_change_threshold = PRICE_CHANGE_THRESHOLD

        # Internal state
        self.state = AIClientState(current_interval=check_interval)

        # Cached last decision
        self._last_decision: Optional[AIDecision] = None

        # Initialize Anthropic client
        try:
            self.client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
            logging.info(f"AIClient initialized (model: {model}, timeout: {timeout}s)")
        except Exception as e:
            raise AIError(f"Failed to initialize Anthropic client: {e}") from e

    def should_buy(
        self,
        symbol: str,
        current_price: float,
        change_1h: float,
        change_3h: float,
        force: bool = False,
    ) -> AIDecision:
        """
        Make a buying decision with caching and retry logic.

        Args:
            symbol: Trading pair (e.g., "WIFUSDT")
            current_price: Current price in USDT
            change_1h: Price change over 1 hour (%)
            change_3h: Price change over 3 hours (%)
            force: Force AI call (ignores cache)

        Returns:
            AIDecision with decision and reasoning

        Raises:
            AIError: When all attempts are exhausted
        """
        # Check if AI call is needed
        if not force and not self.is_call_needed(symbol, current_price):
            cached = self.get_cached_decision()
            if cached is not None:
                logging.info(
                    f"Using cached AI decision for {symbol}: {cached.decision}"
                )
                return cached
            # If no cache, still call AI
            logging.debug("No cached decision, proceeding with AI call")

        user_prompt = format_user_prompt(symbol, current_price, change_1h, change_3h)

        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                logging.debug(
                    f"AI request attempt {attempt + 1}/{self.max_retries} "
                    f"for {symbol} @ {current_price}"
                )

                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=256,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_prompt}],
                )

                content_block = response.content[0]
                if not hasattr(content_block, "text"):
                    raise AIError(
                        f"Unexpected response block type: {type(content_block).__name__}"
                    )
                raw_response: str = content_block.text  # type: ignore[union-attr]
                logging.debug(f"AI raw response: {raw_response[:200]}")

                # Parse the response
                decision = self._parse_response(raw_response)

                # Successful call — update state with caching
                self._update_state(symbol, current_price, decision)

                logging.info(
                    f"AI decision for {symbol}: {decision.decision} "
                    f"(reasoning: {decision.reasoning[:100]}...)"
                )

                return decision

            except anthropic.RateLimitError as e:
                # HTTP 429 — rate limit
                last_error = e
                self.state.consecutive_errors += 1

                # Check for critical error count
                if self.state.consecutive_errors > 10:
                    logging.critical(
                        f"Critical: {self.state.consecutive_errors} consecutive errors detected. "
                        f"AI service may be unavailable."
                    )

                # Extract retry_after from response (if available)
                retry_after = self._extract_retry_after(e)
                wait_time = self._handle_rate_limit(retry_after)

                if attempt < self.max_retries - 1:
                    logging.warning(
                        f"Rate limit hit, retrying in {wait_time:.1f}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    time.sleep(wait_time)

            except anthropic.APIStatusError as e:
                # Other API errors (500, 503, etc.)
                last_error = e
                self.state.consecutive_errors += 1

                # Check for critical error count
                if self.state.consecutive_errors > 10:
                    logging.critical(
                        f"Critical: {self.state.consecutive_errors} consecutive errors detected. "
                        f"AI service may be unavailable."
                    )

                wait_time = self._calculate_backoff_delay(attempt)

                logging.error(
                    f"Anthropic API error: {e.status_code} - {e.message} "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )

                if attempt < self.max_retries - 1:
                    logging.info(f"Retrying in {wait_time:.1f}s")
                    time.sleep(wait_time)

            except anthropic.APIConnectionError as e:
                # Connection errors (network unavailable, etc.)
                last_error = e
                self.state.consecutive_errors += 1

                # Check for critical error count
                if self.state.consecutive_errors > 10:
                    logging.critical(
                        f"Critical: {self.state.consecutive_errors} consecutive errors detected. "
                        f"AI service may be unavailable."
                    )

                wait_time = self._calculate_backoff_delay(attempt)

                logging.error(
                    f"Anthropic API connection error: {e} "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )

                if attempt < self.max_retries - 1:
                    logging.info(f"Retrying in {wait_time:.1f}s")
                    time.sleep(wait_time)

            except AIError:
                # Parsing errors — raise immediately, retry won't help
                raise

            except Exception as e:
                # Unexpected errors
                last_error = e
                self.state.consecutive_errors += 1

                # Check for critical error count
                if self.state.consecutive_errors > 10:
                    logging.critical(
                        f"Critical: {self.state.consecutive_errors} consecutive errors detected. "
                        f"AI service may be unavailable."
                    )

                wait_time = self._calculate_backoff_delay(attempt)

                logging.error(
                    f"Unexpected error calling AI: {type(e).__name__}: {e} "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )

                if attempt < self.max_retries - 1:
                    logging.info(f"Retrying in {wait_time:.1f}s")
                    time.sleep(wait_time)

        # All retries exhausted
        error_message = f"Failed to get AI decision after {self.max_retries} attempts"
        if last_error:
            error_message += f": {type(last_error).__name__}: {last_error}"

        logging.critical(error_message)
        raise AIError(error_message)

    def is_call_needed(self, symbol: str, current_price: float) -> bool:
        """
        Check if AI call is needed or cached result can be used.

        Caching logic:
        1. First call (no history) — always call AI
        2. Symbol changed — always call AI (reset cache)
        3. Less than current_interval seconds passed — don't call
        4. Price change < PRICE_CHANGE_THRESHOLD from last call — don't call

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            current_price: Current price in USDT

        Returns:
            True if AI call is needed, False if can be skipped
        """
        now = time.time()

        # 1. First call — always request AI
        if self.state.last_call_time == 0.0:
            logging.debug(f"AI call needed: first call for {symbol}")
            return True

        # 2. Symbol changed — reset cache and request
        if self.state.last_symbol != symbol:
            logging.debug(
                f"AI call needed: symbol changed from {self.state.last_symbol} to {symbol}"
            )
            return True

        # 3. Check time interval
        time_since_last_call = now - self.state.last_call_time
        if time_since_last_call < self.state.current_interval:
            remaining = self.state.current_interval - time_since_last_call
            logging.debug(
                f"AI call skipped: too soon, {remaining:.1f}s remaining "
                f"(interval: {self.state.current_interval}s)"
            )
            return False

        # 4. Check price change
        if self.state.last_price > 0:
            price_change_pct = abs(
                (current_price - self.state.last_price) / self.state.last_price * 100
            )
            if price_change_pct < self.price_change_threshold:
                logging.debug(
                    f"AI call skipped: price change too small ({price_change_pct:.3f}% < {self.price_change_threshold}%)"
                )
                return False
            else:
                logging.debug(
                    f"AI call needed: significant price change ({price_change_pct:.3f}% >= {self.price_change_threshold}%)"
                )

        logging.debug(
            "AI call needed: interval elapsed and price changed significantly"
        )
        return True

    def _extract_json_from_response(self, raw_response: str) -> str:
        """
        Extract JSON from AI response, removing markdown formatting.

        AI sometimes wraps JSON in markdown code blocks.
        This method cleans the response from such formatting.

        Args:
            raw_response: Raw response from AI

        Returns:
            Cleaned JSON string
        """
        import re

        cleaned = raw_response.strip()

        # Pattern for markdown code block: ```json ... ``` or ``` ... ```
        patterns = [
            r"^```json\s*\n?(.*?)\n?\s*```$",  # ```json ... ```
            r"^```\s*\n?(.*?)\n?\s*```$",  # ``` ... ```
        ]

        for pattern in patterns:
            match = re.match(pattern, cleaned, re.DOTALL)
            if match:
                return match.group(1).strip()

        return cleaned

    def _parse_response(self, raw_response: str) -> AIDecision:
        """
        Parse AI response with validation.

        Handles:
        - Invalid JSON
        - Missing required decision field
        - Unexpected decision values
        - Missing reasoning field (optional)

        Args:
            raw_response: Raw text response from AI

        Returns:
            AIDecision with parsed data

        Raises:
            AIError: On invalid JSON or missing required fields
        """
        # Extract JSON from response
        cleaned_response = self._extract_json_from_response(raw_response)

        # Parse JSON
        try:
            data = json.loads(cleaned_response)
        except json.JSONDecodeError as e:
            logging.error(f"AI returned invalid JSON: {raw_response[:200]}")
            raise AIError(f"Invalid JSON from AI: {e}") from e

        # Verify it's a dictionary
        if not isinstance(data, dict):
            logging.error(f"AI response is not a JSON object: {type(data)}")
            raise AIError(
                f"AI response must be a JSON object, got: {type(data).__name__}"
            )

        # Check required decision field
        if "decision" not in data:
            logging.error(f"AI response missing 'decision' field: {data}")
            raise AIError("Missing 'decision' field in AI response")

        # Extract and normalize decision
        raw_decision = data.get("decision")
        if not isinstance(raw_decision, str):
            logging.error(f"'decision' field is not a string: {type(raw_decision)}")
            raise AIError(
                f"'decision' must be a string, got: {type(raw_decision).__name__}"
            )

        decision = raw_decision.lower().strip()

        # Validate decision value
        valid_decisions = ["buy", "hold"]
        if decision not in valid_decisions:
            logging.warning(
                f"AI returned unexpected decision '{raw_decision}', treating as 'hold'"
            )
            decision = "hold"

        # Extract reasoning (optional)
        reasoning = data.get("reasoning", "")
        if not isinstance(reasoning, str):
            reasoning = str(reasoning)
        if not reasoning.strip():
            reasoning = "No reasoning provided"

        return AIDecision(
            decision=decision, reasoning=reasoning.strip(), raw_response=raw_response
        )

    def _handle_rate_limit(self, retry_after: Optional[int] = None) -> float:
        """
        Handle HTTP 429 Rate Limit from Anthropic API.

        When receiving rate limit:
        1. Use retry_after value from header (if available)
        2. Otherwise apply exponential backoff
        3. Increase interval between calls to reduce load

        Args:
            retry_after: Value from Retry-After header (in seconds)

        Returns:
            Wait time in seconds
        """
        # Determine wait time
        if retry_after is not None and retry_after > 0:
            wait_time = float(retry_after)
        else:
            # Exponential backoff: base_delay * 2^(consecutive_errors)
            wait_time = min(
                self.base_delay * (2**self.state.consecutive_errors), self.max_delay
            )

        logging.warning(
            f"Rate limited by Anthropic API, waiting {wait_time:.1f}s "
            f"(consecutive errors: {self.state.consecutive_errors})"
        )

        # Increase check interval to reduce load
        new_interval = min(
            self.state.current_interval * 2, 300  # Maximum 5 minutes between checks
        )
        if new_interval != self.state.current_interval:
            logging.info(
                f"Increasing check interval: {self.state.current_interval}s -> {new_interval}s"
            )
            self.state.current_interval = new_interval

        return wait_time

    def _calculate_backoff_delay(self, attempt: int) -> float:
        """
        Calculate delay for retry with exponential backoff.

        Formula: min(base_delay * 2^attempt, max_delay)

        Examples (base_delay=2, max_delay=60):
        - attempt 0: 2 * 2^0 = 2 seconds
        - attempt 1: 2 * 2^1 = 4 seconds
        - attempt 2: 2 * 2^2 = 8 seconds
        - attempt 3: 2 * 2^3 = 16 seconds
        - attempt 4: 2 * 2^4 = 32 seconds
        - attempt 5: min(64, 60) = 60 seconds

        Args:
            attempt: Attempt number (0-based)

        Returns:
            Delay in seconds
        """
        return min(self.base_delay * (2**attempt), self.max_delay)

    def _extract_retry_after(self, error: anthropic.RateLimitError) -> Optional[int]:
        """
        Extract retry-after value from rate limit error.

        Args:
            error: RateLimitError exception

        Returns:
            retry-after value in seconds or None
        """
        if hasattr(error, "response") and error.response is not None:
            retry_after_header = error.response.headers.get("retry-after")
            if retry_after_header:
                try:
                    return int(retry_after_header)
                except ValueError:
                    pass
        return None

    def _update_state(
        self, symbol: str, price: float, decision: Optional[AIDecision] = None
    ) -> None:
        """
        Update state after successful AI call.

        Args:
            symbol: Trading pair
            price: Current price
            decision: AI decision (optional, for caching)
        """
        self.state.last_call_time = time.time()
        self.state.last_price = price
        self.state.last_symbol = symbol
        self.state.consecutive_errors = 0

        # Cache the decision
        if decision is not None:
            self._last_decision = decision

        # Restore interval after successful call
        if self.state.current_interval != self.default_interval:
            logging.info(
                f"Restoring check interval: {self.state.current_interval}s -> {self.default_interval}s"
            )
            self.state.current_interval = self.default_interval

    def get_cached_decision(self) -> Optional[AIDecision]:
        """
        Return the last cached decision.

        Used when is_call_needed() returns False.

        Returns:
            Last AIDecision or None if cache is empty
        """
        return self._last_decision

    def reset_cache(self) -> None:
        """
        Force reset the AI client cache.

        Used when:
        - Configuration changes
        - Manual reset by user
        - In tests
        """
        self.state = AIClientState(current_interval=self.default_interval)
        self._last_decision = None
        logging.info("AI client cache reset")

    def get_cache_info(self) -> dict:
        """
        Return information about current cache state.

        Useful for debugging and monitoring.

        Returns:
            Dictionary with cache information
        """
        now = time.time()
        time_since_last_call = (
            now - self.state.last_call_time if self.state.last_call_time > 0 else None
        )

        return {
            "last_symbol": self.state.last_symbol or None,
            "last_price": self.state.last_price if self.state.last_price > 0 else None,
            "last_call_seconds_ago": time_since_last_call,
            "current_interval": self.state.current_interval,
            "consecutive_errors": self.state.consecutive_errors,
            "has_cached_decision": self._last_decision is not None,
            "cached_decision": (
                self._last_decision.decision if self._last_decision else None
            ),
        }
