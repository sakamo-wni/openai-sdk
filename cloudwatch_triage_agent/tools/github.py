"""GitHub Deployments API tool."""

from __future__ import annotations

from datetime import datetime

import httpx
from agents import function_tool

from cloudwatch_triage_agent.config import get_config

GITHUB_API_BASE = "https://api.github.com"


def _get_github_headers() -> dict[str, str]:
    """Get headers for GitHub API requests."""
    config = get_config()
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {config.github.token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


@function_tool
def get_github_deployments(
    environment: str,
    start_time: str,
    end_time: str,
    repo_owner: str | None = None,
    repo_name: str | None = None,
    limit: int = 20,
) -> dict:
    """Get GitHub deployments for a specific environment within a time range.

    Args:
        environment: Target environment ('dev' or 'prod')
        start_time: Start of time range in ISO format (e.g., '2024-01-15T10:00:00Z')
        end_time: End of time range in ISO format (e.g., '2024-01-15T11:00:00Z')
        repo_owner: GitHub repository owner (optional, uses config default)
        repo_name: GitHub repository name (optional, uses config default)
        limit: Maximum number of deployments to return (default: 20, max: 100)

    Returns:
        Dictionary containing:
        - environment: The environment that was queried
        - time_range_start: Start time of the query
        - time_range_end: End time of the query
        - deployments: List of deployment information
        - total_count: Number of deployments found
        - status: Query status (success or failed)
    """
    config = get_config()
    owner = repo_owner or config.github.owner
    repo = repo_name or config.github.repo

    if not owner or not repo:
        return {
            "environment": environment,
            "time_range_start": start_time,
            "time_range_end": end_time,
            "deployments": [],
            "total_count": 0,
            "status": "failed",
            "error": "Repository owner and name must be configured or provided",
        }

    # Parse timestamps
    try:
        start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
    except ValueError as e:
        return {
            "environment": environment,
            "time_range_start": start_time,
            "time_range_end": end_time,
            "deployments": [],
            "total_count": 0,
            "status": "failed",
            "error": f"Invalid time format: {e}. Use ISO format like '2024-01-15T10:00:00Z'",
        }

    # Clamp limit
    limit = min(max(1, limit), 100)

    try:
        # Fetch deployments for the environment
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/deployments"
        params = {
            "environment": environment,
            "per_page": limit,
        }

        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, headers=_get_github_headers(), params=params)
            response.raise_for_status()
            deployments_data = response.json()

        # Filter by time range and fetch statuses
        deployments = []
        for dep in deployments_data:
            created_at = datetime.fromisoformat(dep["created_at"].replace("Z", "+00:00"))

            # Check if deployment is within time range
            if created_at < start_dt or created_at > end_dt:
                continue

            # Fetch deployment status
            status = "unknown"
            with httpx.Client(timeout=30.0) as client:
                status_url = dep["statuses_url"]
                status_response = client.get(status_url, headers=_get_github_headers())
                if status_response.status_code == 200:
                    statuses = status_response.json()
                    if statuses:
                        status = statuses[0].get("state", "unknown")

            deployments.append({
                "deployment_id": dep["id"],
                "environment": dep["environment"],
                "ref": dep["ref"],
                "sha": dep["sha"],
                "created_at": dep["created_at"],
                "updated_at": dep["updated_at"],
                "status": status,
                "description": dep.get("description"),
                "creator": dep["creator"]["login"] if dep.get("creator") else "unknown",
            })

        return {
            "environment": environment,
            "time_range_start": start_time,
            "time_range_end": end_time,
            "deployments": deployments,
            "total_count": len(deployments),
            "status": "success",
        }

    except httpx.HTTPStatusError as e:
        error_msg = f"GitHub API error: {e.response.status_code}"
        if e.response.status_code == 401:
            error_msg = "GitHub authentication failed. Check your GITHUB_TOKEN."
        elif e.response.status_code == 404:
            error_msg = f"Repository '{owner}/{repo}' not found or no access."
        return {
            "environment": environment,
            "time_range_start": start_time,
            "time_range_end": end_time,
            "deployments": [],
            "total_count": 0,
            "status": "failed",
            "error": error_msg,
        }
    except Exception as e:
        return {
            "environment": environment,
            "time_range_start": start_time,
            "time_range_end": end_time,
            "deployments": [],
            "total_count": 0,
            "status": "failed",
            "error": f"Failed to fetch deployments: {str(e)}",
        }
