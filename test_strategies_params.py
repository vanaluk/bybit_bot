# test_strategies_params.py

from strategies import evaluate_entry


class TestEvaluateEntry:
    """Tests for evaluate_entry function"""

    def test_rules_mode_quick_rise(self):
        """Rules mode: quick rise triggers"""
        should_buy, source = evaluate_entry(
            decision_mode="rules",
            ai_client=None,
            symbol="BTCUSDT",
            current_price=50000.0,
            quick_price_change=3.5,  # >= 3.0
            price_change=1.0,
            quick_rise_threshold=3.0,
            price_drop_threshold=-3.0,
        )

        assert should_buy is True
        assert source == "rules_quick_rise"

    def test_rules_mode_price_drop(self):
        """Rules mode: price drop triggers"""
        should_buy, source = evaluate_entry(
            decision_mode="rules",
            ai_client=None,
            symbol="BTCUSDT",
            current_price=50000.0,
            quick_price_change=1.0,
            price_change=-3.5,  # <= -3.0
            quick_rise_threshold=3.0,
            price_drop_threshold=-3.0,
        )

        assert should_buy is True
        assert source == "rules_price_drop"

    def test_rules_mode_no_signal(self):
        """Rules mode: no signal"""
        should_buy, source = evaluate_entry(
            decision_mode="rules",
            ai_client=None,
            symbol="BTCUSDT",
            current_price=50000.0,
            quick_price_change=1.0,  # < 3.0
            price_change=-1.0,  # > -3.0
            quick_rise_threshold=3.0,
            price_drop_threshold=-3.0,
        )

        assert should_buy is False
        assert source == "hold"

    def test_ai_mode_stub_uses_rules(self):
        """Stub: ai mode uses rules"""
        should_buy, source = evaluate_entry(
            decision_mode="ai",
            ai_client=None,
            symbol="BTCUSDT",
            current_price=50000.0,
            quick_price_change=3.5,
            price_change=1.0,
            quick_rise_threshold=3.0,
            price_drop_threshold=-3.0,
        )

        assert should_buy is True
        assert "ai_unavailable" in source

    def test_combined_mode_stub_uses_rules(self):
        """Stub: combined mode uses rules"""
        should_buy, source = evaluate_entry(
            decision_mode="combined",
            ai_client=None,
            symbol="BTCUSDT",
            current_price=50000.0,
            quick_price_change=3.5,
            price_change=1.0,
            quick_rise_threshold=3.0,
            price_drop_threshold=-3.0,
        )

        assert should_buy is True
        assert "ai_unavailable" in source

    def test_unknown_mode_returns_hold(self):
        """Unknown mode falls back to rules"""
        should_buy, source = evaluate_entry(
            decision_mode="unknown",
            ai_client=None,
            symbol="BTCUSDT",
            current_price=50000.0,
            quick_price_change=5.0,
            price_change=-5.0,
            quick_rise_threshold=3.0,
            price_drop_threshold=-3.0,
        )

        # For unknown mode, function falls back to rules
        # and returns True if rules triggered
        assert should_buy is True
        assert source == "rules"


class TestStrategySignatures:
    """Tests for strategy function signatures"""

    def test_run_trailing_stop_strategy_accepts_new_params(self):
        """run_trailing_stop_strategy accepts new parameters"""
        import inspect

        from strategies import run_trailing_stop_strategy

        sig = inspect.signature(run_trailing_stop_strategy)
        params = sig.parameters

        assert "decision_mode" in params
        assert "ai_client" in params
        assert params["decision_mode"].default == "rules"
        assert params["ai_client"].default is None

    def test_run_trailing_stop_strategy_whitelist_accepts_new_params(self):
        """run_trailing_stop_strategy_whitelist accepts new parameters"""
        import inspect

        from strategies import run_trailing_stop_strategy_whitelist

        sig = inspect.signature(run_trailing_stop_strategy_whitelist)
        params = sig.parameters

        assert "decision_mode" in params
        assert "ai_client" in params
        assert params["decision_mode"].default == "rules"
        assert params["ai_client"].default is None
