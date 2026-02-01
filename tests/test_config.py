"""Tests for configuration module."""

import os
from unittest import mock

import pytest

from cloudwatch_triage_agent.config import (
    ServiceSettings,
    Settings,
    get_config,
    get_settings,
)


class TestServiceSettings:
    """Tests for ServiceSettings class."""

    def test_get_log_group_existing(self) -> None:
        """Test getting log group for existing service."""
        settings = ServiceSettings(
            log_groups={
                "api-service": {"dev": "/aws/lambda/api-dev", "prod": "/aws/lambda/api-prod"}
            }
        )

        assert settings.get_log_group("api-service", "dev") == "/aws/lambda/api-dev"
        assert settings.get_log_group("api-service", "prod") == "/aws/lambda/api-prod"

    def test_get_log_group_nonexistent(self) -> None:
        """Test getting log group for non-existent service."""
        settings = ServiceSettings(log_groups={})

        assert settings.get_log_group("unknown-service", "dev") is None

    def test_list_services(self) -> None:
        """Test listing available services."""
        settings = ServiceSettings(
            log_groups={
                "api-service": {"dev": "/aws/lambda/api-dev"},
                "web-app": {"dev": "/aws/ecs/web-dev"},
            }
        )

        services = settings.list_services()
        assert "api-service" in services
        assert "web-app" in services

    def test_parse_json_string(self) -> None:
        """Test parsing JSON string for log groups."""
        json_str = '{"test-svc": {"dev": "/test/dev", "prod": "/test/prod"}}'
        settings = ServiceSettings(log_groups=json_str)  # type: ignore

        assert settings.get_log_group("test-svc", "dev") == "/test/dev"


class TestSettings:
    """Tests for Settings class."""

    def test_validate_missing_openai_key(self) -> None:
        """Test validation catches missing OpenAI API key."""
        settings = Settings(openai_api_key="")
        errors = settings.validate_config()

        assert any("OPENAI_API_KEY" in e for e in errors)

    def test_validate_missing_slack_config(self) -> None:
        """Test validation catches missing Slack configuration."""
        settings = Settings(openai_api_key="test-key")
        errors = settings.validate_config()

        assert any("SLACK_BOT_TOKEN" in e for e in errors)
        assert any("SLACK_CHANNEL_ID" in e for e in errors)

    def test_validate_all_configured(self) -> None:
        """Test validation passes with all required config."""
        with mock.patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-key",
                "SLACK_BOT_TOKEN": "xoxb-test",
                "SLACK_CHANNEL_ID": "C123",
                "GITHUB_TOKEN": "ghp_test",
            },
        ):
            settings = Settings()
            errors = settings.validate_config()

        assert len(errors) == 0


class TestGetSettings:
    """Tests for get_settings and get_config functions."""

    def test_returns_settings_instance(self) -> None:
        """Test that get_settings returns a Settings instance."""
        # Clear cache to get fresh instance
        get_settings.cache_clear()
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_get_config_backward_compatibility(self) -> None:
        """Test that get_config returns a Settings instance (backward compat)."""
        settings = get_config()
        assert isinstance(settings, Settings)
