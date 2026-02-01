"""CloudWatch Logs search tool."""

from __future__ import annotations

import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

import boto3
from agents import function_tool

from cloudwatch_triage_agent.config import get_settings

if TYPE_CHECKING:
    from mypy_boto3_logs import CloudWatchLogsClient


def _get_logs_client() -> "CloudWatchLogsClient":
    """Get a CloudWatch Logs client."""
    settings = get_settings()
    return boto3.client(
        "logs",
        region_name=settings.aws.region,
        aws_access_key_id=settings.aws.access_key_id,
        aws_secret_access_key=settings.aws.secret_access_key,
    )


@function_tool
def search_cloudwatch_logs(
    service: str,
    environment: str,
    query: str,
    start_time: str,
    end_time: str,
    limit: int = 100,
) -> dict[str, Any]:
    """Search CloudWatch Logs using Logs Insights query.

    Args:
        service: Service name to search logs for (e.g., 'api-service', 'web-app')
        environment: Target environment ('dev' or 'prod')
        query: CloudWatch Logs Insights query string.
               Example: "fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc"
        start_time: Start of time range in ISO format (e.g., '2024-01-15T10:00:00Z')
        end_time: End of time range in ISO format (e.g., '2024-01-15T11:00:00Z')
        limit: Maximum number of log entries to return (default: 100, max: 1000)

    Returns:
        Dictionary containing:
        - query: The query that was executed
        - log_group: The log group that was searched
        - time_range_start: Start time of the search
        - time_range_end: End time of the search
        - records: List of log records matching the query
        - statistics: Query statistics (bytes scanned, records matched, etc.)
        - status: Query status (Complete, Failed, Cancelled, etc.)
    """
    settings = get_settings()
    log_group = settings.services.get_log_group(service, environment)  # type: ignore

    if not log_group:
        available_services = settings.services.list_services()
        return {
            "query": query,
            "log_group": "",
            "time_range_start": start_time,
            "time_range_end": end_time,
            "records": [],
            "statistics": {},
            "status": "Failed",
            "error": f"Unknown service '{service}' or environment '{environment}'. "
            f"Available services: {available_services}",
        }

    # Parse timestamps
    try:
        start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
    except ValueError as e:
        return {
            "query": query,
            "log_group": log_group,
            "time_range_start": start_time,
            "time_range_end": end_time,
            "records": [],
            "statistics": {},
            "status": "Failed",
            "error": f"Invalid time format: {e}. Use ISO format like '2024-01-15T10:00:00Z'",
        }

    # Clamp limit
    limit = min(max(1, limit), 1000)

    client = _get_logs_client()

    try:
        # Start the query
        response = client.start_query(
            logGroupName=log_group,
            startTime=int(start_dt.timestamp()),
            endTime=int(end_dt.timestamp()),
            queryString=query,
            limit=limit,
        )
        query_id = response["queryId"]

        # Poll for results (with timeout)
        max_wait = 60  # seconds
        poll_interval = 1  # second
        elapsed = 0

        while elapsed < max_wait:
            result = client.get_query_results(queryId=query_id)
            status = result["status"]

            if status in ("Complete", "Failed", "Cancelled", "Timeout"):
                break

            time.sleep(poll_interval)
            elapsed += poll_interval

        # Process results
        records = []
        for row in result.get("results", []):
            record = {}
            for field in row:
                record[field["field"]] = field["value"]
            records.append(record)

        return {
            "query": query,
            "log_group": log_group,
            "time_range_start": start_time,
            "time_range_end": end_time,
            "records": records,
            "statistics": result.get("statistics", {}),
            "status": status,
        }

    except client.exceptions.ResourceNotFoundException:
        return {
            "query": query,
            "log_group": log_group,
            "time_range_start": start_time,
            "time_range_end": end_time,
            "records": [],
            "statistics": {},
            "status": "Failed",
            "error": f"Log group '{log_group}' not found",
        }
    except Exception as e:
        return {
            "query": query,
            "log_group": log_group,
            "time_range_start": start_time,
            "time_range_end": end_time,
            "records": [],
            "statistics": {},
            "status": "Failed",
            "error": f"Query failed: {str(e)}",
        }
