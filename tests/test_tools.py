"""Tests for tool functions."""

from datetime import datetime, timezone
from unittest import mock

import pytest


class TestCloudWatchTool:
    """Tests for CloudWatch Logs tool."""

    def test_search_logs_invalid_service(self) -> None:
        """Test search with invalid service returns error."""
        from cloudwatch_triage_agent.tools.cloudwatch import search_cloudwatch_logs

        # Mock the config to have no services
        with mock.patch(
            "cloudwatch_triage_agent.tools.cloudwatch.get_config"
        ) as mock_config:
            mock_config.return_value.services.get_log_group.return_value = None
            mock_config.return_value.services.list_services.return_value = ["api-service"]

            # Get the underlying function (unwrap the function_tool decorator)
            func = search_cloudwatch_logs
            if hasattr(func, "__wrapped__"):
                func = func.__wrapped__

            result = func(
                service="unknown-service",
                environment="dev",
                query="fields @timestamp",
                start_time="2024-01-15T10:00:00Z",
                end_time="2024-01-15T11:00:00Z",
            )

        assert result["status"] == "Failed"
        assert "Unknown service" in result.get("error", "")

    def test_search_logs_invalid_time_format(self) -> None:
        """Test search with invalid time format returns error."""
        from cloudwatch_triage_agent.tools.cloudwatch import search_cloudwatch_logs

        with mock.patch(
            "cloudwatch_triage_agent.tools.cloudwatch.get_config"
        ) as mock_config:
            mock_config.return_value.services.get_log_group.return_value = "/test/log/group"

            func = search_cloudwatch_logs
            if hasattr(func, "__wrapped__"):
                func = func.__wrapped__

            result = func(
                service="api-service",
                environment="dev",
                query="fields @timestamp",
                start_time="invalid-time",
                end_time="2024-01-15T11:00:00Z",
            )

        assert result["status"] == "Failed"
        assert "Invalid time format" in result.get("error", "")


class TestGitHubTool:
    """Tests for GitHub Deployments tool."""

    def test_get_deployments_missing_config(self) -> None:
        """Test deployment fetch with missing config returns error."""
        from cloudwatch_triage_agent.tools.github import get_github_deployments

        with mock.patch(
            "cloudwatch_triage_agent.tools.github.get_config"
        ) as mock_config:
            mock_config.return_value.github.owner = ""
            mock_config.return_value.github.repo = ""

            func = get_github_deployments
            if hasattr(func, "__wrapped__"):
                func = func.__wrapped__

            result = func(
                environment="dev",
                start_time="2024-01-15T10:00:00Z",
                end_time="2024-01-15T11:00:00Z",
            )

        assert result["status"] == "failed"
        assert "owner and name must be configured" in result.get("error", "")

    def test_get_deployments_invalid_time_format(self) -> None:
        """Test deployment fetch with invalid time format returns error."""
        from cloudwatch_triage_agent.tools.github import get_github_deployments

        with mock.patch(
            "cloudwatch_triage_agent.tools.github.get_config"
        ) as mock_config:
            mock_config.return_value.github.owner = "test-owner"
            mock_config.return_value.github.repo = "test-repo"

            func = get_github_deployments
            if hasattr(func, "__wrapped__"):
                func = func.__wrapped__

            result = func(
                environment="dev",
                start_time="invalid-time",
                end_time="2024-01-15T11:00:00Z",
            )

        assert result["status"] == "failed"
        assert "Invalid time format" in result.get("error", "")


class TestCloudTrailTool:
    """Tests for CloudTrail tool."""

    def test_get_events_invalid_time_format(self) -> None:
        """Test CloudTrail query with invalid time format returns error."""
        from cloudwatch_triage_agent.tools.cloudtrail import get_cloudtrail_events

        func = get_cloudtrail_events
        if hasattr(func, "__wrapped__"):
            func = func.__wrapped__

        result = func(
            start_time="invalid-time",
            end_time="2024-01-15T11:00:00Z",
        )

        assert result["status"] == "failed"
        assert "Invalid time format" in result.get("error", "")


class TestSlackTool:
    """Tests for Slack notification tool."""

    def test_post_to_slack_missing_channel(self) -> None:
        """Test Slack post with missing channel returns error."""
        from cloudwatch_triage_agent.tools.slack import post_to_slack

        with mock.patch(
            "cloudwatch_triage_agent.tools.slack.get_config"
        ) as mock_config:
            mock_config.return_value.slack.channel_id = ""
            mock_config.return_value.slack.bot_token = "xoxb-test"

            func = post_to_slack
            if hasattr(func, "__wrapped__"):
                func = func.__wrapped__

            result = func(
                title="Test Title",
                body="Test body",
                severity="info",
                cause_candidates=[],
            )

        assert result["status"] == "failed"
        assert "No Slack channel" in result.get("error", "")

    def test_post_to_slack_requires_approval(self) -> None:
        """Test Slack post returns pending status when approval required."""
        from cloudwatch_triage_agent.tools.slack import post_to_slack

        with mock.patch(
            "cloudwatch_triage_agent.tools.slack.get_config"
        ) as mock_config:
            mock_config.return_value.slack.channel_id = "C123"
            mock_config.return_value.slack.bot_token = "xoxb-test"

            func = post_to_slack
            if hasattr(func, "__wrapped__"):
                func = func.__wrapped__

            result = func(
                title="Test Title",
                body="Test body",
                severity="warning",
                cause_candidates=[
                    {
                        "rank": 1,
                        "title": "Test Cause",
                        "description": "Test description",
                        "confidence": "high",
                        "evidence": ["Evidence 1"],
                    }
                ],
                require_approval=True,
            )

        assert result["status"] == "pending_approval"
        assert "message_id" in result
        assert "preview" in result

    def test_approve_nonexistent_message(self) -> None:
        """Test approving non-existent message returns error."""
        from cloudwatch_triage_agent.tools.slack import approve_slack_message

        func = approve_slack_message
        if hasattr(func, "__wrapped__"):
            func = func.__wrapped__

        result = func(message_id="nonexistent-id")

        assert result["status"] == "failed"
        assert "not found" in result.get("error", "")

    def test_get_pending_messages_empty(self) -> None:
        """Test getting pending messages when none exist."""
        from cloudwatch_triage_agent.tools.slack import (
            _pending_messages,
            get_pending_slack_messages,
        )

        # Clear any existing pending messages
        _pending_messages.clear()

        func = get_pending_slack_messages
        if hasattr(func, "__wrapped__"):
            func = func.__wrapped__

        result = func()

        assert result["pending_count"] == 0
        assert result["messages"] == []
