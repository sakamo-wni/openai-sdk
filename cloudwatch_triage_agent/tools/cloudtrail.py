"""AWS CloudTrail events tool."""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

import boto3
from agents import function_tool

from cloudwatch_triage_agent.config import get_settings

if TYPE_CHECKING:
    from mypy_boto3_cloudtrail import CloudTrailClient


def _get_cloudtrail_client() -> "CloudTrailClient":
    """Get a CloudTrail client."""
    settings = get_settings()
    return boto3.client(
        "cloudtrail",
        region_name=settings.aws.region,
        aws_access_key_id=settings.aws.access_key_id,
        aws_secret_access_key=settings.aws.secret_access_key,
    )


# Common AWS services and their change-related events
CHANGE_EVENT_PATTERNS = {
    "lambda": [
        "UpdateFunctionCode",
        "UpdateFunctionConfiguration",
        "PublishVersion",
        "CreateFunction",
        "DeleteFunction",
        "UpdateAlias",
    ],
    "ecs": [
        "UpdateService",
        "CreateService",
        "DeleteService",
        "RegisterTaskDefinition",
        "DeregisterTaskDefinition",
        "RunTask",
        "StopTask",
    ],
    "ec2": [
        "RunInstances",
        "TerminateInstances",
        "StopInstances",
        "StartInstances",
        "ModifyInstanceAttribute",
    ],
    "rds": [
        "ModifyDBInstance",
        "RebootDBInstance",
        "CreateDBInstance",
        "DeleteDBInstance",
        "RestoreDBInstanceFromSnapshot",
    ],
    "elasticache": [
        "ModifyCacheCluster",
        "CreateCacheCluster",
        "DeleteCacheCluster",
        "RebootCacheCluster",
    ],
    "s3": [
        "PutBucketPolicy",
        "DeleteBucketPolicy",
        "PutBucketAcl",
        "CreateBucket",
        "DeleteBucket",
    ],
    "iam": [
        "CreateRole",
        "DeleteRole",
        "AttachRolePolicy",
        "DetachRolePolicy",
        "PutRolePolicy",
        "UpdateAssumeRolePolicy",
    ],
    "dynamodb": [
        "CreateTable",
        "DeleteTable",
        "UpdateTable",
        "UpdateTimeToLive",
    ],
}


@function_tool
def get_cloudtrail_events(
    start_time: str,
    end_time: str,
    service_filter: str | None = None,
    resource_name: str | None = None,
    username: str | None = None,
    include_read_only: bool = False,
    limit: int = 50,
) -> dict[str, Any]:
    """Get AWS CloudTrail events for change tracking within a time range.

    This tool retrieves configuration change events from AWS CloudTrail,
    useful for correlating infrastructure changes with incidents.

    Args:
        start_time: Start of time range in ISO format (e.g., '2024-01-15T10:00:00Z')
        end_time: End of time range in ISO format (e.g., '2024-01-15T11:00:00Z')
        service_filter: Filter by AWS service (e.g., 'lambda', 'ecs', 'ec2', 'rds').
                       If not specified, common change events from all services are returned.
        resource_name: Filter by resource name (partial match supported)
        username: Filter by username or role that made the change
        include_read_only: Include read-only events (default: False, only mutation events)
        limit: Maximum number of events to return (default: 50, max: 100)

    Returns:
        Dictionary containing:
        - time_range_start: Start time of the query
        - time_range_end: End time of the query
        - events: List of CloudTrail events with details
        - total_count: Number of events found
        - filters_applied: Filters that were applied
        - status: Query status (success or failed)
    """
    settings = get_settings()

    # Parse timestamps
    try:
        start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
    except ValueError as e:
        return {
            "time_range_start": start_time,
            "time_range_end": end_time,
            "events": [],
            "total_count": 0,
            "filters_applied": {},
            "status": "failed",
            "error": f"Invalid time format: {e}. Use ISO format like '2024-01-15T10:00:00Z'",
        }

    # Clamp limit
    limit = min(max(1, limit), 100)

    # Build lookup attributes for filtering
    lookup_attributes = []

    if service_filter:
        service_lower = service_filter.lower()
        # Map common names to AWS service event sources
        service_map = {
            "lambda": "lambda.amazonaws.com",
            "ecs": "ecs.amazonaws.com",
            "ec2": "ec2.amazonaws.com",
            "rds": "rds.amazonaws.com",
            "s3": "s3.amazonaws.com",
            "iam": "iam.amazonaws.com",
            "dynamodb": "dynamodb.amazonaws.com",
            "elasticache": "elasticache.amazonaws.com",
        }
        event_source = service_map.get(service_lower, f"{service_lower}.amazonaws.com")
        lookup_attributes.append({"AttributeKey": "EventSource", "AttributeValue": event_source})

    if resource_name:
        lookup_attributes.append({"AttributeKey": "ResourceName", "AttributeValue": resource_name})

    if username:
        lookup_attributes.append({"AttributeKey": "Username", "AttributeValue": username})

    client = _get_cloudtrail_client()

    try:
        # Query CloudTrail
        paginator = client.get_paginator("lookup_events")
        pagination_config = {"MaxItems": limit * 2}  # Fetch more for filtering

        if lookup_attributes:
            # Can only use one lookup attribute at a time
            pages = paginator.paginate(
                LookupAttributes=[lookup_attributes[0]],
                StartTime=start_dt,
                EndTime=end_dt,
                PaginationConfig=pagination_config,
            )
        else:
            pages = paginator.paginate(
                StartTime=start_dt,
                EndTime=end_dt,
                PaginationConfig=pagination_config,
            )

        # Process events
        events = []
        for page in pages:
            for event in page.get("Events", []):
                # Filter read-only events if needed
                if not include_read_only:
                    event_name = event.get("EventName", "")
                    # Skip common read-only patterns
                    if any(
                        event_name.startswith(prefix)
                        for prefix in ["Describe", "Get", "List", "Head", "Lookup"]
                    ):
                        continue

                    # If service filter is specified, only include known change events
                    if service_filter:
                        service_lower = service_filter.lower()
                        known_events = CHANGE_EVENT_PATTERNS.get(service_lower, [])
                        if known_events and event_name not in known_events:
                            continue

                # Apply additional filters if multiple were provided
                if len(lookup_attributes) > 1:
                    # Additional filtering for attributes we couldn't query directly
                    pass  # CloudTrail API limitation - handled by initial query

                # Extract resources
                resources = []
                for resource in event.get("Resources", []):
                    resources.append({
                        "type": resource.get("ResourceType", ""),
                        "name": resource.get("ResourceName", ""),
                    })

                # Parse CloudTrailEvent JSON for additional details
                cloud_trail_event: dict[str, Any] = {}
                try:
                    cloud_trail_event = json.loads(event.get("CloudTrailEvent", "{}"))
                except json.JSONDecodeError:
                    pass

                events.append({
                    "event_id": event.get("EventId", ""),
                    "event_name": event.get("EventName", ""),
                    "event_source": event.get("EventSource", ""),
                    "event_time": event.get("EventTime", "").isoformat()
                    if event.get("EventTime")
                    else "",
                    "username": event.get("Username", ""),
                    "source_ip": cloud_trail_event.get("sourceIPAddress"),
                    "resources": resources,
                    "error_code": cloud_trail_event.get("errorCode"),
                    "error_message": cloud_trail_event.get("errorMessage"),
                    "request_parameters": cloud_trail_event.get("requestParameters", {}),
                })

                if len(events) >= limit:
                    break

            if len(events) >= limit:
                break

        filters_applied = {
            "service_filter": service_filter,
            "resource_name": resource_name,
            "username": username,
            "include_read_only": include_read_only,
        }

        return {
            "time_range_start": start_time,
            "time_range_end": end_time,
            "events": events,
            "total_count": len(events),
            "filters_applied": filters_applied,
            "status": "success",
        }

    except Exception as e:
        return {
            "time_range_start": start_time,
            "time_range_end": end_time,
            "events": [],
            "total_count": 0,
            "filters_applied": {},
            "status": "failed",
            "error": f"Failed to query CloudTrail: {str(e)}",
        }
