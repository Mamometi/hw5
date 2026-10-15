"""The Campus Customs agent team: Boss + four specialists, all on gpt-6-luna.

The Boss reads the open tickets and assigns each one to the specialist best
suited to it. Specialists work the ticket with their own MCP tools and can ask a
colleague for help (ask_colleague) when part of the job is someone else's
responsibility. Nobody is sent a ticket by default.

Every agent-loop node, tool call, delegation and final report is appended to
output/audit_trail.json as it happens.

Guard rails (see config.py):
  - delegation depth (Boss -> specialist -> colleague) and a per-run delegation cap
  - no delegating to yourself or to an agent already up the chain (no loops)
  - per-agent request / tool-call / token limits (PydanticAI UsageLimits)
  - a team token budget across every agent in the run
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.messages import RetryPromptPart, TextPart, ToolCallPart, ToolReturnPart

from audit import AuditTrail
from config import (
    BOSS_LIMITS,
    MAX_DELEGATION_DEPTH,
    MAX_DELEGATIONS_PER_RUN,
    MODEL_NAME,
    PROMPTS_DIR,
    SPECIALIST_LIMITS,
    TEAM_TOKEN_BUDGET,
    build_model,
)
from mcp_client import toolset_for
from models import AGENT_TITLES, Delegation, DeskReport, RunUsage, SpecialistName, SpecialistReport


class TeamBudgetExceeded(Exception):
    """The run's shared token budget is used up; every agent must stop."""


def clip(value: Any, limit: int = 2000) -> str:
    text = value if isinstance(value, str) else str(value)
    return text if len(text) <= limit else text[:limit] + f"... (+{len(text) - limit} chars)"


# ---------------------------------------------------------------------------
# Run state shared by every agent in one desk run
# ---------------------------------------------------------------------------


@dataclass
class RunState:
    audit: AuditTrail
    toolset: MCPToolset
    delegations: list[Delegation] = field(default_factory=list)
    usage: RunUsage = field(default_factory=RunUsage)

    def add_usage(self, agent: str, usage: Any) -> dict:
        inp = getattr(usage, "input_tokens", 0) or 0
        out = getattr(usage, "output_tokens", 0) or 0
        u = self.usage
        u.requests += 1
        u.input_tokens += inp
        u.output_tokens += out
        u.total_tokens += inp + out
        mine = u.by_agent.setdefault(agent, {"requests": 0, "input_tokens": 0, "output_tokens": 0, "tool_calls": 0})
        mine["requests"] += 1
        mine["input_tokens"] += inp
        mine["output_tokens"] += out
        return {"input_tokens": inp, "output_tokens": out, "team_total_tokens": u.total_tokens}

    def add_tool_calls(self, agent: str, n: int) -> None:
        self.usage.tool_calls += n
        self.usage.by_agent.setdefault(
            agent, {"requests": 0, "input_tokens": 0, "output_tokens": 0, "tool_calls": 0}
        )["tool_calls"] += n

    def check_budget(self) -> None:
        if self.usage.total_tokens >= TEAM_TOKEN_BUDGET:
            raise TeamBudgetExceeded(
                f"Team token budget of {TEAM_TOKEN_BUDGET:,} reached "
                f"({self.usage.total_tokens:,} used). Run stopped."
            )


@dataclass
class AgentDeps:
    run: RunState
    agent: str
    chain: tuple[str, ...]  # e.g. ("boss", "facilities"): who asked whom to get here
    ticket_id: int | None = None


# ---------------------------------------------------------------------------
# The five agents
# ---------------------------------------------------------------------------

SHOP_RULES = (PROMPTS_DIR / "shop_rules.md").read_text(encoding="utf-8")


def _prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8") + "\n\n" + SHOP_RULES


def _context_note(ctx: RunContext[AgentDeps]) -> str:
    d = ctx.deps
    depth = len(d.chain) - 1
    can_delegate = depth < MAX_DELEGATION_DEPTH
    lines = [
        "## This run",
        f"- You are: {AGENT_TITLES[d.agent]} (agent name `{d.agent}`). Use `{d.agent}` as your name in MCP tools.",
        f"- Delegation chain: {' -> '.join(d.chain)} (depth {depth} of max {MAX_DELEGATION_DEPTH}).",
    ]
    if d.agent != "boss":
        lines.append(
            "- You may ask a colleague for help."
            if can_delegate
            else "- You are at the maximum delegation depth: you can't ask a colleague. Report back with what you have."
        )
    return "\n".join(lines)


boss_agent = Agent(
    output_type=DeskReport,
    deps_type=AgentDeps,
    instructions=_prompt("boss"),
    name="boss",
    retries=2,
    end_strategy="exhaustive",  # never skip an action requested alongside the final report
)
specialist_agents: dict[str, Agent] = {
    name: Agent(
        output_type=SpecialistReport,
        deps_type=AgentDeps,
        instructions=_prompt(name),
        name=name,
        retries=2,
        end_strategy="exhaustive",
    )
    for name in ("inventory", "accounting", "facilities", "customer_service")
}
AGENTS: dict[str, Agent] = {"boss": boss_agent, **specialist_agents}

for _agent in AGENTS.values():
    _agent.instructions(_context_note)


# ---------------------------------------------------------------------------
# Delegation
# ---------------------------------------------------------------------------


async def _delegate(
    ctx: RunContext[AgentDeps], to_agent: str, task: str, ticket_id: int | None
) -> dict:
    d = ctx.deps
    run = d.run
    run.check_budget()
    depth = len(d.chain)  # depth the new agent would be at

    refusal = None
    if to_agent == d.agent:
        refusal = "You can't delegate to yourself."
    elif to_agent in d.chain:
        refusal = (
            f"{AGENT_TITLES[to_agent]} is already working on this further up the chain "
            f"({' -> '.join(d.chain)}). Finish with what you have instead of passing it back."
        )
    elif depth > MAX_DELEGATION_DEPTH:
        refusal = f"Maximum delegation depth ({MAX_DELEGATION_DEPTH}) reached. Report back with what you have."
    elif len(run.delegations) >= MAX_DELEGATIONS_PER_RUN:
        refusal = f"This run has used all {MAX_DELEGATIONS_PER_RUN} delegations. Finish with what you have."
    if refusal:
        run.audit.log(
            "limit_reached", agent=d.agent, chain=d.chain, ticket_id=ticket_id,
            limit="delegation", to_agent=to_agent, reason=refusal,
        )
        return {"ok": False, "refused": refusal}

    delegation = Delegation(
        from_agent=d.agent, to_agent=to_agent, ticket_id=ticket_id, task=task, depth=depth
    )
    run.delegations.append(delegation)
    chain = (*d.chain, to_agent)
    run.audit.log(
        "delegation", agent=d.agent, chain=d.chain, ticket_id=ticket_id,
        from_agent=d.agent, to_agent=to_agent, task=task, depth=depth,
        delegation_number=len(run.delegations),
    )

    prompt = (
        f"Ticket: {ticket_id if ticket_id is not None else 'n/a'}\n"
        f"Request from {AGENT_TITLES[d.agent]}: {task}"
    )
    try:
        report = await run_agent(to_agent, prompt, run, chain=chain, ticket_id=ticket_id)
        delegation.status, delegation.report = "done", report
    except UsageLimitExceeded as exc:
        delegation.status, delegation.error = "limit_reached", str(exc)
        run.audit.log(
            "limit_reached", agent=to_agent, chain=chain, ticket_id=ticket_id,
            limit="agent_usage", reason=str(exc),
        )
    except TeamBudgetExceeded:
        delegation.status, delegation.error = "limit_reached", "team token budget reached"
        raise
    except Exception as exc:  # report the failure to the caller instead of crashing its run
        delegation.status, delegation.error = "error", clip(exc, 500)
        run.audit.log("error", agent=to_agent, chain=chain, ticket_id=ticket_id, error=clip(exc, 1000))

    run.audit.log(
        "delegation_result", agent=to_agent, chain=chain, ticket_id=ticket_id,
        to_agent=d.agent, status=delegation.status,
        report=delegation.report.model_dump() if delegation.report else None,
        error=delegation.error,
    )
    if delegation.report:
        return {"ok": True, "from": to_agent, "report": delegation.report.model_dump()}
    return {"ok": False, "from": to_agent, "status": delegation.status, "error": delegation.error}


# sequential=True: tickets are worked one after another, never in parallel, so
# each agent sees what earlier agents filed (e.g. Accounting sees the payment
# requests already waiting before it judges whether cash covers another one).
@boss_agent.tool(sequential=True)
async def assign_ticket(
    ctx: RunContext[AgentDeps], to_agent: SpecialistName, ticket_id: int, task: str
) -> dict:
    """Assign a ticket to the one specialist best suited to it, and get their report back.

    Args:
        to_agent: inventory, accounting, facilities or customer_service.
        ticket_id: The ticket to work on.
        task: What you need from them, with the facts you already know.
    """
    return await _delegate(ctx, to_agent, task, ticket_id)


def _register_ask_colleague(agent: Agent) -> None:
    @agent.tool
    async def ask_colleague(
        ctx: RunContext[AgentDeps], to_agent: SpecialistName, task: str, ticket_id: int | None = None
    ) -> dict:
        """Hand part of a ticket to the colleague whose job it is, and get their report back.

        Only use this for work outside your own responsibilities (see your
        instructions). Say exactly what you need and include the figures you have.

        Args:
            to_agent: inventory, accounting, facilities or customer_service (not yourself).
            task: The specific thing you need them to do or check.
            ticket_id: The ticket this is about.
        """
        return await _delegate(ctx, to_agent, task, ticket_id)


for _agent in specialist_agents.values():
    _register_ask_colleague(_agent)


# ---------------------------------------------------------------------------
# Running one agent, with every loop step audited
# ---------------------------------------------------------------------------


async def run_agent(
    name: str,
    prompt: str,
    run: RunState,
    *,
    chain: tuple[str, ...],
    ticket_id: int | None = None,
) -> Any:
    agent = AGENTS[name]
    deps = AgentDeps(run=run, agent=name, chain=chain, ticket_id=ticket_id)
    limits = BOSS_LIMITS if name == "boss" else SPECIALIST_LIMITS
    run.audit.log(
        "agent_start", agent=name, chain=chain, ticket_id=ticket_id,
        prompt=clip(prompt), model=MODEL_NAME,
        limits={
            "request_limit": limits.request_limit,
            "tool_calls_limit": limits.tool_calls_limit,
            "total_tokens_limit": limits.total_tokens_limit,
        },
    )

    async with agent.iter(
        prompt,
        deps=deps,
        model=build_model(),
        toolsets=[toolset_for(run.toolset, name)],
        usage_limits=limits,
    ) as agent_run:
        logged_results: set[str] = set()
        async for node in agent_run:
            run.check_budget()
            if Agent.is_call_tools_node(node):
                resp = node.model_response
                calls = [p for p in resp.parts if isinstance(p, ToolCallPart)]
                text = "".join(p.content for p in resp.parts if isinstance(p, TextPart))
                usage = run.add_usage(name, resp.usage)
                run.add_tool_calls(name, len(calls))
                run.audit.log(
                    "model_response", agent=name, chain=chain, ticket_id=ticket_id,
                    text=clip(text, 1000), tool_calls=[c.tool_name for c in calls], usage=usage,
                )
                for c in calls:
                    run.audit.log(
                        "tool_call", agent=name, chain=chain, ticket_id=ticket_id,
                        tool=c.tool_name, tool_call_id=c.tool_call_id, args=c.args_as_dict(),
                    )
                run.check_budget()
            elif Agent.is_model_request_node(node):
                for p in node.request.parts:
                    if isinstance(p, ToolReturnPart):
                        logged_results.add(p.tool_call_id)
                        run.audit.log(
                            "tool_result", agent=name, chain=chain, ticket_id=ticket_id,
                            tool=p.tool_name, tool_call_id=p.tool_call_id, ok=True,
                            content=clip(p.model_response_str()),
                        )
                    elif isinstance(p, RetryPromptPart) and p.tool_name:
                        logged_results.add(p.tool_call_id)
                        run.audit.log(
                            "tool_result", agent=name, chain=chain, ticket_id=ticket_id,
                            tool=p.tool_name, tool_call_id=p.tool_call_id, ok=False,
                            content=clip(p.model_response()),
                        )
        # Tools called in the same response as the final report run, but the loop
        # ends before another step shows their results; log them from the history.
        for msg in agent_run.result.all_messages():
            for p in getattr(msg, "parts", []):
                if isinstance(p, ToolReturnPart) and p.tool_name != "final_result" and p.tool_call_id not in logged_results:
                    logged_results.add(p.tool_call_id)
                    run.audit.log(
                        "tool_result", agent=name, chain=chain, ticket_id=ticket_id,
                        tool=p.tool_name, tool_call_id=p.tool_call_id, ok=True,
                        content=clip(p.model_response_str()),
                    )
        output = agent_run.result.output

    run.audit.log(
        "decision", agent=name, chain=chain, ticket_id=ticket_id, output=output.model_dump()
    )
    return output
