"""Configuration management for CloudWatch Triage Agent."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

type Environment = Literal["dev", "prod"]


class AWSSettings(BaseSettings):
    """AWS configuration."""

    model_config = SettingsConfigDict(env_prefix="AWS_")

    region: str = "ap-northeast-1"
    access_key_id: str | None = None
    secret_access_key: str | None = None


class SlackSettings(BaseSettings):
    """Slack configuration."""

    model_config = SettingsConfigDict(env_prefix="SLACK_")

    bot_token: str = ""
    channel_id: str = ""


class GitHubSettings(BaseSettings):
    """GitHub configuration."""

    model_config = SettingsConfigDict(env_prefix="GITHUB_")

    token: str = ""
    owner: str = ""
    repo: str = ""


class ServiceSettings(BaseSettings):
    """Service log group mapping configuration."""

    model_config = SettingsConfigDict(env_prefix="SERVICE_")

    log_groups: dict[str, dict[str, str]] = Field(default_factory=dict)

    @field_validator("log_groups", mode="before")
    @classmethod
    def parse_log_groups(cls, v: Any) -> dict[str, dict[str, str]]:
        """Parse log groups from JSON string if needed."""
        if isinstance(v, str):
            return json.loads(v) if v else {}
        return v or {}

    def get_log_group(self, service: str, env: Environment) -> str | None:
        """Get the log group for a service and environment."""
        service_config = self.log_groups.get(service)
        if service_config:
            return service_config.get(env)
        return None

    def list_services(self) -> list[str]:
        """List all configured services."""
        return list(self.log_groups.keys())


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    default_env: Environment = Field(default="dev", alias="DEFAULT_ENV")

    aws: AWSSettings = Field(default_factory=AWSSettings)
    slack: SlackSettings = Field(default_factory=SlackSettings)
    github: GitHubSettings = Field(default_factory=GitHubSettings)
    services: ServiceSettings = Field(default_factory=ServiceSettings)

    def validate_config(self) -> list[str]:
        """Validate configuration and return list of missing required fields."""
        errors: list[str] = []

        if not self.openai_api_key:
            errors.append("OPENAI_API_KEY is required")

        if not self.slack.bot_token:
            errors.append("SLACK_BOT_TOKEN is required for Slack notifications")

        if not self.slack.channel_id:
            errors.append("SLACK_CHANNEL_ID is required for Slack notifications")

        if not self.github.token:
            errors.append("GITHUB_TOKEN is required for deployment history")

        return errors


@lru_cache
def get_settings() -> Settings:
    """Get the application settings (cached)."""
    return Settings()


# Alias for backward compatibility
def get_config() -> Settings:
    """Get the application configuration.

    Deprecated: Use get_settings() instead.
    """
    return get_settings()
