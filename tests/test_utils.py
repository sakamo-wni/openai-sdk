"""Tests for utility functions."""

from datetime import datetime, timedelta, timezone

import pytest

from cloudwatch_triage_agent.utils.helpers import (
    format_datetime,
    format_duration,
    parse_datetime,
    truncate_text,
)


class TestParseDatetime:
    """Tests for parse_datetime function."""

    def test_parse_iso_format(self) -> None:
        """Test parsing ISO format datetime."""
        result = parse_datetime("2024-01-15T10:30:00Z")

        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30

    def test_parse_iso_with_timezone(self) -> None:
        """Test parsing ISO format with explicit timezone."""
        result = parse_datetime("2024-01-15T10:30:00+09:00")

        assert result.hour == 10
        assert result.tzinfo is not None

    def test_parse_relative_hours(self) -> None:
        """Test parsing relative time in hours."""
        before = datetime.now(timezone.utc)
        result = parse_datetime("2h ago")
        after = datetime.now(timezone.utc)

        expected = before - timedelta(hours=2)
        assert expected <= result <= after - timedelta(hours=2) + timedelta(seconds=1)

    def test_parse_relative_minutes(self) -> None:
        """Test parsing relative time in minutes."""
        before = datetime.now(timezone.utc)
        result = parse_datetime("30m ago")
        after = datetime.now(timezone.utc)

        expected = before - timedelta(minutes=30)
        assert expected <= result <= after - timedelta(minutes=30) + timedelta(seconds=1)

    def test_parse_relative_days(self) -> None:
        """Test parsing relative time in days."""
        before = datetime.now(timezone.utc)
        result = parse_datetime("1d ago")
        after = datetime.now(timezone.utc)

        expected = before - timedelta(days=1)
        assert expected <= result <= after - timedelta(days=1) + timedelta(seconds=1)

    def test_parse_now(self) -> None:
        """Test parsing 'now'."""
        before = datetime.now(timezone.utc)
        result = parse_datetime("now")
        after = datetime.now(timezone.utc)

        assert before <= result <= after

    def test_parse_simple_date(self) -> None:
        """Test parsing simple date format."""
        result = parse_datetime("2024-01-15")

        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_parse_invalid_format(self) -> None:
        """Test parsing invalid format raises error."""
        with pytest.raises(ValueError):
            parse_datetime("not a date")


class TestFormatDatetime:
    """Tests for format_datetime function."""

    def test_format_with_timezone(self) -> None:
        """Test formatting with timezone."""
        dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = format_datetime(dt, include_timezone=True)

        assert "2024-01-15" in result
        assert "10:30:00" in result
        assert "UTC" in result

    def test_format_without_timezone(self) -> None:
        """Test formatting without timezone."""
        dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = format_datetime(dt, include_timezone=False)

        assert "2024-01-15" in result
        assert "10:30:00" in result
        assert "UTC" not in result


class TestFormatDuration:
    """Tests for format_duration function."""

    def test_format_seconds(self) -> None:
        """Test formatting duration in seconds."""
        assert format_duration(30) == "30.0s"
        assert format_duration(59.5) == "59.5s"

    def test_format_minutes(self) -> None:
        """Test formatting duration in minutes."""
        assert format_duration(60) == "1.0m"
        assert format_duration(150) == "2.5m"

    def test_format_hours(self) -> None:
        """Test formatting duration in hours."""
        assert format_duration(3600) == "1.0h"
        assert format_duration(7200) == "2.0h"

    def test_format_days(self) -> None:
        """Test formatting duration in days."""
        assert format_duration(86400) == "1.0d"
        assert format_duration(172800) == "2.0d"


class TestTruncateText:
    """Tests for truncate_text function."""

    def test_no_truncation_needed(self) -> None:
        """Test text shorter than max length is not truncated."""
        text = "Short text"
        result = truncate_text(text, max_length=100)

        assert result == text

    def test_truncation_with_suffix(self) -> None:
        """Test text is truncated with suffix."""
        text = "This is a very long text that needs to be truncated"
        result = truncate_text(text, max_length=20)

        assert len(result) == 20
        assert result.endswith("...")

    def test_custom_suffix(self) -> None:
        """Test truncation with custom suffix."""
        text = "This is a very long text"
        result = truncate_text(text, max_length=15, suffix=" [...]")

        assert len(result) == 15
        assert result.endswith(" [...]")

    def test_exact_length(self) -> None:
        """Test text exactly at max length is not truncated."""
        text = "Exactly ten!"
        result = truncate_text(text, max_length=12)

        assert result == text
