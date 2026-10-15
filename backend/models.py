"""Shared data types for the Campus Customs agent team."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
SpecialistName = Literal["inventory", "accounting", "facilities", "customer_service"]

AGENT_TITLES: dict[str, str] = {
    "boss": "Boss",
    "inventory": "Inventory",
    "accounting": "Accounting",
    "facilities": "Facilities",
    "customer_service": "Customer Service",
}

TicketType = Literal["customer_order", "rent_notice", "price_override"]

AuditKind = Literal[
    "run_start",         # a desk run began
    "agent_start",       # an agent began working on a task
    "model_response",    # the model answered: text, tool calls, token usage
    "tool_call",         # an agent called an MCP tool or the delegation tool
    "tool_result",       # what that tool returned
    "delegation",        # one agent handed work to another
    "delegation_result", # the other agent reported back
    "decision",          # an agent's final structured report
    "limit_reached",     # a loop, delegation or token limit stopped something
    "error",             # something failed
    "run_end",           # the desk run finished, with total usage
    "human_action",      # a person approved/rejected a request or reset the database (API)
]


class ApprovalNeeded(BaseModel):
    """Something only a human can decide: a payment or a price override."""

    request_id: int | None = Field(
        None, description="approval_requests.id if a request was filed, else null"
    )
    kind: Literal["invoice_payment", "rent_payment", "price_override", "other"]
    amount: float | None = Field(None, description="Payment amount, or unit price for a price override")
    summary: str = Field(description="One sentence a human can decide from")


class SpecialistReport(BaseModel):
    """What a specialist agent hands back to whoever delegated to it."""

    ticket_id: int | None = None
    summary: str = Field(description="Two or three sentences: what you found and what you did")
    findings: list[str] = Field(default_factory=list, description="Facts from MCP tools, with figures")
    actions_taken: list[str] = Field(
        default_factory=list, description="Changes made through MCP tools (status updates, requests filed, shipments)"
    )
    blocked_by: list[str] = Field(default_factory=list, description="What stops this ticket being finished")
    needs_human_approval: list[ApprovalNeeded] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)
    customer_message: str | None = Field(
        None, description="Draft message to the requester, if one is needed. Not sent."
    )


class TicketOutcome(BaseModel):
    ticket_id: int
    ticket_type: str
    handled_by: list[AgentName] = Field(description="Agents that worked on this ticket, lead first")
    status_after: str = Field(description="The ticket's status after this run")
    summary: str
    human_decisions_needed: list[ApprovalNeeded] = Field(default_factory=list)
    customer_message: str | None = None


class DeskReport(BaseModel):
    """The Boss's final report for a desk run."""

    date_today: str = Field(description="desk.date_today")
    tickets: list[TicketOutcome]
    cash_summary: str = Field(description="Cash on hand vs. obligations, after this run's decisions")
    human_action_items: list[str] = Field(
        description="What a human needs to approve or do next, most urgent first"
    )


class Delegation(BaseModel):
    from_agent: AgentName
    to_agent: SpecialistName
    ticket_id: int | None
    task: str
    depth: int
    status: Literal["running", "done", "error", "limit_reached"] = "running"
    report: SpecialistReport | None = None
    error: str | None = None


class AuditEvent(BaseModel):
    """One line in output/audit_trail.json."""

    event_id: str
    run_id: str
    seq: int
    timestamp: str
    agent: AgentName | None
    kind: AuditKind
    ticket_id: int | None = None
    delegation_chain: list[str] = Field(
        default_factory=list, description="Who asked whom, e.g. ['boss', 'facilities']"
    )
    details: dict[str, Any] = Field(default_factory=dict)


class RunUsage(BaseModel):
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    tool_calls: int = 0
    by_agent: dict[str, dict[str, int]] = Field(default_factory=dict)


# ---- API request bodies (backend/main.py) ----------------------------------


class RunTicketRequest(BaseModel):
    message: str | None = Field(None, description="Optional extra instruction for the Boss")


class ApproveRequest(BaseModel):
    approved_by: str = Field(min_length=1, description="The human approving (not an agent name)")
    note: str = ""


class RejectRequest(BaseModel):
    rejected_by: str = Field(min_length=1, description="The human rejecting (not an agent name)")
    note: str = ""


class ResetRequest(BaseModel):
    confirm: bool = Field(description="Must be true")
    requested_by: str = Field(min_length=1, description="The human resetting the database")


class DeskRunResult(BaseModel):
    run_id: str
    ok: bool
    report: DeskReport | None = None
    error: str | None = None
    delegations: list[Delegation] = Field(default_factory=list)
    usage: RunUsage
