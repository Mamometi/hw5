"""Run the Campus Customs desk: the Boss works through the open tickets.

    cd backend
    ../.venv/bin/python desk.py                      # all open tickets
    ../.venv/bin/python desk.py --ticket 102         # just one ticket
    ../.venv/bin/python desk.py --message "..."      # a custom instruction for the Boss

Every step is appended to output/audit_trail.json. The final DeskRunResult is
printed as JSON.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Callable

from pydantic_ai.exceptions import UsageLimitExceeded

from agents import RunState, TeamBudgetExceeded, clip, run_agent
from audit import AuditTrail
from config import (
    AUDIT_PATH,
    BOSS_LIMITS,
    MAX_DELEGATION_DEPTH,
    MAX_DELEGATIONS_PER_RUN,
    MODEL_NAME,
    SPECIALIST_LIMITS,
    TEAM_TOKEN_BUDGET,
)
from mcp_client import build_mcp_toolset
from models import DeskRunResult

DEFAULT_MESSAGE = "Work through every open ticket at the Campus Customs desk."


def _reconcile_handled_by(report, run: RunState) -> None:
    """Replace the Boss's `handled_by` with who actually worked each ticket.

    The model writes `handled_by` itself and can name agents that never ran.
    The delegation record is the truth: the lead (the Boss's first assignment
    for the ticket), then every colleague brought in, in order. Any correction
    is logged.
    """
    for t in report.tickets:
        actual: list[str] = []
        for d in run.delegations:
            if d.ticket_id == t.ticket_id and d.to_agent not in actual:
                actual.append(d.to_agent)
        if actual != list(t.handled_by):
            run.audit.log(
                "decision", agent=None, ticket_id=t.ticket_id,
                correction="handled_by", claimed_by_boss=list(t.handled_by), from_delegation_record=actual,
            )
            t.handled_by = actual


def _limits_summary() -> dict:
    def lim(u):
        return {
            "request_limit": u.request_limit,
            "tool_calls_limit": u.tool_calls_limit,
            "total_tokens_limit": u.total_tokens_limit,
        }

    return {
        "boss": lim(BOSS_LIMITS),
        "specialist": lim(SPECIALIST_LIMITS),
        "max_delegation_depth": MAX_DELEGATION_DEPTH,
        "max_delegations_per_run": MAX_DELEGATIONS_PER_RUN,
        "team_token_budget": TEAM_TOKEN_BUDGET,
    }


async def run_desk(
    message: str = DEFAULT_MESSAGE,
    ticket_ids: list[int] | None = None,
    on_event: Callable[[dict], None] | None = None,
) -> DeskRunResult:
    """Run the Boss on the given tickets. `on_event` gets every audit event live."""
    audit = AuditTrail(AUDIT_PATH, listeners=[on_event] if on_event else None)
    run = RunState(audit=audit, toolset=build_mcp_toolset())
    prompt = message
    if ticket_ids:
        prompt += f"\nOnly handle these tickets: {', '.join(map(str, ticket_ids))}."

    audit.log(
        "run_start", agent=None, message=message, ticket_ids=ticket_ids,
        model=MODEL_NAME, limits=_limits_summary(),
    )
    report, error = None, None
    try:
        async with run.toolset:  # one MCP server process for the whole run
            report = await run_agent("boss", prompt, run, chain=("boss",))
        _reconcile_handled_by(report, run)
    except TeamBudgetExceeded as exc:
        error = str(exc)
        audit.log("limit_reached", agent=None, limit="team_token_budget", reason=error)
    except UsageLimitExceeded as exc:
        error = f"Boss hit its usage limit: {exc}"
        audit.log("limit_reached", agent="boss", chain=["boss"], limit="agent_usage", reason=str(exc))
    except Exception as exc:
        error = clip(exc, 1000)
        audit.log("error", agent=None, error=error)

    result = DeskRunResult(
        run_id=audit.run_id,
        ok=report is not None,
        report=report,
        error=error,
        delegations=run.delegations,
        usage=run.usage,
    )
    audit.log(
        "run_end", agent=None, ok=result.ok, error=error,
        delegations=len(run.delegations), usage=run.usage.model_dump(),
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Campus Customs agent desk")
    parser.add_argument("--ticket", type=int, action="append", help="Only handle this ticket (repeatable)")
    parser.add_argument("--message", default=DEFAULT_MESSAGE, help="Instruction for the Boss")
    args = parser.parse_args()
    result = asyncio.run(run_desk(args.message, args.ticket))
    print(json.dumps(result.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
