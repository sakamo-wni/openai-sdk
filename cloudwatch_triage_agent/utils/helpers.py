"""Helper utilities for CloudWatch Triage Agent."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def parse_datetime(value: str) -> datetime:
    """Parse a datetime string in various formats.

    Args:
        value: Datetime string (ISO format, or relative like '1h ago', '30m ago')

    Returns:
        Parsed datetime in UTC

    Raises:
        ValueError: If the format is not recognized
    """
    # Handle relative time formats
    value_lower = value.lower().strip()

    if value_lower.endswith(" ago"):
        relative_part = value_lower[:-4].strip()

        # Parse relative time
        if relative_part.endswith("h"):
            hours = int(relative_part[:-1])
            return datetime.now(timezone.utc) - timedelta(hours=hours)
        elif relative_part.endswith("m"):
            minutes = int(relative_part[:-1])
            return datetime.now(timezone.utc) - timedelta(minutes=minutes)
        elif relative_part.endswith("d"):
            days = int(relative_part[:-1])
            return datetime.now(timezone.utc) - timedelta(days=days)
        else:
            raise ValueError(f"Unknown relative time format: {value}")

    # Handle "now"
    if value_lower == "now":
        return datetime.now(timezone.utc)

    # Handle ISO format
    try:
        # Replace Z with +00:00 for proper parsing
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        pass

    # Try common formats
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y/%m/%d",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    raise ValueError(f"Unable to parse datetime: {value}")


def format_datetime(dt: datetime, include_timezone: bool = True) -> str:
    """Format a datetime for display.

    Args:
        dt: Datetime to format
        include_timezone: Whether to include timezone suffix

    Returns:
        Formatted datetime string
    """
    if include_timezone:
        return dt.strftime("%Y-%m-%d %H:%M:%S %Z")
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_duration(seconds: float) -> str:
    """Format a duration in seconds to human-readable format.

    Args:
        seconds: Duration in seconds

    Returns:
        Human-readable duration string
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    elif seconds < 86400:
        hours = seconds / 3600
        return f"{hours:.1f}h"
    else:
        days = seconds / 86400
        return f"{days:.1f}d"


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to a maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length including suffix
        suffix: Suffix to add when truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix
