# Campus Customs MCP Server

A [FastMCP](https://gofastmcp.com) server, `campus-customs-ops`, that is the **only** way into the Campus Customs operations database. The five-agent backend (`backend/`) and Claude Code (`.mcp.json`) both use it. Neither has any other database access.

## Database

- **File:** `../data/campus_customs_new.db`, the working copy of `data/campus_customs.db`. The original is never used. Set `CAMPUS_CUSTOMS_DB` to point the server at another copy, such as a scratch copy for tests.
- **Read tools** open the database read-only (`mode=ro`). **Action tools** open it read-write, with foreign keys turned on, and each one runs as a single transaction.
- **"Today"** is `desk.date_today` (currently `2026-08-31`), never the computer's clock.
- **New table:** the server creates `approval_requests` in the working database on its first write. It holds payment and price-override requests waiting on a human. The original nine tables are unchanged.

## Tools

### Read tools

| Tool | Use | Tables read |
|---|---|---|
| `get_desk_date()` | The shop's current date and desk notes | `desk` |
| `list_open_tickets()` | Every ticket not `resolved` or `shipped` | `tickets` |
| `get_ticket(ticket_id)` | One ticket plus its approval requests | `tickets`, `approval_requests` |
| `check_customer_order_stock_and_restock_invoice(ticket_id)` | `customer_order` tickets (e.g. 101): stock for the SKU and size, alternatives, price, the linked restock invoice with vendor, lead time and days overdue | `tickets`, `desk`, `inventory`, `pricing`, `invoices`, `vendors`, `payments`, `cash_accounts`, `approval_requests` |
| `verify_rent_notice_against_lease(ticket_id)` | `rent_notice` tickets (e.g. 102): the lease, landlord match, rent, days until due, rent already paid, balance after rent | `tickets`, `desk`, `leases`, `payments`, `cash_accounts`, `approval_requests` |
| `evaluate_bulk_discount_request(ticket_id)` | `price_override` tickets (e.g. 103): stock and shortfall, cost, list price, margin, maximum discount at breakeven, every vendor with specialty and lead time (`vendors_check_specialty`; one is a courier) | `tickets`, `desk`, `inventory`, `pricing`, `vendors`, `invoices`, `cash_accounts`, `approval_requests` |
| `get_cash_position(days_ahead=30)` | Cash across all tickets: balances, unpaid invoices, rent due soon, requests awaiting a human, cash left after all obligations | `desk`, `cash_accounts`, `invoices`, `vendors`, `leases`, `approval_requests` |
| `list_approval_requests(status, ticket_id)` | Requests by status and/or ticket | `approval_requests` |
| `list_tickets()` | Every ticket, open or closed, with a simple `state` (`open` or `resolved`) and its approval requests. Used by the FastAPI backend, not given to agents | `tickets`, `approval_requests` |

### Agent action tools (business rules enforced in the tool)

| Tool | What it does | Refuses when |
|---|---|---|
| `update_ticket_status(ticket_id, status, note, agent)` | Sets `in_progress`, `waiting_on_vendor`, `waiting_on_customer`, `awaiting_human_approval` or `resolved`, and appends a dated note | the ticket is closed; the note is empty; it's being `resolved` with requests still waiting on a human |
| `request_payment_approval(kind, ref_id, reason, requested_by, ticket_id, account)` | Files an `invoice` or `rent` payment for a human to approve. **Pays nothing.** The amount comes from the database | the invoice is already paid; the invoice, lease or account is missing; a request for it is already pending or approved |
| `request_price_override_approval(ticket_id, unit_price, reason, requested_by)` | Files a discounted unit price for a human to approve | the price is below `unit_cost` or at/above list price; a request is already waiting |
| `ship_customer_order(ticket_id, shipped_by)` | Takes stock out and marks a `customer_order` shipped | the linked invoice isn't `paid`; stock is short for the exact SKU and size; the ticket is closed or not a customer order |

Every action tool requires a known agent name (`boss`, `inventory`, `accounting`, `facilities`, `customer_service`), so each change is attributable.

### Human-only tools

The backend gives these to no agent. They also refuse an agent's name as the decider.

| Tool | What it does |
|---|---|
| `decide_approval_request(request_id, decision, decided_by, note)` | A human approves or rejects a pending request |
| `execute_approved_payment(request_id, executed_by)` | Pays an **approved** request in one transaction: adds a `payments` row (with `approved_by` = the approver), lowers the account balance, and marks the invoice `paid` or moves the lease's `next_due` forward a month. It then moves the linked ticket on: a `rent_notice` becomes `resolved`, and a `customer_order` becomes `waiting_on_vendor`, unless other requests on the ticket are still waiting. Refuses if the request isn't approved, the invoice is already paid, or the balance can't cover the payment |
| `reset_working_database(confirm, requested_by)` | Copies the original `campus_customs.db` over the working copy (SQLite backup API), undoing every payment, request and status change. Needs `confirm=true` and a human's name |

## Setup and running

From `Homeworks/5`:

```bash
python3 -m venv .venv
```

```bash
.venv/bin/pip install -r mcp_server/requirements.txt
```

Run over stdio. This is what `.mcp.json` and the backend use:

```bash
.venv/bin/python mcp_server/server.py
```

Or over HTTP at `http://127.0.0.1:8001/mcp`, which leaves port 8000 free for FastAPI:

```bash
.venv/bin/python mcp_server/server.py --http
```

## Notes

- **Payment kinds** are `invoice` and `rent`. `payments.ref_id` is the `invoices.id` or `leases.id`.
- **Foreign keys aren't enforced by the original schema**, so the action tools check that tickets, invoices, leases and accounts exist before writing.
- **Running the agents changes the working database.** They file approval requests and update ticket statuses and notes. To start fresh, call `reset_working_database`, or use `POST /api/reset` on the backend.
- **Who calls what.** The FastAPI backend (`backend/main.py`) calls the human-only tools only from its human routes: approve, reject and reset. Set `CAMPUS_CUSTOMS_ORIGINAL_DB` to reset from a different source copy.
