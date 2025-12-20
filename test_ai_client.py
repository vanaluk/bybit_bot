# test_ai_client.py

import pytest
from unittest.mock import MagicMock, patch
from ai_client import AIClient, AIDecision, AIError, AIClientState


class TestAIDecision:
    """Tests for AIDecision dataclass"""
    
    def test_should_buy_returns_true_for_buy(self):
        """should_buy returns True for decision='buy'"""
        decision = AIDecision(decision="buy", reasoning="test")
        assert decision.should_buy is True
    
    def test_should_buy_returns_false_for_hold(self):
        """should_buy returns False for decision='hold'"""
        decision = AIDecision(decision="hold", reasoning="test")
        assert decision.should_buy is False
    
    def test_should_buy_case_insensitive(self):
        """should_buy is case insensitive"""
        decision = AIDecision(decision="BUY", reasoning="test")
        assert decision.should_buy is True
    
    def test_raw_response_optional(self):
        """raw_response is optional"""
        decision = AIDecision(decision="hold", reasoning="test")
        assert decision.raw_response is None


class TestAIClientState:
    """Tests for AIClientState dataclass"""
    
    def test_default_values(self):
        """Verify default values"""
        state = AIClientState()
        
        assert state.last_call_time == 0.0
        assert state.last_price == 0.0
        assert state.last_symbol == ""
        assert state.consecutive_errors == 0
        assert state.current_interval == 60


class TestAIClient:
    """Tests for AIClient class"""
    
    def test_initialization(self):
        """Correct client initialization"""
        client = AIClient(
            api_key="sk-ant-test",
            model="test-model",
            timeout=60,
            max_retries=5,
            check_interval=120
        )
        
        assert client.api_key == "sk-ant-test"
        assert client.model == "test-model"
        assert client.timeout == 60
        assert client.max_retries == 5
        assert client.default_interval == 120
    
    def test_initialization_defaults(self):
        """Initialization with default values"""
        client = AIClient(api_key="sk-ant-test")
        
        assert client.model == "claude-sonnet-4-20250514"
        assert client.timeout == 30
        assert client.max_retries == 3
        assert client.default_interval == 60
    
    @patch('ai_client.anthropic.Anthropic')
    def test_stub_should_buy_returns_hold(self, mock_anthropic):
        """should_buy returns hold for corresponding API response"""
        # Setup mock
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"decision": "hold", "reasoning": "Stub response for testing"}')]
        mock_client.messages.create.return_value = mock_response
        
        client = AIClient(api_key="sk-ant-test")
        
        decision = client.should_buy(
            symbol="BTCUSDT",
            current_price=50000.0,
            change_1h=5.0,
            change_3h=-3.0
        )
        
        assert decision.decision == "hold"
        assert "stub" in decision.reasoning.lower()
    
    def test_stub_is_call_needed_returns_true(self):
        """is_call_needed always returns True for first call"""
        client = AIClient(api_key="sk-ant-test")
        
        result = client.is_call_needed("BTCUSDT", 50000.0)
        
        assert result is True


class TestAIError:
    """Tests for AIError exception"""
    
    def test_ai_error_is_exception(self):
        """AIError inherits from Exception"""
        with pytest.raises(AIError):
            raise AIError("Test error")
    
    def test_ai_error_message(self):
        """AIError stores message"""
        error = AIError("Custom error message")
        assert str(error) == "Custom error message"
