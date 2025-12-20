# test_bot_argparse.py

import argparse

import pytest


class TestCreateArgumentParser:
    """Tests for create_argument_parser"""

    def test_parses_buy_amount_and_coin(self):
        """Parses buy_amount and coin"""
        from bot import create_argument_parser

        parser = create_argument_parser()

        args = parser.parse_args(["100", "WIF"])

        assert args.buy_amount == 100.0
        assert args.coin == "WIF"
        assert args.mode is None

    def test_parses_mode_option(self):
        """Parses --mode option"""
        from bot import create_argument_parser

        parser = create_argument_parser()

        args = parser.parse_args(["100", "WIF", "--mode", "ai"])

        assert args.mode == "ai"

    def test_mode_validates_choices(self):
        """--mode accepts only valid values"""
        from bot import create_argument_parser

        parser = create_argument_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(["100", "WIF", "--mode", "invalid"])

    def test_whitelist_mode_no_coin(self):
        """Whitelist mode without specifying coin"""
        from bot import create_argument_parser

        parser = create_argument_parser()

        args = parser.parse_args(["100"])

        assert args.buy_amount == 100.0
        assert args.coin is None


class TestGetDecisionMode:
    """Tests for get_decision_mode"""

    def test_cli_has_priority_over_env(self, monkeypatch):
        """CLI has priority over .env"""
        monkeypatch.setenv("DECISION_MODE", "combined")

        from bot import get_decision_mode

        args = argparse.Namespace(mode="ai")

        result = get_decision_mode(args)

        assert result == "ai"

    def test_env_used_when_no_cli(self, monkeypatch):
        """.env is used when no CLI argument"""
        monkeypatch.setenv("DECISION_MODE", "combined")

        from bot import get_decision_mode

        args = argparse.Namespace(mode=None)

        result = get_decision_mode(args)

        assert result == "combined"

    def test_default_when_no_cli_and_env(self, monkeypatch):
        """Default value when no CLI and .env"""
        monkeypatch.delenv("DECISION_MODE", raising=False)

        from bot import get_decision_mode

        args = argparse.Namespace(mode=None)

        result = get_decision_mode(args)

        assert result == "rules"


class TestInitAIClient:
    """Tests for init_ai_client"""

    def test_returns_none_for_rules_mode(self):
        """Returns None for rules mode"""
        from bot import init_ai_client

        result = init_ai_client("rules")

        assert result is None

    def test_exits_when_api_key_missing(self, monkeypatch):
        """Exits when API key is missing"""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        from bot import init_ai_client

        with pytest.raises(SystemExit):
            init_ai_client("ai")

    def test_creates_client_with_api_key(self, monkeypatch):
        """Creates client when API key is present"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

        from bot import init_ai_client

        result = init_ai_client("ai")

        assert result is not None
        assert result.api_key == "sk-ant-test"
