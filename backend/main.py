"""Campus Customs FastAPI backend: connects the agent team to the dashboard.

Run from this folder:
    uvicorn main:app --reload --port 8000
(with Homeworks/5/.venv active, or ../.venv/bin/uvicorn main:app --reload --port 8000)

Every read or change of shop data goes through the campus-customs-ops MCP
server: the routes call MCP tools through one long-lived MCP client
(mcp_client.ShopMCP), and agent runs use the agents' own filtered toolsets.
There is no SQL in the backend. The only file it reads directly is the audit
trail (output/audit_trail.json), which is the backend's own log, not shop data.

Money only moves in POST /api/approvals/{id}/approve: agents can file payment
requests, but the balance changes only when a named human approves one here.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from audit import AuditTrail
from config import AUDIT_PATH, MODEL_NAME
from desk import run_desk
from mcp_client import MCPToolError, ShopMCP
from models import ApproveRequest, RejectRequest, ResetRequest, RunTicketRequest

PAYMENT_KINDS = {"invoice_payment", "rent_payment"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with ShopMCP() as mcp:
        app.state.mcp = mcp
        # One desk run or reset at a time: they change the same working database.
        app.state.busy = asyncio.Lock()
        yield


app = FastAPI(title="Campus Customs Ops API", version="1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def mcp_call(tool: str, **args) -> Any:
    """Call an MCP tool; turn tool errors and business-rule refusals into HTTP errors."""
    try:
        result = await app.state.mcp.call(tool, **args)
    except MCPToolError as exc:
        status = 404 if str(exc).split(":")[-1].strip().startswith("No ") else 400
        raise HTTPException(status_code=status, detail=str(exc))
    if isinstance(result, dict) and result.get("ok") is False:
        raise HTTPException(status_code=409, detail=result)
    return result


def _human_log(action: str, **details: Any) -> None:
    AuditTrail(AUDIT_PATH).log("human_action", agent=None, action=action, **details)


async def _find_request(request_id: int) -> dict:
    for r in await mcp_call("list_approval_requests"):
        if r["id"] == request_id:
            return r
    raise HTTPException(status_code=404, detail=f"No approval request with id {request_id}.")


async def _checking() -> dict:
    cash = await mcp_call("get_cash_position")
    acct = next((a for a in cash["cash_accounts"] if a["name"] == "checking"), None)
    return {"balance": acct["balance"] if acct else None, "as_of": acct["date"] if acct else None, "cash": cash}


def _read_audit() -> list[dict]:
    if not AUDIT_PATH.exists():
        return []
    text = AUDIT_PATH.read_text(encoding="utf-8").strip() or "[]"
    events = json.loads(text)
    return events if isinstance(events, list) else []


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/api/health")
async def health() -> dict:
    desk = await mcp_call("get_desk_date")
    return {"ok": True, "model": MODEL_NAME, "date_today": desk.get("date_today"), "busy": app.state.busy.locked()}


# 1. Tickets with their open/resolved state ----------------------------------


@app.get("/api/tickets")
async def list_tickets() -> dict:
    """All tickets with their raw status and a simple open/resolved state."""
    tickets = await mcp_call("list_tickets")
    return {
        "tickets": tickets,
        "counts": {
            "open": sum(t["state"] == "open" for t in tickets),
            "resolved": sum(t["state"] == "resolved" for t in tickets),
        },
    }


@app.get("/api/tickets/{ticket_id}")
async def get_ticket(ticket_id: int) -> dict:
    return await mcp_call("get_ticket", ticket_id=ticket_id)


# 2. Run the agent team on one ticket ------------------------------------------


@app.post("/api/tickets/{ticket_id}/run")
async def run_ticket(ticket_id: int, body: RunTicketRequest | None = None) -> dict:
    """Run the Boss and team on one ticket. Waits for the run to finish (about a minute)."""
    ticket = await mcp_call("get_ticket", ticket_id=ticket_id)
    if ticket["status"] in ("resolved", "shipped"):
        raise HTTPException(status_code=409, detail=f"Ticket {ticket_id} is already {ticket['status']}.")
    if app.state.busy.locked():
        raise HTTPException(status_code=409, detail="The agent team is already running; try again when it finishes.")
    async with app.state.busy:
        message = f"Work on ticket {ticket_id} at the Campus Customs desk."
        if body and body.message:
            message += f" {body.message}"
        result = await run_desk(message, [ticket_id])
    return {
        "result": result.model_dump(mode="json"),
        "ticket_after": await mcp_call("get_ticket", ticket_id=ticket_id),
    }


_background_runs: set[asyncio.Task] = set()  # keep running even if the browser disconnects


def _sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@app.post("/api/tickets/{ticket_id}/run/stream")
async def run_ticket_stream(ticket_id: int, body: RunTicketRequest | None = None) -> StreamingResponse:
    """Same as /run, but streams every audit event live as Server-Sent Events:
    `event: audit` for each agent step, then `event: result` (or `event: error`).
    The run finishes even if the client disconnects.
    """
    ticket = await mcp_call("get_ticket", ticket_id=ticket_id)
    if ticket["status"] in ("resolved", "shipped"):
        raise HTTPException(status_code=409, detail=f"Ticket {ticket_id} is already {ticket['status']}.")
    if app.state.busy.locked():
        raise HTTPException(status_code=409, detail="The agent team is already running; try again when it finishes.")

    queue: asyncio.Queue = asyncio.Queue()
    await app.state.busy.acquire()  # held until the background run ends

    async def work() -> None:
        try:
            message = f"Work on ticket {ticket_id} at the Campus Customs desk."
            if body and body.message:
                message += f" {body.message}"
            result = await run_desk(message, [ticket_id], on_event=lambda e: queue.put_nowait(("audit", e)))
            after = await mcp_call("get_ticket", ticket_id=ticket_id)
            queue.put_nowait(("result", {"result": result.model_dump(mode="json"), "ticket_after": after}))
        except Exception as exc:  # report, don't leave the client hanging
            queue.put_nowait(("error", {"detail": str(exc)[:1000]}))
        finally:
            app.state.busy.release()
            queue.put_nowait(None)

    task = asyncio.create_task(work())
    _background_runs.add(task)
    task.add_done_callback(_background_runs.discard)

    async def events():
        yield _sse("started", {"ticket_id": ticket_id})
        while (item := await queue.get()) is not None:
            yield _sse(*item)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/runs/{run_id}/events")
async def run_events(run_id: str) -> dict:
    """Every audit event for one run, in order (lets the dashboard redraw a past run)."""
    events = [e for e in _read_audit() if e.get("run_id") == run_id]
    if not events:
        raise HTTPException(status_code=404, detail=f"No run with id {run_id}.")
    return {"run_id": run_id, "events": events}


# 3. Recent agent activity -----------------------------------------------------


@app.get("/api/activity")
async def activity(
    limit: int = Query(50, ge=1, le=500, description="Max items per list"),
    run_id: str | None = None,
    ticket_id: int | None = None,
) -> dict:
    """Recent agent messages, delegations and MCP tool calls from the audit trail, newest first."""
    events = _read_audit()
    if run_id:
        events = [e for e in events if e.get("run_id") == run_id]
    if ticket_id is not None:
        run_ids = {e["run_id"] for e in events if e.get("ticket_id") == ticket_id}
        events = [e for e in events if e.get("run_id") in run_ids]

    runs: dict[str, dict] = {}
    messages, delegations, tool_calls, human_actions = [], [], [], []
    calls_by_id: dict[str, dict] = {}
    open_delegations: dict[tuple, dict] = {}

    for e in events:
        k, d, rid = e["kind"], e.get("details", {}), e["run_id"]
        base = {"timestamp": e["timestamp"], "run_id": rid, "ticket_id": e.get("ticket_id")}
        if k == "run_start":
            runs[rid] = {"run_id": rid, "started_at": e["timestamp"], "message": d.get("message"),
                         "ticket_ids": d.get("ticket_ids"), "ok": None}
        elif k == "run_end" and rid in runs:
            runs[rid].update(ended_at=e["timestamp"], ok=d.get("ok"), error=d.get("error"),
                             delegations=d.get("delegations"),
                             total_tokens=(d.get("usage") or {}).get("total_tokens"))
        elif k == "agent_start":
            messages.append({**base, "agent": e["agent"], "chain": e["delegation_chain"], "type": "task", "text": d.get("prompt")})
        elif k == "model_response" and d.get("text"):
            messages.append({**base, "agent": e["agent"], "chain": e["delegation_chain"], "type": "message", "text": d["text"]})
        elif k == "decision" and isinstance(d.get("output"), dict):
            out = d["output"]
            text = out.get("summary") or out.get("cash_summary") or ""
            messages.append({**base, "agent": e["agent"], "chain": e["delegation_chain"], "type": "report", "text": text})
        elif k == "delegation":
            item = {**base, "from_agent": d["from_agent"], "to_agent": d["to_agent"], "depth": d["depth"],
                    "task": d["task"], "status": "running", "summary": None}
            delegations.append(item)
            open_delegations[(rid, d["to_agent"], e.get("ticket_id"))] = item
        elif k == "delegation_result":
            item = open_delegations.pop((rid, e["agent"], e.get("ticket_id")), None)
            if item:
                item["status"] = d.get("status")
                item["summary"] = (d.get("report") or {}).get("summary") or d.get("error")
        elif k == "tool_call" and d.get("tool") != "final_result":
            item = {**base, "agent": e["agent"], "tool": d["tool"], "args": d.get("args"),
                    "kind": "delegation" if d["tool"] in ("assign_ticket", "ask_colleague") else "mcp",
                    "ok": None, "result": None}
            tool_calls.append(item)
            calls_by_id[d.get("tool_call_id")] = item
        elif k == "tool_result":
            item = calls_by_id.get(d.get("tool_call_id"))
            if item:
                item["ok"], item["result"] = d.get("ok"), d.get("content")
        elif k == "human_action":
            human_actions.append({**base, **d})

    newest = lambda xs: list(reversed(xs))[:limit]  # noqa: E731
    return {
        "runs": newest(list(runs.values())),
        "messages": newest(messages),
        "delegations": newest(delegations),
        "tool_calls": newest(tool_calls),
        "mcp_tools_used": sorted({t["tool"] for t in tool_calls if t["kind"] == "mcp"}),
        "human_actions": newest(human_actions),
    }


# 4. Human approval of proposed payments / purchases ---------------------------


@app.get("/api/approvals")
async def list_approvals(status: str | None = Query(None, pattern="^(pending|approved|rejected|executed)$")) -> dict:
    """Payment and price-override requests the agents have filed."""
    args = {"status": status} if status else {}
    return {"requests": await mcp_call("list_approval_requests", **args)}


@app.post("/api/approvals/{request_id}/approve")
async def approve(request_id: int, body: ApproveRequest) -> dict:
    """A named human approves a request. For a payment (an invoice, i.e. a vendor
    purchase, or rent) this is the only place money moves: approve, then execute
    in the MCP server's single transaction. A price override is just approved.
    """
    req = await _find_request(request_id)
    is_payment = req["kind"] in PAYMENT_KINDS
    before = await _checking()

    if req["status"] == "pending":
        if is_payment:
            acct = next((a for a in before["cash"]["cash_accounts"] if a["name"] == req["account"]), None)
            if acct is None or acct["balance"] < req["amount"]:
                raise HTTPException(
                    status_code=409,
                    detail=f"Account '{req['account']}' can't cover ${req['amount']:,.2f}; request left pending.",
                )
        await mcp_call("decide_approval_request", request_id=request_id, decision="approve",
                       decided_by=body.approved_by, note=body.note)
    elif not (req["status"] == "approved" and is_payment):  # approved-but-unpaid can be retried
        raise HTTPException(status_code=409, detail=f"Request {request_id} is already {req['status']}.")

    payment = None
    if is_payment:
        payment = await mcp_call("execute_approved_payment", request_id=request_id, executed_by=body.approved_by)
    after = await _checking()

    _human_log(
        "approve", request_id=request_id, request_kind=req["kind"], amount=req["amount"],
        approved_by=body.approved_by, ticket=req.get("ticket_id"),
        payment_id=payment["payment_id"] if payment else None,
        checking_before=before["balance"], checking_after=after["balance"],
    )
    return {
        "request": await _find_request(request_id),
        "payment": payment,
        "checking_balance_before": before["balance"],
        "checking_balance_after": after["balance"],
    }


@app.post("/api/approvals/{request_id}/reject")
async def reject(request_id: int, body: RejectRequest) -> dict:
    """A named human rejects a pending request. Nothing is paid or changed."""
    req = await _find_request(request_id)
    await mcp_call("decide_approval_request", request_id=request_id, decision="reject",
                   decided_by=body.rejected_by, note=body.note)
    _human_log("reject", request_id=request_id, request_kind=req["kind"], amount=req["amount"],
               rejected_by=body.rejected_by, ticket=req.get("ticket_id"))
    return {"request": await _find_request(request_id)}


# 5. Checking balance --------------------------------------------------------------


@app.get("/api/cash")
async def cash() -> dict:
    """Checking balance from cash_accounts, plus what's owed and waiting on approval."""
    c = await _checking()
    cash = c["cash"]
    return {
        "checking_balance": c["balance"],
        "as_of": c["as_of"],
        "date_today": cash["today"],
        "cash_accounts": cash["cash_accounts"],
        "payment_requests_awaiting_human": cash["payment_requests_awaiting_human"],
        "unpaid_invoices": cash["unpaid_invoices"],
        "rent_due_within_window": cash["rent_due_within_window"],
        "total_obligations": cash["total_obligations"],
        "cash_after_all_obligations": cash["cash_after_all_obligations"],
    }


# 6. Reset the working database ------------------------------------------------------


@app.post("/api/reset")
async def reset(body: ResetRequest) -> dict:
    """Copy the original campus_customs.db over the working copy. The audit trail is
    kept (it's append-only); the reset itself is logged there.
    """
    if app.state.busy.locked():
        raise HTTPException(status_code=409, detail="The agent team is running; reset after it finishes.")
    async with app.state.busy:
        result = await mcp_call("reset_working_database", confirm=body.confirm, requested_by=body.requested_by)
    _human_log("reset_database", requested_by=body.requested_by, checking_after=result.get("checking_balance"))
    return result
