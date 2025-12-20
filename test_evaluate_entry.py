# test_evaluate_entry.py

from unittest.mock import MagicMock

import pytest

from ai_client import AIClient, AIDecision, AIError
from strategies import evaluate_entry


@pytest.fixture
def mock_ai_client():
    """Create a mock AI client."""
    client = MagicMock(spec=AIClient)
    return client


class TestRulesMode:
    """Tests for rules mode."""

    def test_quick_rise_triggers_buy(self):
        """Quick rise triggers buy."""
        should_buy, source = evaluate_entry(
            decision_mode="rules",
            ai_client=None,
            symbol="BTCUSDT",
            current_price=50000,
            quick_price_change=4.0,  # > 3%
            price_change=-1.0,
            quick_rise_threshold=3.0,
            price_drop_threshold=-3.0,
        )

        assert should_buy is True
        assert source == "rules_quick_rise"

    def test_price_drop_triggers_buy(self):
        """Price drop triggers buy."""
        should_buy, source = evaluate_entry(
            decision_mode="rules",
            ai_client=None,
            symbol="BTCUSDT",
            current_price=50000,
            quick_price_change=1.0,
            price_change=-4.0,  # < -3%
            quick_rise_threshold=3.0,
            price_drop_threshold=-3.0,
        )

        assert should_buy is True
        assert source == "rules_price_drop"

    def test_no_signal_holds(self):
        """No signal — hold."""
        should_buy, source = evaluate_entry(
            decision_mode="rules",
            ai_client=None,
            symbol="BTCUSDT",
            current_price=50000,
            quick_price_change=1.0,
            price_change=-1.0,
            quick_rise_threshold=3.0,
            price_drop_threshold=-3.0,
        )

        assert should_buy is False
        assert source == "hold"

    def test_ignores_ai_client(self, mock_ai_client):
        """Rules mode ignores AI client."""
        should_buy, source = evaluate_entry(
            decision_mode="rules",
            ai_client=mock_ai_client,
            symbol="BTCUSDT",
            current_price=50000,
            quick_price_change=1.0,
            price_change=-1.0,
            quick_rise_threshold=3.0,
            price_drop_threshold=-3.0,
        )

        assert should_buy is False
        mock_ai_client.should_buy.assert_not_called()


class TestAIMode:
    """Tests for ai mode."""

    def test_ai_buy_decision(self, mock_ai_client):
        """AI decides to buy."""
        mock_ai_client.should_buy.return_value = AIDecision(
            decision="buy", reasoning="Strong momentum"
        )

        should_buy, source = evaluate_entry(
            decision_mode="ai",
            ai_client=mock_ai_client,
            symbol="BTCUSDT",
            current_price=50000,
            quick_price_change=1.0,
            price_change=-1.0,
            quick_rise_threshold=3.0,
            price_drop_threshold=-3.0,
        )

        assert should_buy is True
        assert source == "ai"
        mock_ai_client.should_buy.assert_called_once()

    def test_ai_hold_decision(self, mock_ai_client):
        """AI decides to hold."""
        mock_ai_client.should_buy.return_value = AIDecision(
            decision="hold", reasoning="Weak momentum"
        )

        should_buy, source = evaluate_entry(
            decision_mode="ai",
            ai_client=mock_ai_client,
            symbol="BTCUSDT",
            current_price=50000,
            quick_price_change=5.0,  # Rules would trigger
            price_change=-5.0,
            quick_rise_threshold=3.0,
            price_drop_threshold=-3.0,
        )

        assert should_buy is False
        assert source == "hold"

    def test_ai_error_fallback_to_rules(self, mock_ai_client):
        """On AI error — fallback to rules."""
        mock_ai_client.should_buy.side_effect = AIError("API Error")

        should_buy, source = evaluate_entry(
            decision_mode="ai",
            ai_client=mock_ai_client,
            symbol="BTCUSDT",
            current_price=50000,
            quick_price_change=5.0,  # Rules will trigger
            price_change=-1.0,
            quick_rise_threshold=3.0,
            price_drop_threshold=-3.0,
        )

        assert should_buy is True
        assert source == "rules (ai_unavailable)"

    def test_ai_error_no_rules_signal(self, mock_ai_client):
        """On AI error and no rules signal — hold."""
        mock_ai_client.should_buy.side_effect = AIError("API Error")

        should_buy, source = evaluate_entry(
            decision_mode="ai",
            ai_client=mock_ai_client,
            symbol="BTCUSDT",
            current_price=50000,
            quick_price_change=1.0,  # Rules won't trigger
            price_change=-1.0,
            quick_rise_threshold=3.0,
            price_drop_threshold=-3.0,
        )

        assert should_buy is False
        assert source == "hold"

    def test_none_ai_client_fallback(self):
        """None AI client — fallback to rules."""
        should_buy, source = evaluate_entry(
            decision_mode="ai",
            ai_client=None,
            symbol="BTCUSDT",
            current_price=50000,
            quick_price_change=5.0,
            price_change=-1.0,
            quick_rise_threshold=3.0,
            price_drop_threshold=-3.0,
        )

        assert should_buy is True
        assert source == "rules (ai_unavailable)"


class TestCombinedMode:
    """Tests for combined mode."""

    def test_no_rules_signal_no_ai_call(self, mock_ai_client):
        """No rules signal — AI is not called."""
        should_buy, source = evaluate_entry(
            decision_mode="combined",
            ai_client=mock_ai_client,
            symbol="BTCUSDT",
            current_price=50000,
            quick_price_change=1.0,
            price_change=-1.0,
            quick_rise_threshold=3.0,
            price_drop_threshold=-3.0,
        )

        assert should_buy is False
        assert source == "hold"
        mock_ai_client.should_buy.assert_not_called()

    def test_rules_signal_ai_confirms(self, mock_ai_client):
        """Rules triggered, AI confirmed."""
        mock_ai_client.should_buy.return_value = AIDecision(
            decision="buy", reasoning="Confirmed"
        )

        should_buy, source = evaluate_entry(
            decision_mode="combined",
            ai_client=mock_ai_client,
            symbol="BTCUSDT",
            current_price=50000,
            quick_price_change=5.0,
            price_change=-1.0,
            quick_rise_threshold=3.0,
            price_drop_threshold=-3.0,
        )

        assert should_buy is True
        assert source == "rules+ai"

    def test_rules_signal_ai_vetoes(self, mock_ai_client):
        """Rules triggered, AI rejected."""
        mock_ai_client.should_buy.return_value = AIDecision(
            decision="hold", reasoning="Not a good entry"
        )

        should_buy, source = evaluate_entry(
            decision_mode="combined",
            ai_client=mock_ai_client,
            symbol="BTCUSDT",
            current_price=50000,
            quick_price_change=5.0,
            price_change=-1.0,
            quick_rise_threshold=3.0,
            price_drop_threshold=-3.0,
        )

        assert should_buy is False
        assert source == "ai_veto"

    def test_rules_signal_ai_error_fallback(self, mock_ai_client):
        """Rules triggered, AI error — fallback."""
        mock_ai_client.should_buy.side_effect = AIError("API Error")

        should_buy, source = evaluate_entry(
            decision_mode="combined",
            ai_client=mock_ai_client,
            symbol="BTCUSDT",
            current_price=50000,
            quick_price_change=5.0,
            price_change=-1.0,
            quick_rise_threshold=3.0,
            price_drop_threshold=-3.0,
        )

        assert should_buy is True
        assert source == "rules (ai_unavailable)"

    def test_none_ai_client_uses_rules(self):
        """None AI client — only rules are used."""
        should_buy, source = evaluate_entry(
            decision_mode="combined",
            ai_client=None,
            symbol="BTCUSDT",
            current_price=50000,
            quick_price_change=5.0,
            price_change=-1.0,
            quick_rise_threshold=3.0,
            price_drop_threshold=-3.0,
        )

        assert should_buy is True
        assert source == "rules (ai_unavailable)"


class TestEdgeCases:
    """Tests for edge cases."""

    def test_unknown_mode_defaults_to_rules(self):
        """Unknown mode — fallback to rules."""
        should_buy, source = evaluate_entry(
            decision_mode="unknown_mode",
            ai_client=None,
            symbol="BTCUSDT",
            current_price=50000,
            quick_price_change=5.0,
            price_change=-1.0,
            quick_rise_threshold=3.0,
            price_drop_threshold=-3.0,
        )

        assert should_buy is True
        assert source == "rules"

    def test_exact_threshold_triggers(self):
        """Exact threshold value triggers signal."""
        should_buy, source = evaluate_entry(
            decision_mode="rules",
            ai_client=None,
            symbol="BTCUSDT",
            current_price=50000,
            quick_price_change=3.0,  # Exactly at threshold
            price_change=-1.0,
            quick_rise_threshold=3.0,
            price_drop_threshold=-3.0,
        )

        assert should_buy is True
        assert source == "rules_quick_rise"

    def test_both_conditions_met_quick_rise_priority(self):
        """When both conditions are met — quick rise has priority."""
        should_buy, source = evaluate_entry(
            decision_mode="rules",
            ai_client=None,
            symbol="BTCUSDT",
            current_price=50000,
            quick_price_change=5.0,
            price_change=-5.0,
            quick_rise_threshold=3.0,
            price_drop_threshold=-3.0,
        )

        assert should_buy is True
        assert source == "rules_quick_rise"
