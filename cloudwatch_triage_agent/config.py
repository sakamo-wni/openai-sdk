"""Configuration management for CloudWatch Triage Agent."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Literal

from dotenv import load_dotenv

load_dotenv()

Environment = Literal["dev", "prod"]


@dataclass
class AWSConfig:
    """AWS configuration."""

    region: str = field(default_factory=lambda: os.getenv("AWS_REGION", "ap-northeast-1"))
    access_key_id: str | None = field(default_factory=lambda: os.getenv("AWS_ACCESS_KEY_ID"))
    secret_access_key: str | None = field(
        default_factory=lambda: os.getenv("AWS_SECRET_ACCESS_KEY")
    )


@dataclass
class SlackConfig:
    """Slack configuration."""

    bot_token: str = field(default_factory=lambda: os.getenv("SLACK_BOT_TOKEN", ""))
    channel_id: str = field(default_factory=lambda: os.getenv("SLACK_CHANNEL_ID", ""))


@dataclass
class GitHubConfig:
    """GitHub configuration."""

    token: str = field(default_factory=lambda: os.getenv("GITHUB_TOKEN", ""))
    owner: str = field(default_factory=lambda: os.getenv("GITHUB_OWNER", ""))
    repo: str = field(default_factory=lambda: os.getenv("GITHUB_REPO", ""))


@dataclass
class ServiceConfig:
    """Service log group mapping configuration."""

    log_groups: dict[str, dict[str, str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.log_groups:
            raw = os.getenv("SERVICE_LOG_GROUPS", "{}")
            self.log_groups = json.loads(raw)

    def get_log_group(self, service: str, env: Environment) -> str | None:
        """Get the log group for a service and environment."""
        service_config = self.log_groups.get(service)
        if service_config:
            return service_config.get(env)
        return None

    def list_services(self) -> list[str]:
        """List all configured services."""
        return list(self.log_groups.keys())


@dataclass
class Config:
    """Main configuration container."""

    aws: AWSConfig = field(default_factory=AWSConfig)
    slack: SlackConfig = field(default_factory=SlackConfig)
    github: GitHubConfig = field(default_factory=GitHubConfig)
    services: ServiceConfig = field(default_factory=ServiceConfig)
    default_env: Environment = field(
        default_factory=lambda: os.getenv("DEFAULT_ENV", "dev")  # type: ignore
    )
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))

    def validate(self) -> list[str]:
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


def get_config() -> Config:
    """Get the application configuration."""
    return Config()
