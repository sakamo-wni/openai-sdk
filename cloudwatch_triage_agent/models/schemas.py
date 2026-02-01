"""Pydantic schemas for CloudWatch Triage Agent."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Environment = Literal["dev", "prod"]


class TriageDecision(BaseModel):
    """Decision made by the Triage Agent."""

    service: str = Field(description="Target service name to investigate")
    environment: Environment = Field(description="Target environment (dev or prod)")
    time_range_start: datetime = Field(description="Start of the investigation time range")
    time_range_end: datetime = Field(description="End of the investigation time range")
    initial_query: str = Field(description="Initial CloudWatch Logs Insights query to execute")
    symptoms_summary: str = Field(description="Summary of reported symptoms")
    investigation_focus: list[str] = Field(
        description="Key areas to focus investigation on",
        default_factory=list,
    )


class LogSearchResult(BaseModel):
    """Result from CloudWatch Logs search."""

    query: str = Field(description="The query that was executed")
    log_group: str = Field(description="The log group that was searched")
    time_range_start: datetime = Field(description="Start of search time range")
    time_range_end: datetime = Field(description="End of search time range")
    records: list[dict] = Field(description="Log records returned", default_factory=list)
    statistics: dict = Field(
        description="Query statistics (bytes scanned, records matched, etc.)",
        default_factory=dict,
    )
    status: str = Field(description="Query status (Complete, Failed, etc.)")


class DeploymentInfo(BaseModel):
    """GitHub deployment information."""

    deployment_id: int = Field(description="GitHub deployment ID")
    environment: str = Field(description="Deployment environment")
    ref: str = Field(description="Git ref (branch/tag/sha) that was deployed")
    sha: str = Field(description="Git commit SHA")
    created_at: datetime = Field(description="When the deployment was created")
    updated_at: datetime = Field(description="When the deployment was last updated")
    status: str = Field(description="Deployment status")
    description: str | None = Field(default=None, description="Deployment description")
    creator: str = Field(description="GitHub username of deployer")


class CloudTrailEvent(BaseModel):
    """AWS CloudTrail event information."""

    event_id: str = Field(description="Unique event ID")
    event_name: str = Field(description="AWS API action name")
    event_source: str = Field(description="AWS service that generated the event")
    event_time: datetime = Field(description="When the event occurred")
    username: str = Field(description="User or role that performed the action")
    source_ip: str | None = Field(default=None, description="Source IP address")
    resources: list[dict] = Field(
        description="AWS resources affected",
        default_factory=list,
    )
    error_code: str | None = Field(default=None, description="Error code if action failed")
    error_message: str | None = Field(default=None, description="Error message if action failed")
    request_parameters: dict = Field(
        description="Request parameters",
        default_factory=dict,
    )


class CauseCandidate(BaseModel):
    """A potential root cause candidate."""

    rank: int = Field(description="Rank (1-3, with 1 being most likely)")
    title: str = Field(description="Brief title of the cause")
    description: str = Field(description="Detailed description of the potential cause")
    evidence: list[str] = Field(description="Evidence supporting this cause")
    confidence: Literal["high", "medium", "low"] = Field(
        description="Confidence level in this cause"
    )
    related_changes: list[str] = Field(
        description="Related deployments or changes",
        default_factory=list,
    )


class CauseCandidateResult(BaseModel):
    """Result containing top cause candidates from investigation."""

    service: str = Field(description="Service that was investigated")
    environment: Environment = Field(description="Environment that was investigated")
    time_range_start: datetime = Field(description="Start of investigation period")
    time_range_end: datetime = Field(description="End of investigation period")
    symptoms: str = Field(description="Original symptoms reported")
    candidates: list[CauseCandidate] = Field(
        description="Top 3 cause candidates ranked by likelihood"
    )
    investigation_summary: str = Field(description="Summary of the investigation process")
    logs_analyzed: int = Field(description="Number of log entries analyzed")
    changes_reviewed: int = Field(description="Number of changes/deployments reviewed")


class SlackMessage(BaseModel):
    """Slack message to be posted."""

    channel: str = Field(description="Slack channel ID")
    title: str = Field(description="Message title/header")
    body: str = Field(description="Main message body in Slack markdown format")
    severity: Literal["critical", "warning", "info"] = Field(
        description="Severity level for color coding"
    )
    cause_candidates: list[CauseCandidate] = Field(
        description="Cause candidates to include in message"
    )
    investigation_link: str | None = Field(
        default=None,
        description="Link to detailed investigation (CloudWatch console, etc.)",
    )


class InvestigationContext(BaseModel):
    """Context passed between agents during investigation."""

    triage_decision: TriageDecision = Field(description="Initial triage decision")
    log_results: list[LogSearchResult] = Field(
        description="Log search results collected",
        default_factory=list,
    )
    deployments: list[DeploymentInfo] = Field(
        description="Recent deployments found",
        default_factory=list,
    )
    cloudtrail_events: list[CloudTrailEvent] = Field(
        description="Relevant CloudTrail events",
        default_factory=list,
    )
    cause_candidates: CauseCandidateResult | None = Field(
        default=None,
        description="Generated cause candidates",
    )
    slack_message: SlackMessage | None = Field(
        default=None,
        description="Prepared Slack message",
    )
    approved_for_slack: bool = Field(
        default=False,
        description="Whether Slack posting has been approved",
    )
