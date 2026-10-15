"""Campus Customs operations MCP server.

The only way into ../data/campus_customs_new.db (the working copy; the original
campus_customs.db is never touched). The agents and the backend have no other
database access.

Tools come in three groups:
  read tools          gather what an agent needs for a ticket (read-only connection)
  agent action tools  change shop data, but every business rule is enforced here,
                      not just in the agents' prompts
  human-only tools    approve/reject requests and execute approved payments; the
                      backend never gives these to an agent

Payments and price overrides go through the approval_requests table, which this
server creates in the working database on first use.

Run from this folder (stdio):  python server.py
Run (HTTP):                    python server.py --http
HTTP URL:                      http://127.0.0.1:8001/mcp
Set CAMPUS_CUSTOMS_DB to point the server at another copy (e.g. for tests).
"""

from __future__ import annotations

import argparse
import calendar
import json
import os
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastmcp import FastMCP

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DB_PATH = Path(os.getenv("CAMPUS_CUSTOMS_DB", ROOT / "data" / "campus_customs_new.db"))
# Pristine starting data; reset_working_database copies it over DB_PATH.
ORIGINAL_DB_PATH = Path(os.getenv("CAMPUS_CUSTOMS_ORIGINAL_DB", ROOT / "data" / "campus_customs.db"))

# Names the agents act under. Human-only tools refuse these as the decider, so
# an agent can never approve or execute its own request.
AGENT_NAMES = {"boss", "inventory", "accounting", "facilities", "customer_service"}

mcp = FastMCP("campus-customs-ops")


def _connect(write: bool = False) -> sqlite3.Connection:
    """Open the working database. Read tools get a read-only connection."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")
    mode = "rw" if write else "ro"
    conn = sqlite3.connect(f"file:{DB_PATH}?mode={mode}", uri=True)
    conn.row_factory = sqlite3.Row
    if write:
        conn.execute("PRAGMA foreign_keys = ON")
        _ensure_approval_table(conn)
    return conn


def _ensure_approval_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS approval_requests (
            id INTEGER PRIMARY KEY,
            kind TEXT NOT NULL,            -- invoice_payment | rent_payment | price_override
            ticket_id INTEGER,
            ref_id INTEGER,                -- invoices.id, leases.id, or NULL for price_override
            amount REAL NOT NULL,          -- payment amount, or unit price for price_override
            account TEXT,                  -- cash_accounts.name for payments
            details TEXT,                  -- JSON with the figures the request was based on
            reason TEXT NOT NULL,
            requested_by TEXT NOT NULL,    -- agent name
            status TEXT NOT NULL,          -- pending | approved | rejected | executed
            decided_by TEXT,               -- human name
            decision_note TEXT,
            created_at TEXT NOT NULL,
            decided_at TEXT,
            FOREIGN KEY (ticket_id) REFERENCES tickets(id)
        )
        """
    )


def _has_approval_table(conn: sqlite3.Connection) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'approval_requests'"
        ).fetchone()
        is not None
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> dict | None:
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _today(conn: sqlite3.Connection) -> date:
    """The shop's current date is desk.date_today, not the system clock."""
    return date.fromisoformat(conn.execute("SELECT date_today FROM desk").fetchone()[0])


def _ticket(conn: sqlite3.Connection, ticket_id: int, expected_type: str) -> dict:
    ticket = _row(conn, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    if ticket is None:
        raise ValueError(f"No ticket with id {ticket_id}.")
    if ticket["type"] != expected_type:
        raise ValueError(
            f"Ticket {ticket_id} is a '{ticket['type']}' ticket; "
            f"this tool only handles '{expected_type}' tickets."
        )
    return ticket


def _approvals_for_ticket(conn: sqlite3.Connection, ticket_id: int) -> list[dict]:
    """Approval requests already filed for a ticket, so agents don't file duplicates."""
    if not _has_approval_table(conn):
        return []
    return _rows(
        conn,
        "SELECT id, kind, ref_id, amount, status, requested_by, decided_by, created_at "
        "FROM approval_requests WHERE ticket_id = ? ORDER BY id",
        (ticket_id,),
    )


def _cash_accounts(conn: sqlite3.Connection) -> list[dict]:
    return _rows(conn, "SELECT name, balance, date FROM cash_accounts ORDER BY name")


def _stock(conn: sqlite3.Connection, sku: str, size: str, qty: int) -> dict:
    """Stock for one SKU/size against a requested quantity, plus the other sizes."""
    item = _row(
        conn,
        "SELECT name, qty, location FROM inventory WHERE sku = ? AND size = ?",
        (sku, size),
    )
    on_hand = item["qty"] if item else 0
    return {
        "sku": sku,
        "name": item["name"] if item else None,
        "size": size,
        "qty_requested": qty,
        "qty_on_hand": on_hand,
        "location": item["location"] if item else None,
        "sku_size_exists": item is not None,
        "can_fill_from_stock": on_hand >= qty,
        "shortfall": max(qty - on_hand, 0),
        "other_sizes": _rows(
            conn,
            "SELECT size, qty, location FROM inventory WHERE sku = ? AND size != ? ORDER BY size",
            (sku, size),
        ),
    }


@mcp.tool
def check_customer_order_stock_and_restock_invoice(ticket_id: int) -> dict:
    """Gather what's needed to resolve a customer_order ticket (e.g. ticket 101).

    Returns the ticket; stock on hand for the requested SKU and size, with the
    other sizes of that SKU as alternatives; the SKU's price and order total;
    the restock invoice linked to the ticket, with its vendor, lead time, days
    overdue (against desk.date_today), any payments already recorded and the
    earliest restock date if paid today; and current cash balances.
    """
    with _connect() as conn:
        ticket = _ticket(conn, ticket_id, "customer_order")
        today = _today(conn)
        qty = ticket["qty"] or 0
        stock = _stock(conn, ticket["sku"], ticket["size"], qty)
        pricing = _row(
            conn, "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (ticket["sku"],)
        )

        invoice = None
        if ticket["invoice_id"] is not None:
            invoice = _row(
                conn,
                """
                SELECT i.id, i.amount, i.due_date, i.status, i.description,
                       i.vendor_id, v.name AS vendor_name,
                       v.specialty AS vendor_specialty, v.lead_days AS vendor_lead_days
                FROM invoices i
                LEFT JOIN vendors v ON v.id = i.vendor_id
                WHERE i.id = ?
                """,
                (ticket["invoice_id"],),
            )
        if invoice:
            invoice["days_overdue"] = max(
                (today - date.fromisoformat(invoice["due_date"])).days, 0
            )
            invoice["payments_recorded"] = _rows(
                conn,
                "SELECT * FROM payments WHERE kind = 'invoice' AND ref_id = ?",
                (invoice["id"],),
            )
            if invoice["vendor_lead_days"] is not None:
                invoice["earliest_restock_if_paid_today"] = (
                    today + timedelta(days=invoice["vendor_lead_days"])
                ).isoformat()

        cash = _cash_accounts(conn)
        approvals = _approvals_for_ticket(conn, ticket_id)

    return {
        "today": today.isoformat(),
        "ticket": ticket,
        "stock": stock,
        "pricing": pricing,
        "order_total_at_list_price": pricing["list_price"] * qty if pricing else None,
        "linked_restock_invoice": invoice,
        "cash_accounts": cash,
        "approval_requests": approvals,
    }


@mcp.tool
def verify_rent_notice_against_lease(ticket_id: int) -> dict:
    """Gather what's needed to resolve a rent_notice ticket (e.g. ticket 102).

    Returns the ticket and its linked lease; whether the ticket's requester
    matches the lease's landlord; the rent amount and next due date, with days
    until due (against desk.date_today); any rent payments already recorded for
    the lease; and cash balances with what would remain after paying the rent.
    """
    with _connect() as conn:
        ticket = _ticket(conn, ticket_id, "rent_notice")
        today = _today(conn)

        lease = None
        if ticket["lease_id"] is not None:
            lease = _row(conn, "SELECT * FROM leases WHERE id = ?", (ticket["lease_id"],))
        payments = (
            _rows(conn, "SELECT * FROM payments WHERE kind = 'rent' AND ref_id = ?", (lease["id"],))
            if lease
            else []
        )
        cash = _cash_accounts(conn)
        approvals = _approvals_for_ticket(conn, ticket_id)

    checks = None
    if lease:
        rent = lease["monthly_rent"]
        checks = {
            "requester_matches_landlord": (
                ticket["requester"].strip().lower() == lease["landlord"].strip().lower()
            ),
            "rent_amount": rent,
            "next_due": lease["next_due"],
            "days_until_due": (date.fromisoformat(lease["next_due"]) - today).days,
            "balance_after_rent_by_account": {
                a["name"]: a["balance"] - rent for a in cash
            },
        }

    return {
        "today": today.isoformat(),
        "ticket": ticket,
        "lease": lease,
        "checks": checks,
        "payments_recorded_for_lease": payments,
        "cash_accounts": cash,
        "approval_requests": approvals,
    }


@mcp.tool
def evaluate_bulk_discount_request(ticket_id: int) -> dict:
    """Gather what's needed to resolve a price_override ticket (e.g. ticket 103).

    Returns the ticket; stock for the requested SKU and size, with the
    shortfall and the other sizes of that SKU; unit cost, list price, margin
    and the deepest per-unit discount that still covers cost; order totals at
    list price and at cost; every vendor with its specialty, lead time and an
    estimated arrival date (against desk.date_today) -- check `specialty`: not
    every vendor can supply this product (one is a courier); open invoices
    still owed; and current cash balances.
    """
    with _connect() as conn:
        ticket = _ticket(conn, ticket_id, "price_override")
        today = _today(conn)
        qty = ticket["qty"] or 0
        stock = _stock(conn, ticket["sku"], ticket["size"], qty)
        pricing = _row(
            conn, "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (ticket["sku"],)
        )
        vendors = _rows(conn, "SELECT * FROM vendors ORDER BY lead_days, id")
        open_invoices = _rows(
            conn,
            """
            SELECT i.id, i.amount, i.due_date, i.description, v.name AS vendor_name
            FROM invoices i LEFT JOIN vendors v ON v.id = i.vendor_id
            WHERE i.status = 'open'
            ORDER BY i.due_date
            """,
        )
        cash = _cash_accounts(conn)
        approvals = _approvals_for_ticket(conn, ticket_id)

    discount = None
    if pricing:
        cost, price = pricing["unit_cost"], pricing["list_price"]
        margin = price - cost
        discount = {
            "unit_cost": cost,
            "list_price": price,
            "margin_per_unit": margin,
            "margin_pct": round(margin / price * 100, 1) if price else None,
            "max_discount_per_unit_at_breakeven": margin,
            "max_discount_pct_at_breakeven": round(margin / price * 100, 1) if price else None,
            "order_total_at_list_price": price * qty,
            "order_total_at_cost": cost * qty,
            "shortfall_restock_cost_at_unit_cost": cost * stock["shortfall"],
        }

    for v in vendors:
        v["estimated_arrival_if_ordered_today"] = (
            today + timedelta(days=v["lead_days"])
        ).isoformat()

    return {
        "today": today.isoformat(),
        "ticket": ticket,
        "stock": stock,
        "pricing_and_discount_limits": discount,
        "vendors_check_specialty": vendors,
        "open_invoices": open_invoices,
        "cash_accounts": cash,
        "approval_requests": approvals,
    }


# ---------------------------------------------------------------------------
# General read tools
# ---------------------------------------------------------------------------

TICKET_STATUSES = {
    "in_progress",
    "waiting_on_vendor",
    "waiting_on_customer",
    "awaiting_human_approval",
    "resolved",
}
CLOSED_STATUSES = {"resolved", "shipped"}


@mcp.tool
def get_desk_date() -> dict:
    """The shop's current date (desk.date_today) and desk notes.

    Use this date, never the computer's clock, for anything overdue or coming due.
    """
    with _connect() as conn:
        return _row(conn, "SELECT date_today, notes FROM desk") or {}


@mcp.tool
def list_open_tickets() -> list[dict]:
    """Every ticket that isn't closed (status not 'resolved' or 'shipped').

    Returns id, type, requester, subject, status, created_at and the request notes,
    so the Boss can decide which agent should handle each one.
    """
    with _connect() as conn:
        return _rows(
            conn,
            """
            SELECT id, type, requester, subject, sku, size, qty, lease_id, invoice_id,
                   status, notes, created_at
            FROM tickets
            WHERE status NOT IN ('resolved', 'shipped')
            ORDER BY created_at, id
            """,
        )


@mcp.tool
def list_tickets() -> list[dict]:
    """Every ticket, open or closed, with a simple `state`: 'resolved' once the
    ticket is resolved or shipped, otherwise 'open' (whatever stage it's at).
    """
    with _connect() as conn:
        rows = _rows(
            conn,
            """
            SELECT id, type, requester, subject, sku, size, qty, lease_id, invoice_id,
                   status, notes, created_at
            FROM tickets
            ORDER BY id
            """,
        )
        for r in rows:
            r["state"] = "resolved" if r["status"] in CLOSED_STATUSES else "open"
            r["approval_requests"] = _approvals_for_ticket(conn, r["id"])
    return rows


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """One ticket with all its fields, plus any approval requests filed for it."""
    with _connect() as conn:
        ticket = _row(conn, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        if ticket is None:
            raise ValueError(f"No ticket with id {ticket_id}.")
        ticket["approval_requests"] = _approvals_for_ticket(conn, ticket_id)
        return ticket


@mcp.tool
def get_cash_position(days_ahead: int = 30) -> dict:
    """The shop's cash picture across all tickets, for deciding what can be paid.

    Returns cash account balances; every unpaid invoice with its vendor and days
    overdue; rent coming due within `days_ahead` days of desk.date_today; payment
    requests still waiting on a human (pending or approved but not executed); and
    the cash left if all of those obligations were paid.
    """
    with _connect() as conn:
        today = _today(conn)
        accounts = _cash_accounts(conn)
        invoices = _rows(
            conn,
            """
            SELECT i.id, i.amount, i.due_date, i.status, i.description,
                   i.vendor_id, v.name AS vendor_name
            FROM invoices i LEFT JOIN vendors v ON v.id = i.vendor_id
            WHERE i.status != 'paid'
            ORDER BY i.due_date
            """,
        )
        leases = _rows(conn, "SELECT * FROM leases ORDER BY next_due")
        requests = (
            _rows(
                conn,
                "SELECT id, kind, ticket_id, ref_id, amount, account, status, requested_by "
                "FROM approval_requests WHERE kind != 'price_override' "
                "AND status IN ('pending', 'approved') ORDER BY id",
            )
            if _has_approval_table(conn)
            else []
        )

    for inv in invoices:
        inv["days_overdue"] = max((today - date.fromisoformat(inv["due_date"])).days, 0)
    rent_due = []
    for lease in leases:
        days = (date.fromisoformat(lease["next_due"]) - today).days
        if days <= days_ahead:
            rent_due.append({**lease, "days_until_due": days})

    total_cash = sum(a["balance"] for a in accounts)
    obligations = sum(i["amount"] for i in invoices) + sum(l["monthly_rent"] for l in rent_due)
    return {
        "today": today.isoformat(),
        "cash_accounts": accounts,
        "total_cash": total_cash,
        "unpaid_invoices": invoices,
        "rent_due_within_window": rent_due,
        "window_days": days_ahead,
        "payment_requests_awaiting_human": requests,
        "total_obligations": obligations,
        "cash_after_all_obligations": total_cash - obligations,
    }


@mcp.tool
def list_approval_requests(
    status: Literal["pending", "approved", "rejected", "executed"] | None = None,
    ticket_id: int | None = None,
) -> list[dict]:
    """Payment and price-override requests waiting on (or decided by) a human.

    Filter by status and/or ticket. Each row says who requested it, the amount,
    the figures it was based on, and who decided it.
    """
    with _connect() as conn:
        if not _has_approval_table(conn):
            return []
        sql, params = "SELECT * FROM approval_requests WHERE 1 = 1", []
        if status:
            sql += " AND status = ?"
            params.append(status)
        if ticket_id is not None:
            sql += " AND ticket_id = ?"
            params.append(ticket_id)
        rows = _rows(conn, sql + " ORDER BY id", tuple(params))
    for r in rows:
        r["details"] = json.loads(r["details"]) if r["details"] else None
    return rows


# ---------------------------------------------------------------------------
# Agent action tools: the business rules are enforced here, not just in prompts
# ---------------------------------------------------------------------------


def _refuse(reason: str, **extra) -> dict:
    return {"ok": False, "refused": reason, **extra}


def _check_agent(name: str) -> str | None:
    if name not in AGENT_NAMES:
        return f"'{name}' is not a known agent. Use one of: {', '.join(sorted(AGENT_NAMES))}."
    return None


def _append_note(conn: sqlite3.Connection, ticket_id: int, today: date, who: str, note: str) -> None:
    conn.execute(
        "UPDATE tickets SET notes = COALESCE(notes, '') || ? WHERE id = ?",
        (f"\n[{today.isoformat()} {who}] {note.strip()}", ticket_id),
    )


def _open_requests(conn: sqlite3.Connection, kind: str, **match) -> list[dict]:
    sql = "SELECT * FROM approval_requests WHERE kind = ? AND status IN ('pending', 'approved')"
    params: list = [kind]
    for col, val in match.items():
        sql += f" AND {col} = ?"
        params.append(val)
    return _rows(conn, sql, tuple(params))


@mcp.tool
def update_ticket_status(
    ticket_id: int,
    status: Literal[
        "in_progress", "waiting_on_vendor", "waiting_on_customer", "awaiting_human_approval", "resolved"
    ],
    note: str,
    agent: str,
) -> dict:
    """Move a ticket to a new status and append a dated note saying why.

    Rules: closed tickets (resolved/shipped) can't be changed; 'shipped' is only
    set by ship_customer_order; a ticket can't be marked resolved while it has a
    payment or price override still waiting on a human.
    """
    if err := _check_agent(agent):
        return _refuse(err)
    if not note.strip():
        return _refuse("A note explaining the status change is required.")
    with _connect(write=True) as conn:
        today = _today(conn)
        ticket = _row(conn, "SELECT id, status FROM tickets WHERE id = ?", (ticket_id,))
        if ticket is None:
            return _refuse(f"No ticket with id {ticket_id}.")
        if ticket["status"] in CLOSED_STATUSES:
            return _refuse(f"Ticket {ticket_id} is already {ticket['status']}.")
        if status == "resolved":
            waiting = [
                r for r in _approvals_for_ticket(conn, ticket_id) if r["status"] in ("pending", "approved")
            ]
            if waiting:
                return _refuse(
                    "Ticket has approval requests still waiting on a human.",
                    waiting_requests=waiting,
                )
        conn.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
        _append_note(conn, ticket_id, today, agent, note)
        updated = _row(conn, "SELECT id, status, notes FROM tickets WHERE id = ?", (ticket_id,))
    return {"ok": True, "ticket": updated}


@mcp.tool
def request_payment_approval(
    kind: Literal["invoice", "rent"],
    ref_id: int,
    reason: str,
    requested_by: str,
    ticket_id: int | None = None,
    account: str = "checking",
) -> dict:
    """File a payment request for a human to approve. This does NOT pay anything.

    kind='invoice' pays invoices.id = ref_id; kind='rent' pays the rent on
    leases.id = ref_id. The amount always comes from the database (the invoice
    amount or the lease's monthly_rent), never from the caller. Refuses if the
    invoice is already paid, the account doesn't exist, or the same payment is
    already waiting on a human. Flags it if the account can't cover the amount.
    """
    if err := _check_agent(requested_by):
        return _refuse(err)
    if not reason.strip():
        return _refuse("A reason is required.")
    with _connect(write=True) as conn:
        today = _today(conn)
        acct = _row(conn, "SELECT * FROM cash_accounts WHERE name = ?", (account,))
        if acct is None:
            return _refuse(f"No cash account named '{account}'.")
        if ticket_id is not None and _row(conn, "SELECT id FROM tickets WHERE id = ?", (ticket_id,)) is None:
            return _refuse(f"No ticket with id {ticket_id}.")

        if kind == "invoice":
            inv = _row(conn, "SELECT * FROM invoices WHERE id = ?", (ref_id,))
            if inv is None:
                return _refuse(f"No invoice with id {ref_id}.")
            if inv["status"] == "paid":
                return _refuse(f"Invoice {ref_id} is already paid.")
            amount = inv["amount"]
            details = {
                "invoice": inv,
                "days_overdue": max((today - date.fromisoformat(inv["due_date"])).days, 0),
            }
        else:
            lease = _row(conn, "SELECT * FROM leases WHERE id = ?", (ref_id,))
            if lease is None:
                return _refuse(f"No lease with id {ref_id}.")
            amount = lease["monthly_rent"]
            details = {
                "lease": lease,
                "days_until_due": (date.fromisoformat(lease["next_due"]) - today).days,
            }

        request_kind = f"{kind}_payment"
        existing = _open_requests(conn, request_kind, ref_id=ref_id)
        if existing:
            return _refuse(
                "This payment already has a request waiting on a human.", existing_request=existing[0]
            )

        details.update(
            account_balance=acct["balance"],
            balance_after=acct["balance"] - amount,
            sufficient_funds=acct["balance"] >= amount,
        )
        cur = conn.execute(
            """
            INSERT INTO approval_requests
                (kind, ticket_id, ref_id, amount, account, details, reason, requested_by, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (request_kind, ticket_id, ref_id, amount, account, json.dumps(details), reason, requested_by, _now()),
        )
        request_id = cur.lastrowid
        if ticket_id is not None:
            _append_note(
                conn, ticket_id, today, requested_by,
                f"Payment request #{request_id} filed ({request_kind}, ${amount:,.2f}); waiting on human approval.",
            )
    return {
        "ok": True,
        "request_id": request_id,
        "kind": request_kind,
        "amount": amount,
        "account": account,
        "status": "pending",
        "sufficient_funds": details["sufficient_funds"],
        "balance_after": details["balance_after"],
        "next_step": "A human must approve this request; nothing has been paid.",
    }


@mcp.tool
def request_price_override_approval(
    ticket_id: int, unit_price: float, reason: str, requested_by: str
) -> dict:
    """Propose a discounted unit price for a ticket, for a human to approve.

    Refuses a price below the SKU's unit_cost (the shop never sells at a loss) or
    at/above list price (that isn't a discount), and refuses a second request
    while one is already waiting. Records the discount and order totals.
    """
    if err := _check_agent(requested_by):
        return _refuse(err)
    if not reason.strip():
        return _refuse("A reason is required.")
    with _connect(write=True) as conn:
        today = _today(conn)
        ticket = _row(conn, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        if ticket is None:
            return _refuse(f"No ticket with id {ticket_id}.")
        if not ticket["sku"] or not ticket["qty"]:
            return _refuse(f"Ticket {ticket_id} has no SKU and quantity to price.")
        pricing = _row(conn, "SELECT * FROM pricing WHERE sku = ?", (ticket["sku"],))
        if pricing is None:
            return _refuse(f"No pricing for SKU {ticket['sku']}.")
        cost, price, qty = pricing["unit_cost"], pricing["list_price"], ticket["qty"]
        if unit_price < cost:
            return _refuse(
                f"${unit_price:.2f} is below unit cost (${cost:.2f}); the shop doesn't sell at a loss.",
                unit_cost=cost,
            )
        if unit_price >= price:
            return _refuse(f"${unit_price:.2f} isn't below list price (${price:.2f}).", list_price=price)
        existing = _open_requests(conn, "price_override", ticket_id=ticket_id)
        if existing:
            return _refuse(
                "This ticket already has a price override waiting on a human.", existing_request=existing[0]
            )

        details = {
            "sku": ticket["sku"],
            "size": ticket["size"],
            "qty": qty,
            "unit_cost": cost,
            "list_price": price,
            "discount_per_unit": round(price - unit_price, 2),
            "discount_pct": round((price - unit_price) / price * 100, 1),
            "margin_per_unit": round(unit_price - cost, 2),
            "order_total_at_list": price * qty,
            "order_total_at_override": round(unit_price * qty, 2),
            "profit_at_override": round((unit_price - cost) * qty, 2),
        }
        cur = conn.execute(
            """
            INSERT INTO approval_requests
                (kind, ticket_id, ref_id, amount, account, details, reason, requested_by, status, created_at)
            VALUES ('price_override', ?, NULL, ?, NULL, ?, ?, ?, 'pending', ?)
            """,
            (ticket_id, unit_price, json.dumps(details), reason, requested_by, _now()),
        )
        request_id = cur.lastrowid
        _append_note(
            conn, ticket_id, today, requested_by,
            f"Price override request #{request_id} filed (${unit_price:.2f}/unit, "
            f"{details['discount_pct']}% off); waiting on human approval.",
        )
    return {
        "ok": True,
        "request_id": request_id,
        "status": "pending",
        **details,
        "next_step": "A human must approve this price before it's offered to the customer.",
    }


@mcp.tool
def ship_customer_order(ticket_id: int, shipped_by: str) -> dict:
    """Ship a customer_order ticket: take the items out of stock and mark it shipped.

    Refuses unless the ticket is an open customer_order, the requested SKU/size
    has enough stock, and any invoice linked to the ticket has been paid.
    """
    if err := _check_agent(shipped_by):
        return _refuse(err)
    with _connect(write=True) as conn:
        today = _today(conn)
        ticket = _row(conn, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        if ticket is None:
            return _refuse(f"No ticket with id {ticket_id}.")
        if ticket["type"] != "customer_order":
            return _refuse(f"Ticket {ticket_id} is a '{ticket['type']}' ticket, not a customer_order.")
        if ticket["status"] in CLOSED_STATUSES:
            return _refuse(f"Ticket {ticket_id} is already {ticket['status']}.")
        if ticket["invoice_id"] is not None:
            inv = _row(conn, "SELECT id, status, amount FROM invoices WHERE id = ?", (ticket["invoice_id"],))
            if inv is None or inv["status"] != "paid":
                return _refuse(
                    f"Linked invoice {ticket['invoice_id']} hasn't been paid; orders don't ship on unpaid invoices.",
                    invoice=inv,
                )
        qty = ticket["qty"] or 0
        stock = _row(
            conn, "SELECT qty FROM inventory WHERE sku = ? AND size = ?", (ticket["sku"], ticket["size"])
        )
        on_hand = stock["qty"] if stock else 0
        if qty <= 0 or on_hand < qty:
            return _refuse(
                f"Not enough stock: {on_hand} on hand, {qty} needed.", qty_on_hand=on_hand, qty_needed=qty
            )
        conn.execute(
            "UPDATE inventory SET qty = qty - ? WHERE sku = ? AND size = ?",
            (qty, ticket["sku"], ticket["size"]),
        )
        conn.execute("UPDATE tickets SET status = 'shipped' WHERE id = ?", (ticket_id,))
        _append_note(conn, ticket_id, today, shipped_by, f"Shipped {qty} x {ticket['sku']} {ticket['size']}.")
    return {"ok": True, "ticket_id": ticket_id, "shipped_qty": qty, "qty_left": on_hand - qty}


# ---------------------------------------------------------------------------
# Human-only tools: the backend never gives these to an agent
# ---------------------------------------------------------------------------


def _check_human(name: str) -> str | None:
    if not name.strip():
        return "A human's name is required."
    if name.strip().lower() in AGENT_NAMES:
        return f"'{name}' is an agent; only a human can do this."
    return None


def _add_month(d: date) -> date:
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


@mcp.tool
def decide_approval_request(
    request_id: int, decision: Literal["approve", "reject"], decided_by: str, note: str = ""
) -> dict:
    """HUMAN ONLY. Approve or reject a pending payment or price-override request.

    Approving a payment doesn't pay it; execute_approved_payment does that.
    """
    if err := _check_human(decided_by):
        return _refuse(err)
    with _connect(write=True) as conn:
        today = _today(conn)
        req = _row(conn, "SELECT * FROM approval_requests WHERE id = ?", (request_id,))
        if req is None:
            return _refuse(f"No approval request with id {request_id}.")
        if req["status"] != "pending":
            return _refuse(f"Request {request_id} is already {req['status']}.")
        status = "approved" if decision == "approve" else "rejected"
        conn.execute(
            "UPDATE approval_requests SET status = ?, decided_by = ?, decision_note = ?, decided_at = ? WHERE id = ?",
            (status, decided_by.strip(), note, _now(), request_id),
        )
        if req["ticket_id"] is not None:
            _append_note(conn, req["ticket_id"], today, decided_by.strip(), f"Request #{request_id} {status}. {note}")
            # The human has decided, so the ticket no longer waits on approval: it goes
            # back to in_progress for the agents to follow up (e.g. confirm the price to
            # the customer). An approved payment is left alone; execute_approved_payment
            # moves its ticket on once the money has actually moved.
            approved_payment = status == "approved" and req["kind"] != "price_override"
            ticket = _row(conn, "SELECT id, status FROM tickets WHERE id = ?", (req["ticket_id"],))
            still_waiting = conn.execute(
                "SELECT 1 FROM approval_requests WHERE ticket_id = ? AND status IN ('pending', 'approved') AND id != ?",
                (req["ticket_id"], request_id),
            ).fetchone()
            if not approved_payment and ticket and ticket["status"] == "awaiting_human_approval" and not still_waiting:
                conn.execute("UPDATE tickets SET status = 'in_progress' WHERE id = ?", (ticket["id"],))
                _append_note(conn, ticket["id"], today, "system", "Status set to in_progress after the human decision.")
    return {"ok": True, "request_id": request_id, "status": status, "decided_by": decided_by.strip()}


@mcp.tool
def execute_approved_payment(request_id: int, executed_by: str) -> dict:
    """HUMAN ONLY. Pay an approved invoice or rent request, all in one transaction.

    Re-checks the request is approved, the invoice is still unpaid and the account
    can cover it. Then records the payment (approved_by = the approver), lowers
    the account balance, and marks the invoice paid or moves the lease's
    next_due forward one month.
    """
    if err := _check_human(executed_by):
        return _refuse(err)
    with _connect(write=True) as conn:
        today = _today(conn)
        req = _row(conn, "SELECT * FROM approval_requests WHERE id = ?", (request_id,))
        if req is None:
            return _refuse(f"No approval request with id {request_id}.")
        if req["kind"] not in ("invoice_payment", "rent_payment"):
            return _refuse(f"Request {request_id} is a {req['kind']}, not a payment.")
        if req["status"] != "approved":
            return _refuse(f"Request {request_id} is {req['status']}; only approved payments can be executed.")
        acct = _row(conn, "SELECT * FROM cash_accounts WHERE name = ?", (req["account"],))
        if acct is None or acct["balance"] < req["amount"]:
            return _refuse(
                f"Account '{req['account']}' can't cover ${req['amount']:,.2f}.",
                balance=acct["balance"] if acct else None,
            )

        kind = "invoice" if req["kind"] == "invoice_payment" else "rent"
        if kind == "invoice":
            inv = _row(conn, "SELECT * FROM invoices WHERE id = ?", (req["ref_id"],))
            if inv is None or inv["status"] == "paid":
                return _refuse(f"Invoice {req['ref_id']} is missing or already paid.")
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (req["ref_id"],))
        else:
            lease = _row(conn, "SELECT * FROM leases WHERE id = ?", (req["ref_id"],))
            if lease is None:
                return _refuse(f"Lease {req['ref_id']} is missing.")
            next_due = _add_month(date.fromisoformat(lease["next_due"])).isoformat()
            conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (next_due, req["ref_id"]))

        cur = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
            (kind, req["ref_id"], req["amount"], req["account"], today.isoformat(), req["decided_by"]),
        )
        conn.execute(
            "UPDATE cash_accounts SET balance = balance - ?, date = ? WHERE name = ?",
            (req["amount"], today.isoformat(), req["account"]),
        )
        conn.execute(
            "UPDATE approval_requests SET status = 'executed', decision_note = "
            "COALESCE(decision_note, '') || ? WHERE id = ?",
            (f" (Executed by {executed_by.strip()} on {today.isoformat()}.)", request_id),
        )
        ticket_status = None
        if req["ticket_id"] is not None:
            _append_note(
                conn, req["ticket_id"], today, executed_by.strip(),
                f"Payment for request #{request_id} executed (${req['amount']:,.2f}).",
            )
            # Move the ticket on, unless something else on it still waits on a human:
            # paid rent closes a rent notice; a paid restock invoice means the
            # customer order is now waiting on the vendor, not on approval.
            ticket = _row(conn, "SELECT id, type, status FROM tickets WHERE id = ?", (req["ticket_id"],))
            still_waiting = conn.execute(
                "SELECT 1 FROM approval_requests WHERE ticket_id = ? AND status IN ('pending', 'approved')",
                (req["ticket_id"],),
            ).fetchone()
            if ticket and ticket["status"] not in CLOSED_STATUSES and not still_waiting:
                if kind == "rent" and ticket["type"] == "rent_notice":
                    ticket_status = "resolved"
                elif kind == "invoice" and ticket["type"] == "customer_order":
                    ticket_status = "waiting_on_vendor"
                if ticket_status:
                    conn.execute("UPDATE tickets SET status = ? WHERE id = ?", (ticket_status, ticket["id"]))
                    _append_note(conn, ticket["id"], today, "system", f"Status set to {ticket_status} after payment.")
        balance = conn.execute(
            "SELECT balance FROM cash_accounts WHERE name = ?", (req["account"],)
        ).fetchone()[0]
    return {
        "ok": True,
        "payment_id": cur.lastrowid,
        "kind": kind,
        "ref_id": req["ref_id"],
        "amount": req["amount"],
        "account": req["account"],
        "new_balance": balance,
        "approved_by": req["decided_by"],
        "ticket_status_after": ticket_status,
    }



@mcp.tool
def reset_working_database(confirm: bool, requested_by: str) -> dict:
    """HUMAN ONLY. Throw away every change in the working database and start over.

    Copies the original campus_customs.db over the working copy (SQLite's
    backup API, so it's safe while other connections are open). This removes
    payments, approval requests, status changes and notes made since the last
    reset. Requires confirm=True and a human's name.
    """
    if err := _check_human(requested_by):
        return _refuse(err)
    if not confirm:
        return _refuse("Pass confirm=true to reset the working database.")
    if not ORIGINAL_DB_PATH.exists():
        return _refuse(f"Original database not found: {ORIGINAL_DB_PATH}")
    if ORIGINAL_DB_PATH.resolve() == DB_PATH.resolve():
        return _refuse("The working database is the original; refusing to reset it onto itself.")

    src = sqlite3.connect(f"file:{ORIGINAL_DB_PATH}?mode=ro", uri=True)
    dst = sqlite3.connect(DB_PATH)
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()

    with _connect() as conn:
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        today = _today(conn).isoformat()
        checking = conn.execute("SELECT balance FROM cash_accounts WHERE name = 'checking'").fetchone()
    return {
        "ok": True,
        "reset_by": requested_by.strip(),
        "copied_from": ORIGINAL_DB_PATH.name,
        "working_database": DB_PATH.name,
        "tables": tables,
        "date_today": today,
        "checking_balance": checking[0] if checking else None,
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Campus Customs operations MCP server")
    parser.add_argument(
        "--http",
        action="store_true",
        help="Serve Streamable HTTP on port 8001 (keeps FastAPI free on 8000)",
    )
    args = parser.parse_args()
    if args.http:
        mcp.run(transport="http", host="127.0.0.1", port=8001)
    else:
        mcp.run()
