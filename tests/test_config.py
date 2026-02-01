"""Tests for configuration module."""

import os
from unittest import mock

import pytest

from cloudwatch_triage_agent.config import Config, ServiceConfig, get_config


class TestServiceConfig:
    """Tests for ServiceConfig class."""

    def test_get_log_group_existing(self) -> None:
        """Test getting log group for existing service."""
        config = ServiceConfig(
            log_groups={
                "api-service": {"dev": "/aws/lambda/api-dev", "prod": "/aws/lambda/api-prod"}
            }
        )

        assert config.get_log_group("api-service", "dev") == "/aws/lambda/api-dev"
        assert config.get_log_group("api-service", "prod") == "/aws/lambda/api-prod"

    def test_get_log_group_nonexistent(self) -> None:
        """Test getting log group for non-existent service."""
        config = ServiceConfig(log_groups={})

        assert config.get_log_group("unknown-service", "dev") is None

    def test_list_services(self) -> None:
        """Test listing available services."""
        config = ServiceConfig(
            log_groups={
                "api-service": {"dev": "/aws/lambda/api-dev"},
                "web-app": {"dev": "/aws/ecs/web-dev"},
            }
        )

        services = config.list_services()
        assert "api-service" in services
        assert "web-app" in services

    def test_load_from_env(self) -> None:
        """Test loading service config from environment variable."""
        env_value = '{"test-svc": {"dev": "/test/dev", "prod": "/test/prod"}}'

        with mock.patch.dict(os.environ, {"SERVICE_LOG_GROUPS": env_value}):
            config = ServiceConfig()

        assert config.get_log_group("test-svc", "dev") == "/test/dev"


class TestConfig:
    """Tests for Config class."""

    def test_validate_missing_openai_key(self) -> None:
        """Test validation catches missing OpenAI API key."""
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
            config = Config(openai_api_key="")
            errors = config.validate()

        assert any("OPENAI_API_KEY" in e for e in errors)

    def test_validate_missing_slack_config(self) -> None:
        """Test validation catches missing Slack configuration."""
        config = Config(openai_api_key="test-key")
        config.slack.bot_token = ""
        config.slack.channel_id = ""

        errors = config.validate()

        assert any("SLACK_BOT_TOKEN" in e for e in errors)
        assert any("SLACK_CHANNEL_ID" in e for e in errors)

    def test_validate_all_configured(self) -> None:
        """Test validation passes with all required config."""
        config = Config(openai_api_key="test-key")
        config.slack.bot_token = "xoxb-test"
        config.slack.channel_id = "C123"
        config.github.token = "ghp_test"

        errors = config.validate()

        assert len(errors) == 0


class TestGetConfig:
    """Tests for get_config function."""

    def test_returns_config_instance(self) -> None:
        """Test that get_config returns a Config instance."""
        config = get_config()
        assert isinstance(config, Config)
