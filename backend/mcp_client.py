"""The agents' only route to shop data: the campus-customs-ops MCP server.

The backend starts mcp_server/server.py over stdio (the same way
.mcp.json does for Claude Code) and gives each agent a filtered view of its
tools. The backend has no database code of its own.

Each agent sees only the tools on its allowlist. The human-only tools
(decide_approval_request, execute_approved_payment) are on no agent's list, so
no agent can approve or execute a payment.
"""

from __future__ import annotations

import os
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.toolsets import FilteredToolset

from config import MCP_PYTHON, MCP_SERVER_PATH, PROJECT_ROOT

HUMAN_ONLY_TOOLS = frozenset(
    {"decide_approval_request", "execute_approved_payment", "reset_working_database"}
)

_SHARED_READS = {"get_desk_date", "get_ticket"}

AGENT_TOOLS: dict[str, frozenset[str]] = {
    "boss": frozenset(_SHARED_READS | {"list_open_tickets", "get_cash_position", "list_approval_requests"}),
    "inventory": frozenset(
        _SHARED_READS
        | {
            "check_customer_order_stock_and_restock_invoice",
            "evaluate_bulk_discount_request",
            "ship_customer_order",
            "update_ticket_status",
        }
    ),
    "accounting": frozenset(
        _SHARED_READS
        | {
            "get_cash_position",
            "list_approval_requests",
            "check_customer_order_stock_and_restock_invoice",
            "verify_rent_notice_against_lease",
            "evaluate_bulk_discount_request",
            "request_payment_approval",
            "request_price_override_approval",
            "update_ticket_status",
        }
    ),
    "facilities": frozenset(
        _SHARED_READS | {"verify_rent_notice_against_lease", "update_ticket_status"}
    ),
    "customer_service": frozenset(
        _SHARED_READS
        | {
            "check_customer_order_stock_and_restock_invoice",
            "evaluate_bulk_discount_request",
            "list_approval_requests",
            "update_ticket_status",
        }
    ),
}

for _agent, _tools in AGENT_TOOLS.items():
    assert not (_tools & HUMAN_ONLY_TOOLS), f"{_agent} must not get human-only tools"


def _transport() -> StdioTransport:
    """Start mcp_server/server.py as a stdio subprocess (the same way .mcp.json does)."""
    env = None
    overrides = {k: os.environ[k] for k in ("CAMPUS_CUSTOMS_DB", "CAMPUS_CUSTOMS_ORIGINAL_DB") if os.getenv(k)}
    if overrides:  # point the server at other copies, e.g. for tests
        env = {**overrides, "PATH": os.environ.get("PATH", "")}
    log_dir = PROJECT_ROOT / "output"
    log_dir.mkdir(exist_ok=True)
    return StdioTransport(
        command=MCP_PYTHON,
        args=[str(MCP_SERVER_PATH)],
        env=env,
        cwd=str(MCP_SERVER_PATH.parent),
        log_file=log_dir / "mcp_server.log",  # server banner/logs go here, not the terminal
    )


def build_mcp_toolset() -> MCPToolset:
    """The agents' client for the MCP server."""
    return MCPToolset(Client(_transport()), id="campus-customs-ops")


class MCPToolError(Exception):
    """An MCP tool raised an error (e.g. unknown ticket id)."""


class ShopMCP:
    """The FastAPI backend's own MCP client, for routes that read or change shop
    data outside an agent run (ticket list, cash, approvals, reset). One server
    process is kept open for the app's lifetime.
    """

    def __init__(self) -> None:
        self._client = Client(_transport())

    async def __aenter__(self) -> "ShopMCP":
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *exc) -> None:
        await self._client.__aexit__(*exc)

    async def call(self, tool: str, **args) -> Any:
        result = await self._client.call_tool(tool, args, raise_on_error=False)
        if result.is_error:
            text = " ".join(getattr(c, "text", "") for c in result.content).strip()
            raise MCPToolError(text or f"{tool} failed")
        if result.data is not None:
            return result.data
        return result.structured_content


def toolset_for(base: MCPToolset, agent: str) -> FilteredToolset:
    allowed = AGENT_TOOLS[agent]
    return base.filtered(lambda _ctx, tool_def: tool_def.name in allowed)
