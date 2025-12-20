# test_ai_config.py

from ai_config import (
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT,
    format_user_prompt,
    get_ai_config,
    validate_ai_config,
)


class TestGetAIConfig:
    """Tests for get_ai_config function"""

    def test_returns_defaults_when_no_env_vars(self, monkeypatch):
        """Returns default values when no environment variables"""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("AI_MODEL", raising=False)
        monkeypatch.delenv("AI_TIMEOUT", raising=False)

        config = get_ai_config()

        assert config["api_key"] is None
        assert config["model"] == DEFAULT_MODEL
        assert config["timeout"] == DEFAULT_TIMEOUT

    def test_reads_env_vars(self, monkeypatch):
        """Reads values from environment variables"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("AI_MODEL", "claude-3-opus")
        monkeypatch.setenv("AI_TIMEOUT", "60")

        config = get_ai_config()

        assert config["api_key"] == "sk-ant-test"
        assert config["model"] == "claude-3-opus"
        assert config["timeout"] == 60


class TestValidateAIConfig:
    """Tests for validate_ai_config function"""

    def test_rules_mode_always_valid(self):
        """Rules mode is always valid"""
        result = validate_ai_config("rules")
        assert result is None

    def test_ai_mode_requires_api_key(self, monkeypatch):
        """AI mode requires API key"""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        result = validate_ai_config("ai")

        assert result is not None
        assert "ANTHROPIC_API_KEY" in result

    def test_combined_mode_requires_api_key(self, monkeypatch):
        """Combined mode requires API key"""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        result = validate_ai_config("combined")

        assert result is not None
        assert "ANTHROPIC_API_KEY" in result

    def test_ai_mode_valid_with_api_key(self, monkeypatch):
        """AI mode is valid with API key"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

        result = validate_ai_config("ai")

        assert result is None

    def test_invalid_mode_returns_error(self):
        """Invalid mode returns error"""
        result = validate_ai_config("invalid_mode")

        assert result is not None
        assert "Invalid mode" in result


class TestFormatUserPrompt:
    """Tests for format_user_prompt function"""

    def test_formats_prompt_correctly(self):
        """Correctly formats the prompt"""
        prompt = format_user_prompt(
            symbol="BTCUSDT", current_price=50000.0, change_1h=2.5, change_3h=-1.2
        )

        assert "BTCUSDT" in prompt
        assert "50000.0" in prompt
        assert "+2.50%" in prompt
        assert "-1.20%" in prompt

    def test_handles_negative_changes(self):
        """Correctly handles negative changes"""
        prompt = format_user_prompt(
            symbol="ETHUSDT", current_price=3000.0, change_1h=-5.0, change_3h=-10.0
        )

        assert "-5.00%" in prompt
        assert "-10.00%" in prompt
