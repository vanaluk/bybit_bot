"""
Unit tests for AIClient API integration

Tests the interaction with Anthropic API using mocks.
"""

import time
from unittest.mock import MagicMock, patch

import anthropic
import pytest

from ai_client import AIClient, AIDecision, AIError


class TestAIClientShouldBuy:
    """Tests for should_buy method"""

    @patch("ai_client.anthropic.Anthropic")
    def test_sends_correct_request(self, mock_anthropic):
        """Sends correct request to API"""
        # Setup mock
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text='{"decision": "hold", "reasoning": "test"}')
        ]
        mock_client.messages.create.return_value = mock_response

        client = AIClient(api_key="sk-ant-test")

        client.should_buy(
            symbol="BTCUSDT", current_price=50000.0, change_1h=2.5, change_3h=-1.2
        )

        # Verify call
        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args.kwargs

        assert call_kwargs["model"] == "claude-sonnet-4-20250514"
        assert call_kwargs["max_tokens"] == 256
        assert "system" in call_kwargs
        assert "messages" in call_kwargs

    @patch("ai_client.anthropic.Anthropic")
    def test_returns_ai_decision(self, mock_anthropic):
        """Returns AIDecision"""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text='{"decision": "buy", "reasoning": "Good opportunity"}')
        ]
        mock_client.messages.create.return_value = mock_response

        client = AIClient(api_key="sk-ant-test")

        decision = client.should_buy(
            symbol="BTCUSDT", current_price=50000.0, change_1h=5.0, change_3h=-3.5
        )

        assert isinstance(decision, AIDecision)
        assert decision.decision == "buy"
        assert decision.should_buy is True
        assert "Good opportunity" in decision.reasoning

    @patch("ai_client.anthropic.Anthropic")
    def test_prompt_contains_data(self, mock_anthropic):
        """Prompt contains passed data"""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text='{"decision": "hold", "reasoning": "test"}')
        ]
        mock_client.messages.create.return_value = mock_response

        client = AIClient(api_key="sk-ant-test")

        client.should_buy(
            symbol="WIFUSDT", current_price=2.45, change_1h=3.5, change_3h=1.2
        )

        call_kwargs = mock_client.messages.create.call_args.kwargs
        messages = call_kwargs["messages"]
        user_message = messages[0]["content"]

        assert "WIFUSDT" in user_message
        assert "2.45" in user_message
        assert "+3.50%" in user_message
        assert "+1.20%" in user_message


class TestAIClientInit:
    """Tests for client initialization"""

    @patch("ai_client.anthropic.Anthropic")
    def test_creates_anthropic_client(self, mock_anthropic):
        """Creates Anthropic client"""
        AIClient(api_key="sk-ant-test", timeout=60)

        mock_anthropic.assert_called_once_with(api_key="sk-ant-test", timeout=60)

    @patch("ai_client.anthropic.Anthropic")
    def test_raises_on_init_error(self, mock_anthropic):
        """Raises AIError on initialization error"""
        mock_anthropic.side_effect = Exception("Init failed")

        with pytest.raises(AIError) as exc_info:
            AIClient(api_key="sk-ant-test")

        assert "Failed to initialize" in str(exc_info.value)


class TestParseResponse:
    """Tests for response parsing"""

    @patch("ai_client.anthropic.Anthropic")
    def test_parses_valid_buy_response(self, mock_anthropic):
        """Parses valid response with decision=buy"""
        mock_anthropic.return_value = MagicMock()
        client = AIClient(api_key="sk-ant-test")

        response = '{"decision": "buy", "reasoning": "Strong momentum detected"}'
        decision = client._parse_response(response)

        assert decision.decision == "buy"
        assert decision.should_buy is True
        assert decision.reasoning == "Strong momentum detected"

    @patch("ai_client.anthropic.Anthropic")
    def test_parses_valid_hold_response(self, mock_anthropic):
        """Parses valid response with decision=hold"""
        mock_anthropic.return_value = MagicMock()
        client = AIClient(api_key="sk-ant-test")

        response = '{"decision": "hold", "reasoning": "Waiting for better entry"}'
        decision = client._parse_response(response)

        assert decision.decision == "hold"
        assert decision.should_buy is False
        assert decision.reasoning == "Waiting for better entry"

    @patch("ai_client.anthropic.Anthropic")
    def test_normalizes_decision_case(self, mock_anthropic):
        """Normalizes decision case"""
        mock_anthropic.return_value = MagicMock()
        client = AIClient(api_key="sk-ant-test")

        response = '{"decision": "BUY", "reasoning": "test"}'
        decision = client._parse_response(response)

        assert decision.decision == "buy"
        assert decision.should_buy is True

    @patch("ai_client.anthropic.Anthropic")
    def test_strips_whitespace_from_decision(self, mock_anthropic):
        """Strips whitespace from decision"""
        mock_anthropic.return_value = MagicMock()
        client = AIClient(api_key="sk-ant-test")

        response = '{"decision": "  buy  ", "reasoning": "test"}'
        decision = client._parse_response(response)

        assert decision.decision == "buy"

    @patch("ai_client.anthropic.Anthropic")
    def test_handles_missing_reasoning(self, mock_anthropic):
        """Handles missing reasoning"""
        mock_anthropic.return_value = MagicMock()
        client = AIClient(api_key="sk-ant-test")

        response = '{"decision": "hold"}'
        decision = client._parse_response(response)

        assert decision.decision == "hold"
        assert decision.reasoning == "No reasoning provided"

    @patch("ai_client.anthropic.Anthropic")
    def test_handles_empty_reasoning(self, mock_anthropic):
        """Handles empty reasoning"""
        mock_anthropic.return_value = MagicMock()
        client = AIClient(api_key="sk-ant-test")

        response = '{"decision": "hold", "reasoning": ""}'
        decision = client._parse_response(response)

        assert decision.reasoning == "No reasoning provided"

    @patch("ai_client.anthropic.Anthropic")
    def test_handles_whitespace_reasoning(self, mock_anthropic):
        """Handles reasoning with only whitespace"""
        mock_anthropic.return_value = MagicMock()
        client = AIClient(api_key="sk-ant-test")

        response = '{"decision": "hold", "reasoning": "   "}'
        decision = client._parse_response(response)

        assert decision.reasoning == "No reasoning provided"

    @patch("ai_client.anthropic.Anthropic")
    def test_strips_markdown_json_block(self, mock_anthropic):
        """Strips markdown code block with json"""
        mock_anthropic.return_value = MagicMock()
        client = AIClient(api_key="sk-ant-test")

        response = '```json\n{"decision": "buy", "reasoning": "test"}\n```'
        decision = client._parse_response(response)

        assert decision.decision == "buy"

    @patch("ai_client.anthropic.Anthropic")
    def test_strips_markdown_block_without_language(self, mock_anthropic):
        """Strips markdown code block without language tag"""
        mock_anthropic.return_value = MagicMock()
        client = AIClient(api_key="sk-ant-test")

        response = '```\n{"decision": "hold", "reasoning": "test"}\n```'
        decision = client._parse_response(response)

        assert decision.decision == "hold"

    @patch("ai_client.anthropic.Anthropic")
    def test_treats_unexpected_decision_as_hold(self, mock_anthropic):
        """Unexpected decision value is treated as hold"""
        mock_anthropic.return_value = MagicMock()
        client = AIClient(api_key="sk-ant-test")

        response = '{"decision": "wait", "reasoning": "test"}'
        decision = client._parse_response(response)

        assert decision.decision == "hold"
        assert decision.should_buy is False

    @patch("ai_client.anthropic.Anthropic")
    def test_treats_sell_as_hold(self, mock_anthropic):
        """decision=sell is treated as hold"""
        mock_anthropic.return_value = MagicMock()
        client = AIClient(api_key="sk-ant-test")

        response = '{"decision": "sell", "reasoning": "test"}'
        decision = client._parse_response(response)

        assert decision.decision == "hold"

    @patch("ai_client.anthropic.Anthropic")
    def test_stores_raw_response(self, mock_anthropic):
        """Stores raw response"""
        mock_anthropic.return_value = MagicMock()
        client = AIClient(api_key="sk-ant-test")

        response = '{"decision": "buy", "reasoning": "test"}'
        decision = client._parse_response(response)

        assert decision.raw_response == response


class TestParseResponseErrors:
    """Tests for parsing error handling"""

    @patch("ai_client.anthropic.Anthropic")
    def test_raises_on_invalid_json(self, mock_anthropic):
        """Raises AIError on invalid JSON"""
        mock_anthropic.return_value = MagicMock()
        client = AIClient(api_key="sk-ant-test")

        with pytest.raises(AIError) as exc_info:
            client._parse_response("not valid json")

        assert "Invalid JSON" in str(exc_info.value)

    @patch("ai_client.anthropic.Anthropic")
    def test_raises_on_json_array(self, mock_anthropic):
        """Raises AIError if JSON is an array"""
        mock_anthropic.return_value = MagicMock()
        client = AIClient(api_key="sk-ant-test")

        with pytest.raises(AIError) as exc_info:
            client._parse_response('[{"decision": "buy"}]')

        assert "must be a JSON object" in str(exc_info.value)

    @patch("ai_client.anthropic.Anthropic")
    def test_raises_on_missing_decision_field(self, mock_anthropic):
        """Raises AIError when decision field is missing"""
        mock_anthropic.return_value = MagicMock()
        client = AIClient(api_key="sk-ant-test")

        with pytest.raises(AIError) as exc_info:
            client._parse_response('{"reasoning": "some text"}')

        assert "Missing 'decision'" in str(exc_info.value)

    @patch("ai_client.anthropic.Anthropic")
    def test_raises_on_non_string_decision(self, mock_anthropic):
        """Raises AIError if decision is not a string"""
        mock_anthropic.return_value = MagicMock()
        client = AIClient(api_key="sk-ant-test")

        with pytest.raises(AIError) as exc_info:
            client._parse_response('{"decision": 1, "reasoning": "test"}')

        assert "'decision' must be a string" in str(exc_info.value)

    @patch("ai_client.anthropic.Anthropic")
    def test_raises_on_null_decision(self, mock_anthropic):
        """Raises AIError if decision = null"""
        mock_anthropic.return_value = MagicMock()
        client = AIClient(api_key="sk-ant-test")

        with pytest.raises(AIError) as exc_info:
            client._parse_response('{"decision": null, "reasoning": "test"}')

        assert "'decision' must be a string" in str(exc_info.value)


class TestExtractJsonFromResponse:
    """Tests for _extract_json_from_response"""

    @patch("ai_client.anthropic.Anthropic")
    def test_returns_plain_json_unchanged(self, mock_anthropic):
        """Returns plain JSON unchanged"""
        mock_anthropic.return_value = MagicMock()
        client = AIClient(api_key="sk-ant-test")

        json_str = '{"decision": "buy"}'

        result = client._extract_json_from_response(json_str)

        assert result == json_str

    @patch("ai_client.anthropic.Anthropic")
    def test_extracts_from_json_code_block(self, mock_anthropic):
        """Extracts JSON from ```json ... ```"""
        mock_anthropic.return_value = MagicMock()
        client = AIClient(api_key="sk-ant-test")

        response = '```json\n{"decision": "buy"}\n```'

        result = client._extract_json_from_response(response)

        assert result == '{"decision": "buy"}'

    @patch("ai_client.anthropic.Anthropic")
    def test_extracts_from_plain_code_block(self, mock_anthropic):
        """Extracts JSON from ``` ... ```"""
        mock_anthropic.return_value = MagicMock()
        client = AIClient(api_key="sk-ant-test")

        response = '```\n{"decision": "hold"}\n```'

        result = client._extract_json_from_response(response)

        assert result == '{"decision": "hold"}'

    @patch("ai_client.anthropic.Anthropic")
    def test_handles_extra_whitespace(self, mock_anthropic):
        """Handles extra whitespace"""
        mock_anthropic.return_value = MagicMock()
        client = AIClient(api_key="sk-ant-test")

        response = '  ```json\n  {"decision": "buy"}  \n```  '

        result = client._extract_json_from_response(response.strip())

        assert '{"decision": "buy"}' in result


class TestRetryLogic:
    """Tests for retry logic."""

    @patch("ai_client.anthropic.Anthropic")
    def test_successful_request_no_retry(self, mock_anthropic):
        """Successful request does not require retry."""
        # Setup mock for successful response
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text='{"decision": "buy", "reasoning": "test"}')
        ]
        mock_client.messages.create.return_value = mock_response

        client = AIClient(api_key="sk-ant-test")

        decision = client.should_buy("BTCUSDT", 50000, -2.5, -3.5)

        assert decision.decision == "buy"
        assert mock_client.messages.create.call_count == 1

    @patch("ai_client.anthropic.Anthropic")
    def test_retry_on_rate_limit(self, mock_anthropic):
        """Retry on rate limit."""
        # First call — rate limit, second — success
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        rate_limit_error = anthropic.RateLimitError(
            message="Rate limited",
            response=MagicMock(headers={"retry-after": "1"}),
            body=None,
        )
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text='{"decision": "hold", "reasoning": "test"}')
        ]

        mock_client.messages.create.side_effect = [rate_limit_error, mock_response]

        client = AIClient(api_key="sk-ant-test")

        with patch("ai_client.time.sleep") as mock_sleep:
            decision = client.should_buy("BTCUSDT", 50000, -2.5, -3.5)

        assert decision.decision == "hold"
        assert mock_client.messages.create.call_count == 2
        mock_sleep.assert_called_once()

    @patch("ai_client.anthropic.Anthropic")
    def test_retry_on_api_error(self, mock_anthropic):
        """Retry on API error (500)."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        api_error = anthropic.APIStatusError(
            message="Internal Server Error",
            response=MagicMock(status_code=500),
            body=None,
        )
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text='{"decision": "buy", "reasoning": "test"}')
        ]

        mock_client.messages.create.side_effect = [api_error, mock_response]

        client = AIClient(api_key="sk-ant-test")

        with patch("ai_client.time.sleep"):
            decision = client.should_buy("BTCUSDT", 50000, -2.5, -3.5)

        assert decision.decision == "buy"
        assert mock_client.messages.create.call_count == 2

    @patch("ai_client.anthropic.Anthropic")
    def test_retry_on_connection_error(self, mock_anthropic):
        """Retry on connection error."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        connection_error = anthropic.APIConnectionError(
            message="Connection failed", request=MagicMock()
        )
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text='{"decision": "hold", "reasoning": "test"}')
        ]

        mock_client.messages.create.side_effect = [connection_error, mock_response]

        client = AIClient(api_key="sk-ant-test")

        with patch("ai_client.time.sleep"):
            decision = client.should_buy("BTCUSDT", 50000, -2.5, -3.5)

        assert decision.decision == "hold"
        assert mock_client.messages.create.call_count == 2

    @patch("ai_client.anthropic.Anthropic")
    def test_raises_after_max_retries(self, mock_anthropic):
        """Raises AIError after exhausting retries."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        client = AIClient(api_key="sk-ant-test", max_retries=3)

        api_error = anthropic.APIStatusError(
            message="Server Error", response=MagicMock(status_code=500), body=None
        )

        mock_client.messages.create.side_effect = api_error

        with patch("ai_client.time.sleep"):
            with pytest.raises(AIError) as exc_info:
                client.should_buy("BTCUSDT", 50000, -2.5, -3.5)

        assert "Failed to get AI decision after 3 attempts" in str(exc_info.value)
        assert mock_client.messages.create.call_count == 3

    @patch("ai_client.anthropic.Anthropic")
    def test_no_retry_on_parse_error(self, mock_anthropic):
        """No retry on parse error."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="invalid json")]
        mock_client.messages.create.return_value = mock_response

        client = AIClient(api_key="sk-ant-test")

        with pytest.raises(AIError) as exc_info:
            client.should_buy("BTCUSDT", 50000, -2.5, -3.5)

        assert "Invalid JSON" in str(exc_info.value)
        # Only one call, no retry
        assert mock_client.messages.create.call_count == 1


class TestExponentialBackoff:
    """Tests for exponential backoff."""

    @patch("ai_client.anthropic.Anthropic")
    def test_backoff_delay_increases(self, mock_anthropic):
        """Delay increases exponentially."""
        mock_anthropic.return_value = MagicMock()
        client = AIClient(api_key="sk-ant-test")

        assert client._calculate_backoff_delay(0) == 2.0
        assert client._calculate_backoff_delay(1) == 4.0
        assert client._calculate_backoff_delay(2) == 8.0
        assert client._calculate_backoff_delay(3) == 16.0
        assert client._calculate_backoff_delay(4) == 32.0

    @patch("ai_client.anthropic.Anthropic")
    def test_backoff_delay_max_limit(self, mock_anthropic):
        """Delay does not exceed max_delay."""
        mock_anthropic.return_value = MagicMock()
        client = AIClient(api_key="sk-ant-test")
        client.max_delay = 60.0

        assert client._calculate_backoff_delay(10) == 60.0
        assert client._calculate_backoff_delay(100) == 60.0


class TestRateLimitHandling:
    """Tests for rate limit handling."""

    @patch("ai_client.anthropic.Anthropic")
    def test_uses_retry_after_header(self, mock_anthropic):
        """Uses value from retry-after header."""
        mock_anthropic.return_value = MagicMock()
        client = AIClient(api_key="sk-ant-test")

        wait_time = client._handle_rate_limit(retry_after=30)

        assert wait_time == 30.0

    @patch("ai_client.anthropic.Anthropic")
    def test_uses_exponential_backoff_without_header(self, mock_anthropic):
        """Uses exponential backoff without header."""
        mock_anthropic.return_value = MagicMock()
        client = AIClient(api_key="sk-ant-test")
        client.state.consecutive_errors = 2

        wait_time = client._handle_rate_limit(retry_after=None)

        # base_delay * 2^consecutive_errors = 2 * 2^2 = 8
        assert wait_time == 8.0

    @patch("ai_client.anthropic.Anthropic")
    def test_increases_check_interval(self, mock_anthropic):
        """Increases check interval on rate limit."""
        mock_anthropic.return_value = MagicMock()
        client = AIClient(api_key="sk-ant-test")
        initial_interval = client.state.current_interval

        client._handle_rate_limit(retry_after=10)

        assert client.state.current_interval == initial_interval * 2

    @patch("ai_client.anthropic.Anthropic")
    def test_check_interval_max_limit(self, mock_anthropic):
        """Interval does not exceed 5 minutes."""
        mock_anthropic.return_value = MagicMock()
        client = AIClient(api_key="sk-ant-test")
        client.state.current_interval = 200

        client._handle_rate_limit(retry_after=10)

        assert client.state.current_interval == 300  # 5 minutes maximum


class TestStateManagement:
    """Tests for state management."""

    @patch("ai_client.anthropic.Anthropic")
    def test_update_state_on_success(self, mock_anthropic):
        """Updates state on success."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text='{"decision": "buy", "reasoning": "test"}')
        ]
        mock_client.messages.create.return_value = mock_response

        client = AIClient(api_key="sk-ant-test")
        client.state.consecutive_errors = 5
        client.state.current_interval = 120

        client.should_buy("BTCUSDT", 50000, -2.5, -3.5)

        assert client.state.consecutive_errors == 0
        assert client.state.last_symbol == "BTCUSDT"
        assert client.state.last_price == 50000
        assert client.state.current_interval == client.default_interval

    @patch("ai_client.anthropic.Anthropic")
    def test_increments_errors_on_failure(self, mock_anthropic):
        """Increments error counter on failure."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        client = AIClient(api_key="sk-ant-test", max_retries=2)

        api_error = anthropic.APIStatusError(
            message="Error", response=MagicMock(status_code=500), body=None
        )
        mock_client.messages.create.side_effect = api_error

        initial_errors = client.state.consecutive_errors

        with patch("ai_client.time.sleep"):
            with pytest.raises(AIError):
                client.should_buy("BTCUSDT", 50000, -2.5, -3.5)

        assert client.state.consecutive_errors == initial_errors + 2


class TestExtractRetryAfter:
    """Tests for extracting retry-after."""

    @patch("ai_client.anthropic.Anthropic")
    def test_extracts_from_header(self, mock_anthropic):
        """Extracts value from header."""
        mock_anthropic.return_value = MagicMock()
        client = AIClient(api_key="sk-ant-test")

        error = MagicMock()
        error.response = MagicMock()
        error.response.headers = {"retry-after": "45"}

        result = client._extract_retry_after(error)

        assert result == 45

    @patch("ai_client.anthropic.Anthropic")
    def test_returns_none_without_header(self, mock_anthropic):
        """Returns None without header."""
        mock_anthropic.return_value = MagicMock()
        client = AIClient(api_key="sk-ant-test")

        error = MagicMock()
        error.response = MagicMock()
        error.response.headers = {}

        result = client._extract_retry_after(error)

        assert result is None

    @patch("ai_client.anthropic.Anthropic")
    def test_returns_none_on_invalid_value(self, mock_anthropic):
        """Returns None on invalid value."""
        mock_anthropic.return_value = MagicMock()
        client = AIClient(api_key="sk-ant-test")

        error = MagicMock()
        error.response = MagicMock()
        error.response.headers = {"retry-after": "invalid"}

        result = client._extract_retry_after(error)

        assert result is None

    @patch("ai_client.anthropic.Anthropic")
    def test_returns_none_without_response(self, mock_anthropic):
        """Returns None without response."""
        mock_anthropic.return_value = MagicMock()
        client = AIClient(api_key="sk-ant-test")

        error = MagicMock()
        error.response = None

        result = client._extract_retry_after(error)

        assert result is None


class TestIsCallNeeded:
    """Tests for is_call_needed."""

    @patch("ai_client.anthropic.Anthropic")
    def test_first_call_always_needed(self, mock_anthropic):
        """First call is always needed."""
        client = AIClient(api_key="sk-ant-test", check_interval=60)
        assert client.is_call_needed("BTCUSDT", 50000) is True

    @patch("ai_client.anthropic.Anthropic")
    def test_call_needed_when_symbol_changes(self, mock_anthropic):
        """Call needed when symbol changes."""
        # Simulate previous call
        client = AIClient(api_key="sk-ant-test", check_interval=60)
        client.state.last_call_time = time.time()
        client.state.last_symbol = "BTCUSDT"
        client.state.last_price = 50000

        assert client.is_call_needed("ETHUSDT", 3000) is True

    @patch("ai_client.anthropic.Anthropic")
    def test_call_not_needed_within_interval(self, mock_anthropic):
        """Call not needed within interval."""
        client = AIClient(api_key="sk-ant-test", check_interval=60)
        client.state.last_call_time = time.time()
        client.state.last_symbol = "BTCUSDT"
        client.state.last_price = 50000
        client.state.current_interval = 60

        assert client.is_call_needed("BTCUSDT", 50100) is False

    @patch("ai_client.anthropic.Anthropic")
    def test_call_not_needed_small_price_change(self, mock_anthropic):
        """Call not needed for small price change."""
        # Interval elapsed
        client = AIClient(api_key="sk-ant-test", check_interval=60)
        client.state.last_call_time = time.time() - 120
        client.state.last_symbol = "BTCUSDT"
        client.state.last_price = 50000
        client.state.current_interval = 60
        client.price_change_threshold = 0.5

        # Change 0.1% < 0.5%
        new_price = 50000 * 1.001  # 50050
        assert client.is_call_needed("BTCUSDT", new_price) is False

    @patch("ai_client.anthropic.Anthropic")
    def test_call_needed_significant_price_change(self, mock_anthropic):
        """Call needed for significant price change."""
        # Interval elapsed
        client = AIClient(api_key="sk-ant-test", check_interval=60)
        client.state.last_call_time = time.time() - 120
        client.state.last_symbol = "BTCUSDT"
        client.state.last_price = 50000
        client.state.current_interval = 60
        client.price_change_threshold = 0.5

        # Change 1% > 0.5%
        new_price = 50000 * 1.01  # 50500
        assert client.is_call_needed("BTCUSDT", new_price) is True

    @patch("ai_client.anthropic.Anthropic")
    def test_call_needed_after_interval_elapsed(self, mock_anthropic):
        """Call needed after interval elapsed with significant price change."""
        client = AIClient(api_key="sk-ant-test", check_interval=60)
        client.state.last_call_time = time.time() - 120
        client.state.last_symbol = "BTCUSDT"
        client.state.last_price = 50000
        client.state.current_interval = 60

        # Price changed significantly
        assert client.is_call_needed("BTCUSDT", 52000) is True


class TestCaching:
    """Tests for decision caching."""

    @patch("ai_client.anthropic.Anthropic")
    def test_caches_decision(self, mock_anthropic):
        """Caches decision after call."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text='{"decision": "buy", "reasoning": "test"}')
        ]
        mock_client.messages.create.return_value = mock_response

        client = AIClient(api_key="sk-ant-test", check_interval=60)
        client.should_buy("BTCUSDT", 50000, -2.5, -3.5)

        assert client._last_decision is not None
        assert client._last_decision.decision == "buy"

    @patch("ai_client.anthropic.Anthropic")
    def test_returns_cached_decision_when_not_needed(self, mock_anthropic):
        """Returns cached decision when call is not needed."""
        # First make real call
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text='{"decision": "buy", "reasoning": "test"}')
        ]
        mock_client.messages.create.return_value = mock_response

        client = AIClient(api_key="sk-ant-test", check_interval=60)
        client.should_buy("BTCUSDT", 50000, -2.5, -3.5)

        # Reset call counter
        mock_client.messages.create.reset_mock()

        # Simulate elapsed interval but small price change
        client.state.last_call_time = time.time() - 120  # Interval elapsed
        # Price change 0.1% < 0.5% threshold
        new_price = 50000 * 1.001  # 50050

        # Second call with small price change
        # Should return cache without API call
        decision = client.should_buy("BTCUSDT", new_price, -2.5, -3.5)

        assert decision.decision == "buy"
        mock_client.messages.create.assert_not_called()

    @patch("ai_client.anthropic.Anthropic")
    def test_force_ignores_cache(self, mock_anthropic):
        """Force parameter ignores cache."""
        # Cache decision
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text='{"decision": "hold", "reasoning": "cached"}')
        ]
        mock_client.messages.create.return_value = mock_response

        client = AIClient(api_key="sk-ant-test", check_interval=60)
        client._last_decision = AIDecision("hold", "cached")
        client.state.last_call_time = time.time()
        client.state.last_symbol = "BTCUSDT"
        client.state.last_price = 50000

        mock_response2 = MagicMock()
        mock_response2.content = [
            MagicMock(text='{"decision": "buy", "reasoning": "forced"}')
        ]
        mock_client.messages.create.return_value = mock_response2

        decision = client.should_buy("BTCUSDT", 50000, -2.5, -3.5, force=True)

        assert decision.decision == "buy"
        assert decision.reasoning == "forced"
        mock_client.messages.create.assert_called_once()

    @patch("ai_client.anthropic.Anthropic")
    def test_get_cached_decision_returns_last(self, mock_anthropic):
        """get_cached_decision returns last decision."""
        client = AIClient(api_key="sk-ant-test", check_interval=60)
        client._last_decision = AIDecision("hold", "test reason")

        cached = client.get_cached_decision()

        assert cached is not None
        assert cached.decision == "hold"
        assert cached.reasoning == "test reason"

    @patch("ai_client.anthropic.Anthropic")
    def test_get_cached_decision_returns_none_when_empty(self, mock_anthropic):
        """get_cached_decision returns None when cache is empty."""
        client = AIClient(api_key="sk-ant-test", check_interval=60)
        cached = client.get_cached_decision()

        assert cached is None


class TestResetCache:
    """Tests for cache reset."""

    @patch("ai_client.anthropic.Anthropic")
    def test_reset_clears_state(self, mock_anthropic):
        """reset_cache clears state."""
        client = AIClient(api_key="sk-ant-test", check_interval=60)
        client.state.last_call_time = time.time()
        client.state.last_symbol = "BTCUSDT"
        client.state.last_price = 50000
        client.state.consecutive_errors = 5
        client._last_decision = AIDecision("buy", "test")

        client.reset_cache()

        assert client.state.last_call_time == 0.0
        assert client.state.last_symbol == ""
        assert client.state.last_price == 0.0
        assert client.state.consecutive_errors == 0
        assert client._last_decision is None

    @patch("ai_client.anthropic.Anthropic")
    def test_reset_restores_default_interval(self, mock_anthropic):
        """reset_cache restores default interval."""
        client = AIClient(api_key="sk-ant-test", check_interval=60)
        client.state.current_interval = 300  # Increased due to rate limit

        client.reset_cache()

        assert client.state.current_interval == client.default_interval


class TestGetCacheInfo:
    """Tests for getting cache info."""

    @patch("ai_client.anthropic.Anthropic")
    def test_returns_empty_info_initially(self, mock_anthropic):
        """Returns empty info initially."""
        client = AIClient(api_key="sk-ant-test", check_interval=60)
        info = client.get_cache_info()

        assert info["last_symbol"] is None
        assert info["last_price"] is None
        assert info["last_call_seconds_ago"] is None
        assert info["has_cached_decision"] is False
        assert info["cached_decision"] is None

    @patch("ai_client.anthropic.Anthropic")
    def test_returns_filled_info_after_call(self, mock_anthropic):
        """Returns filled info after call."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text='{"decision": "buy", "reasoning": "test"}')
        ]
        mock_client.messages.create.return_value = mock_response

        client = AIClient(api_key="sk-ant-test", check_interval=60)
        client.should_buy("BTCUSDT", 50000, -2.5, -3.5)

        info = client.get_cache_info()

        assert info["last_symbol"] == "BTCUSDT"
        assert info["last_price"] == 50000
        assert info["last_call_seconds_ago"] is not None
        assert info["last_call_seconds_ago"] < 1  # Just called
        assert info["has_cached_decision"] is True
        assert info["cached_decision"] == "buy"


class TestPriceChangeCalculation:
    """Tests for price change calculation."""

    @patch("ai_client.anthropic.Anthropic")
    def test_price_increase_detected(self, mock_anthropic):
        """Detects price increase."""
        client = AIClient(api_key="sk-ant-test", check_interval=60)
        client.state.last_call_time = time.time() - 120
        client.state.last_symbol = "BTCUSDT"
        client.state.last_price = 50000
        client.state.current_interval = 60
        client.price_change_threshold = 0.5

        # Increase 2%
        new_price = 51000
        assert client.is_call_needed("BTCUSDT", new_price) is True

    @patch("ai_client.anthropic.Anthropic")
    def test_price_decrease_detected(self, mock_anthropic):
        """Detects price decrease."""
        client = AIClient(api_key="sk-ant-test", check_interval=60)
        client.state.last_call_time = time.time() - 120
        client.state.last_symbol = "BTCUSDT"
        client.state.last_price = 50000
        client.state.current_interval = 60
        client.price_change_threshold = 0.5

        # Decrease 2%
        new_price = 49000
        assert client.is_call_needed("BTCUSDT", new_price) is True

    @patch("ai_client.anthropic.Anthropic")
    def test_zero_last_price_always_calls(self, mock_anthropic):
        """With zero last price always calls."""
        client = AIClient(api_key="sk-ant-test", check_interval=60)
        client.state.last_call_time = time.time() - 120
        client.state.last_symbol = "BTCUSDT"
        client.state.last_price = 0.0  # Not set
        client.state.current_interval = 60

        assert client.is_call_needed("BTCUSDT", 50000) is True
