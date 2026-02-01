"""Main entry point for CloudWatch Triage Agent."""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone

from agents import Runner

from cloudwatch_triage_agent.agents import create_investigator_agent, create_triage_agent
from cloudwatch_triage_agent.config import get_config
from cloudwatch_triage_agent.models.schemas import TriageDecision


def print_banner() -> None:
    """Print the application banner."""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║           CloudWatch Log Triage Agent                       ║
║           AI-powered incident investigation                 ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)


def validate_config() -> bool:
    """Validate configuration and print warnings."""
    config = get_config()
    errors = config.validate()

    if errors:
        print("\n⚠️  Configuration warnings:")
        for error in errors:
            print(f"   - {error}")
        print()
        return False
    return True


async def run_triage(symptoms: str) -> TriageDecision:
    """Run the Triage Agent to analyze symptoms.

    Args:
        symptoms: User-reported incident symptoms

    Returns:
        TriageDecision with investigation parameters
    """
    print("\n🔍 Running Triage Agent...")
    print(f"   Analyzing symptoms: {symptoms[:100]}...")

    triage_agent = create_triage_agent()
    result = await Runner.run(triage_agent, symptoms)

    if not isinstance(result.final_output, TriageDecision):
        raise ValueError("Triage Agent did not return a valid TriageDecision")

    decision = result.final_output

    print("\n📋 Triage Decision:")
    print(f"   Service: {decision.service}")
    print(f"   Environment: {decision.environment}")
    print(f"   Time Range: {decision.time_range_start} to {decision.time_range_end}")
    print(f"   Focus Areas: {', '.join(decision.investigation_focus)}")

    return decision


async def run_investigation(triage_decision: TriageDecision) -> dict:
    """Run the Investigator Agent to perform deep analysis.

    Args:
        triage_decision: Decision from the Triage Agent

    Returns:
        Investigation results including cause candidates
    """
    print("\n🔬 Running Investigator Agent...")

    investigator_agent = create_investigator_agent()

    # Build context prompt from triage decision
    context = f"""
## Investigation Context

Based on the triage analysis, please investigate the following incident:

**Service:** {triage_decision.service}
**Environment:** {triage_decision.environment}
**Time Range:** {triage_decision.time_range_start.isoformat()} to {triage_decision.time_range_end.isoformat()}

**Reported Symptoms:**
{triage_decision.symptoms_summary}

**Investigation Focus Areas:**
{chr(10).join(f"- {focus}" for focus in triage_decision.investigation_focus)}

**Initial Query Strategy:**
```
{triage_decision.initial_query}
```

Please perform a systematic investigation:
1. Start with the initial query to understand error patterns
2. Deep dive into specific errors found
3. Check for recent deployments and infrastructure changes
4. Correlate changes with incident timing
5. Generate TOP 3 cause candidates with evidence
6. Prepare a Slack notification (require approval)
"""

    result = await Runner.run(investigator_agent, context)

    return {
        "cause_candidates": result.final_output,
        "triage_decision": triage_decision,
    }


async def interactive_session() -> None:
    """Run an interactive triage session."""
    print_banner()

    if not validate_config():
        print("⚠️  Some features may not work without proper configuration.")
        print("   See .env.example for required environment variables.\n")

    print("Enter incident symptoms or 'quit' to exit.")
    print("Example: 'API returning 500 errors for the last 30 minutes'\n")

    while True:
        try:
            symptoms = input("🚨 Describe the incident: ").strip()

            if symptoms.lower() in ("quit", "exit", "q"):
                print("\nGoodbye! 👋")
                break

            if not symptoms:
                print("Please enter a description of the incident.\n")
                continue

            # Phase 1: Triage
            triage_decision = await run_triage(symptoms)

            # Confirm with user before proceeding
            proceed = input("\n❓ Proceed with investigation? (y/n): ").strip().lower()
            if proceed != "y":
                print("Investigation cancelled.\n")
                continue

            # Phase 2: Investigation
            results = await run_investigation(triage_decision)

            # Display results
            print("\n" + "=" * 60)
            print("📊 INVESTIGATION RESULTS")
            print("=" * 60)

            cause_result = results["cause_candidates"]
            if cause_result:
                print(f"\n📝 Investigation Summary:")
                print(f"   {cause_result.investigation_summary}")
                print(f"   Logs analyzed: {cause_result.logs_analyzed}")
                print(f"   Changes reviewed: {cause_result.changes_reviewed}")

                print("\n🎯 Root Cause Candidates:")
                for candidate in cause_result.candidates:
                    confidence_emoji = {
                        "high": "🔴",
                        "medium": "🟡",
                        "low": "🟢",
                    }.get(candidate.confidence, "⚪")

                    print(f"\n   #{candidate.rank} {candidate.title} {confidence_emoji}")
                    print(f"      Confidence: {candidate.confidence}")
                    print(f"      {candidate.description}")
                    if candidate.evidence:
                        print("      Evidence:")
                        for evidence in candidate.evidence[:3]:
                            print(f"        - {evidence}")
                    if candidate.related_changes:
                        print("      Related Changes:")
                        for change in candidate.related_changes:
                            print(f"        - {change}")

            # Check for pending Slack messages
            from cloudwatch_triage_agent.tools.slack import get_pending_slack_messages

            pending = get_pending_slack_messages()
            if pending["pending_count"] > 0:
                print(f"\n📨 {pending['pending_count']} Slack message(s) pending approval.")
                for msg in pending["messages"]:
                    approve = input(
                        f"   Approve message {msg['message_id']} to {msg['channel']}? (y/n): "
                    ).strip().lower()
                    if approve == "y":
                        from cloudwatch_triage_agent.tools.slack import approve_slack_message

                        result = approve_slack_message(msg["message_id"])
                        if result["status"] == "sent":
                            print(f"   ✅ Message sent to {result['channel']}")
                        else:
                            print(f"   ❌ Failed: {result.get('error', 'Unknown error')}")

            print("\n" + "=" * 60 + "\n")

        except KeyboardInterrupt:
            print("\n\nInterrupted. Goodbye! 👋")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("Please try again.\n")


async def single_investigation(symptoms: str, auto_approve_slack: bool = False) -> dict:
    """Run a single investigation programmatically.

    Args:
        symptoms: Incident symptoms description
        auto_approve_slack: If True, automatically approve Slack messages

    Returns:
        Investigation results
    """
    # Phase 1: Triage
    triage_decision = await run_triage(symptoms)

    # Phase 2: Investigation
    results = await run_investigation(triage_decision)

    # Handle Slack approval
    if auto_approve_slack:
        from cloudwatch_triage_agent.tools.slack import (
            approve_slack_message,
            get_pending_slack_messages,
        )

        pending = get_pending_slack_messages()
        for msg in pending["messages"]:
            approve_slack_message(msg["message_id"])

    return results


def main() -> None:
    """Main entry point."""
    if len(sys.argv) > 1:
        # Run with provided symptoms
        symptoms = " ".join(sys.argv[1:])
        results = asyncio.run(single_investigation(symptoms))
        print(f"\nResults: {results}")
    else:
        # Interactive mode
        asyncio.run(interactive_session())


if __name__ == "__main__":
    main()
