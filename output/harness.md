# Campus Customs — Agent Harness Notes

Working database: `data/campus_customs_new.db`, a copy of `data/campus_customs.db`. All work uses the copy, and the original stays unchanged.

Everything below comes from querying the database directly. Where something is an inference rather than a stored fact, it is marked **(inferred)**.

---

## 1. Database at a glance

| Table | Rows | Primary key | Declared foreign keys |
|---|---|---|---|
| `desk` | 1 | none | none |
| `tickets` | 3 | `id` | `lease_id` → `leases.id`, `invoice_id` → `invoices.id` |
| `inventory` | 10 | (`sku`, `size`) | none |
| `pricing` | 4 | `sku` | none |
| `vendors` | 3 | `id` | none |
| `leases` | 1 | `id` | none |
| `cash_accounts` | 1 | `name` | none |
| `payments` | 0 | `id` | none |
| `invoices` | 1 | `id` | `vendor_id` → `vendors.id` |

- **Foreign keys are not enforced.** `PRAGMA foreign_keys` is `0`, so SQLite won't stop a bad `lease_id`, `invoice_id` or `vendor_id`. The tools need to check these themselves.
- **Several links exist only by convention:** `tickets.sku` → `inventory.sku` / `pricing.sku`, `payments.account` → `cash_accounts.name`, and `payments.ref_id` → a lease or invoice depending on `payments.kind`. None of these are declared constraints.
- There are no views or triggers. The only indexes are the automatic ones for the primary keys on `inventory`, `pricing` and `cash_accounts`.

### How the tables connect

```
                    desk (date_today = "today")
                              │  anchors every due-date / overdue check
                              ▼
 ┌──────────────────────── tickets ────────────────────────┐
 │ sku (+size)            lease_id (FK)       invoice_id (FK)
 ▼                          ▼                     ▼
inventory ◄─sku─► pricing  leases              invoices ──vendor_id (FK)──► vendors
                            │                     │
                            └──── paid via ───────┘
                                     ▼
                                 payments ──account──► cash_accounts
```

---

## 2. Tables and fields

### `desk`: the shop's "today"
| Field | Type | Current value |
|---|---|---|
| `date_today` | TEXT, required | `2026-08-31` |
| `notes` | TEXT | empty |

**Why agents need it:** this is the shop's simulated current date. Agents should use it instead of the system clock when deciding whether something is overdue or coming due. Against `2026-08-31`, invoice 501 (due `2026-08-28`) is 3 days overdue, and the lease (due `2026-09-02`) is due in 2 days. `notes` could hold a shift log or handoff notes **(inferred)**.

### `tickets`: incoming work
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | 101, 102, 103 |
| `type` | TEXT, required | `customer_order`, `rent_notice`, `price_override` |
| `requester` | TEXT, required | who raised it: a customer, landlord or student org |
| `subject` | TEXT, required | short title |
| `sku`, `size`, `qty` | TEXT / TEXT / INTEGER | used by product tickets (101, 103) |
| `lease_id` | INTEGER FK → `leases.id` | used by ticket 102 |
| `invoice_id` | INTEGER FK → `invoices.id` | used by ticket 101 |
| `status` | TEXT, required | all three are `open` |
| `notes` | TEXT | the free-text request |
| `created_at` | TEXT | ISO 8601 with `-04:00` offset |

**Why agents need it:** this is the work queue. `type` decides which agent handles a ticket, and the optional columns link it to the rest of the database. Only the columns relevant to a ticket's type are filled in.

### `inventory`: stock by SKU and size
| Field | Type | Notes |
|---|---|---|
| `sku` | TEXT | part of the PK |
| `name` | TEXT | product name |
| `size` | TEXT | part of the PK: `S`/`M`/`L`/`XL`, or `OS` (one size) |
| `qty` | INTEGER | units on hand |
| `location` | TEXT | aisle |

| SKU | Name | S | M | L | XL | OS | Location |
|---|---|---|---|---|---|---|---|
| CC-HOOD-NAVY | Basic Hoodie Big Yale | 4 | 8 | 14 | 6 | | Aisle A |
| CC-TEE-WHITE | Classic Bulldog Tee | **0** | 5 | 3 | 2 | | Aisle B |
| CC-HAT-BLUE | Yale Cap | | | | | 40 | Aisle C |
| CC-MUG-CREST | Crest Mug | | | | | **0** | Aisle D |

**Why agents need it:** to check whether an order can be filled, by size, and to update stock after a sale. Two items are out of stock: Tee S (needed by ticket 101) and the Crest Mug.

### `pricing`: cost and price per SKU
| SKU | `unit_cost` | `list_price` | Margin per unit |
|---|---|---|---|
| CC-HOOD-NAVY | 22.00 | 58.00 | 36.00 (62%) |
| CC-TEE-WHITE | 8.00 | 28.00 | 20.00 (71%) |
| CC-HAT-BLUE | 6.00 | 22.00 | 16.00 (73%) |
| CC-MUG-CREST | 3.50 | 14.00 | 10.50 (75%) |

**Why agents need it:** to quote prices and to judge discount requests. `unit_cost` is the floor below which a sale loses money. Pricing is per SKU, not per size.

### `vendors`: suppliers
| `id` | `name` | `specialty` | `lead_days` |
|---|---|---|---|
| 1 | Bulldog Print Co | apparel reprint | 5 |
| 2 | Elm City Gifts | mugs and small goods | 3 |
| 3 | QuickShip CT | local courier | 1 |

**Why agents need it:** to know who invoice 501 is owed to, and how long a restock would take. Bulldog Print Co needs 5 days for apparel. Vendors 2 and 3 aren't referenced by any current invoice or ticket. They're possible options for restocking the mug or for fast delivery **(inferred)**.

### `leases`: the shop's rent obligation
| `id` | `space_name` | `landlord` | `monthly_rent` | `next_due` | `notes` |
|---|---|---|---|---|---|
| 1 | Chapel Street shop | Elm City Properties | 2400.00 | 2026-09-02 | empty |

**Why agents need it:** to confirm a rent notice is real (the landlord and amount should match) and to know when it's due. Ticket 102's requester, Elm City Properties, matches the lease's landlord.

### `cash_accounts`: money available
| `name` | `balance` | `date` |
|---|---|---|
| checking | 3400.00 | 2026-08-31 |

**Why agents need it:** to check whether the shop can afford a payment before making it. `date` is when the balance was last recorded, and it matches `desk.date_today`.

### `payments`: payment log (empty)
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `kind` | TEXT, required | type of payment; no values exist yet. Likely `rent` / `invoice` **(inferred)** |
| `ref_id` | INTEGER | the lease or invoice being paid, depending on `kind`. Not a declared FK |
| `amount` | REAL, required | |
| `account` | TEXT, required | should match a `cash_accounts.name`, such as `checking`. Not a declared FK |
| `paid_at` | TEXT, required | |
| `approved_by` | TEXT, required | who approved the payment |

**Why agents need it:** this is where an agent records a payment it makes. Because `approved_by` is required, every payment needs a named approver. That points to a human approval step before money moves **(inferred)**. Recording a payment doesn't update `cash_accounts.balance`, `invoices.status` or `leases.next_due` on its own, since there are no triggers. The tool has to update those as well.

### `invoices`: bills owed to vendors
| `id` | `vendor_id` | `amount` | `due_date` | `status` | `description` |
|---|---|---|---|---|---|
| 501 | 1 (Bulldog Print Co) | 840.00 | 2026-08-28 | open | Rush reprint CC-TEE-WHITE S |

**Why agents need it:** to know what's owed, to whom and by when. Invoice 501 is already 3 days overdue, and it's directly tied to ticket 101's out-of-stock tee.

---

## 3. The three open tickets, traced through all nine tables

All three tickets are `open`, and they're the only rows in `tickets`.

### Ticket 101: customer order, Bulldog tee (Tauhid Zaman)
*Request:* 1 × CC-TEE-WHITE, size S. *Notes:* "Needs a tee in size S."

| Table | What it shows |
|---|---|
| `tickets` | `sku`=CC-TEE-WHITE, `size`=S, `qty`=1, `invoice_id`=501 |
| `inventory` | CC-TEE-WHITE / S has **0** on hand (Aisle B). The order can't be filled from stock. M has 5, L has 3, XL has 2 |
| `pricing` | List price 28.00, cost 8.00 |
| `invoices` | 501: 840.00 to vendor 1 for "Rush reprint CC-TEE-WHITE S". Still `open`, due 2026-08-28 |
| `vendors` | Vendor 1 is Bulldog Print Co (apparel reprint, 5 lead days) |
| `desk` | Today is 2026-08-31, so invoice 501 is 3 days overdue |
| `cash_accounts` | Checking has 3400.00, enough to cover 840.00 |
| `payments` | Nothing recorded yet. Paying 501 would add a row here with `ref_id`=501 |
| `leases` | Not linked directly. But paying 501 competes with rent for the same cash (see the summary below) |

**What this means:** the S tee is out of stock, and the reprint that would restock it is on an unpaid, overdue invoice. Filling the order probably depends on paying invoice 501 and waiting about 5 days for the reprint **(inferred)**.

### Ticket 102: rent notice (Elm City Properties)
*Notes:* "Email: shop rent due in 2 days."

| Table | What it shows |
|---|---|
| `tickets` | `lease_id`=1. No SKU or invoice |
| `leases` | Lease 1: Chapel Street shop, landlord Elm City Properties, rent 2400.00, next due 2026-09-02 |
| `desk` | Today is 2026-08-31, so rent is due in 2 days. That matches the ticket |
| `cash_accounts` | Checking has 3400.00, enough to cover 2400.00 |
| `payments` | Nothing recorded yet. Paying rent would add a row with `ref_id`=1 and an `approved_by` name |
| `vendors` / `invoices` | Not involved. The landlord is a lease party, not a vendor, and rent isn't billed through `invoices` |
| `inventory` / `pricing` | Not involved |

**What this means:** the notice checks out. The requester matches the landlord, and the date matches `next_due`. The one open question is the amount, which isn't in the ticket and comes from `leases.monthly_rent`.

### Ticket 103: price override, bulk hoodie discount (Yale AI Club)
*Request:* 20 × CC-HOOD-NAVY, size M, at a bulk discount.

| Table | What it shows |
|---|---|
| `tickets` | `sku`=CC-HOOD-NAVY, `size`=M, `qty`=20. No discount amount is specified |
| `inventory` | CC-HOOD-NAVY / M has **8** on hand (Aisle A), **12 short** of 20. The hoodie has 32 across all sizes (S 4, M 8, L 14, XL 6) |
| `pricing` | List price 58.00, cost 22.00. 20 at list price is 1,160.00, and 20 at cost is 440.00. The most the shop could discount without losing money is 36.00 per unit, or 62% |
| `vendors` | Bulldog Print Co (apparel reprint, 5 lead days) is the only apparel vendor and could supply the missing 12 **(inferred)** |
| `desk` | Today is 2026-08-31. Any restock would arrive around 2026-09-05 at the earliest **(inferred from lead_days)** |
| `invoices` / `payments` | Nothing yet. A restock order would presumably create a new invoice **(inferred)** |
| `cash_accounts` / `leases` | Not linked directly. But a restock would be another drain on the same limited cash |

**What this means:** the shop has to decide on two things, a discount and a restock. The discount should stay above cost. The order can't be filled from stock in size M without a restock.

---

## 4. How the tickets interact: cash

The three tickets aren't independent. Two of them need money from the single `checking` account:

| Item | Amount |
|---|---|
| Checking balance (2026-08-31) | 3,400.00 |
| Rent, lease 1 (ticket 102, due 09-02) | −2,400.00 |
| Invoice 501, Bulldog Print Co (ticket 101, overdue since 08-28) | −840.00 |
| **Left after both** | **160.00** |

The shop can pay both, but only 160.00 would be left. That's not enough for a restock of 12 hoodies for ticket 103 (12 × 22.00 = 264.00 at unit cost, before any vendor markup) **(inferred)**. Ticket 103's revenue could change that, but only if the order can be filled. So the agents will need to look across tickets before spending money, not just handle each one on its own.

---

## 5. MCP tools

Server: `mcp_server/server.py` (FastMCP, server name `campus-customs-ops`), over `data/campus_customs_new.db`.

**It's the only way into the database.** The backend has no SQLite code. Agents reach shop data only through these tools, and Claude Code reaches it through `.mcp.json`.

Every tool:
- treats `desk.date_today` as today
- returns live query results; nothing is hardcoded
- uses a read-only connection unless it's an action tool

**Business rules are enforced inside the tools.** Agent prompts also describe them, but the tools are what stop a rule from being broken.

**New table.** The server adds one table to the working database on first write: `approval_requests` (see 5.4). Nothing else in the schema changed.

### 5.1 All tools

| # | Tool | Group | Who can use it | Tables read | Tables written |
|---|---|---|---|---|---|
| 1 | `get_desk_date` | read | all agents | `desk` | none |
| 2 | `list_open_tickets` | read | Boss | `tickets` | none |
| 3 | `get_ticket` | read | all agents | `tickets`, `approval_requests` | none |
| 4 | `check_customer_order_stock_and_restock_invoice` | read (ticket 101) | Inventory, Accounting, Customer Service | `tickets`, `desk`, `inventory`, `pricing`, `invoices`, `vendors`, `payments`, `cash_accounts`, `approval_requests` | none |
| 5 | `verify_rent_notice_against_lease` | read (ticket 102) | Facilities, Accounting | `tickets`, `desk`, `leases`, `payments`, `cash_accounts`, `approval_requests` | none |
| 6 | `evaluate_bulk_discount_request` | read (ticket 103) | Inventory, Accounting, Customer Service | `tickets`, `desk`, `inventory`, `pricing`, `vendors`, `invoices`, `cash_accounts`, `approval_requests` | none |
| 7 | `get_cash_position` | read | Boss, Accounting | `desk`, `cash_accounts`, `invoices`, `vendors`, `leases`, `approval_requests` | none |
| 8 | `list_approval_requests` | read | Boss, Accounting, Customer Service | `approval_requests` | none |
| 9 | `update_ticket_status` | agent action | Inventory, Accounting, Facilities, Customer Service | `desk`, `tickets`, `approval_requests` | `tickets` (status, notes) |
| 10 | `request_payment_approval` | agent action | Accounting | `desk`, `cash_accounts`, `tickets`, `invoices`, `leases`, `approval_requests` | `approval_requests`, `tickets.notes` |
| 11 | `request_price_override_approval` | agent action | Accounting | `desk`, `tickets`, `pricing`, `approval_requests` | `approval_requests`, `tickets.notes` |
| 12 | `ship_customer_order` | agent action | Inventory | `desk`, `tickets`, `invoices`, `inventory` | `inventory.qty`, `tickets` |
| 13 | `decide_approval_request` | **human only** | no agent | `desk`, `approval_requests` | `approval_requests`, `tickets.notes` |
| 14 | `execute_approved_payment` | **human only** | no agent | `desk`, `approval_requests`, `cash_accounts`, `invoices`, `leases`, `tickets` | `payments`, `cash_accounts`, `invoices.status` or `leases.next_due`, `approval_requests`, `tickets` (status, notes) |
| 15 | `list_tickets` | read (P7) | backend API only | `tickets`, `approval_requests` | none |
| 16 | `reset_working_database` | **human only** (P7) | no agent | `campus_customs.db` (original), `desk`, `cash_accounts` | the whole working database (restored from the original) |

"Who can use it" is enforced by per-agent allowlists in `backend/mcp_client.py`. An agent never sees a tool that isn't on its list, and no list includes the three human-only tools. The FastAPI backend (section 13) calls the human-only and backend-only tools only from its human routes.

### 5.2 The ticket tools and why they matter

**`check_customer_order_stock_and_restock_invoice`: ticket 101**
- **Returns:**
  - stock for the requested SKU and size, the shortfall, and other sizes
  - the price and order total
  - the linked invoice joined to its vendor, with days overdue, payments recorded and the earliest restock date if paid today
  - cash balances, and the ticket's approval requests
- **Why it matters:** size S has 0 in stock, so stock alone only says "no". The tool also follows `tickets.invoice_id` to invoice 501, the $840 rush reprint of that exact item. That shows the reprint is overdue and that Bulldog Print Co needs about 5 days after payment. The agent can then give a real answer: offer another size, or explain the reprint and its earliest date, and flag that 501 needs paying.

**`verify_rent_notice_against_lease`: ticket 102**
- **Returns:** the linked lease; whether the requester matches the landlord; rent, due date and days until due; rent payments recorded; balances before and after rent; and the ticket's approval requests.
- **Why it matters:** the notice asks for money but doesn't say how much. The tool supplies the amount ($2,400) from the lease, confirms the sender is the real landlord and the date matches `desk.date_today`, and checks rent hasn't already been paid. It also shows only $1,000 would be left afterwards.

**`evaluate_bulk_discount_request`: ticket 103**
- **Returns:**
  - stock and the shortfall, with other sizes
  - cost, list price, margin and the largest discount that still covers cost
  - totals at list price and at cost, and the cost of restocking the shortfall
  - every vendor with its specialty, lead time and arrival date (`vendors_check_specialty`). Not every vendor can supply apparel: one is a courier
  - open invoices, cash balances, and the ticket's approval requests
- **Why it matters:** the club asks for "a bulk discount" without naming a figure, and wants 20 in size M when only 8 are in stock. The tool sets the limits for any offer: at most $36 off a hoodie (62%) without a loss. It also shows a 12-unit shortfall that would cost at least $264 to restock, with the earliest arrival around 2026-09-05. Open invoices and cash show the money is already committed elsewhere.

### 5.3 Tools added in P5

| Tool | Ticket(s) | Why it's needed |
|---|---|---|
| `get_desk_date` | all | Gives agents "today" from `desk.date_today`, so overdue and due-soon checks never use the computer's clock. |
| `list_open_tickets` | all | Lets the Boss see the queue and route by `type` and content, instead of every agent reading every ticket. |
| `get_ticket` | all | One ticket's full record and approval requests, so specialists can check a ticket's current state before acting. |
| `get_cash_position` | 101, 102, 103 together | The cross-ticket view from section 4: paying 501 ($840) and rent ($2,400) together leaves $160. The P3 tools only saw one ticket at a time. |
| `list_approval_requests` | 101, 102, 103 | Shows what's already waiting on a human, so agents don't file duplicates and the Boss can list what the owner must decide. |
| `update_ticket_status` | 101, 102, 103 | Records progress on the ticket with a dated note: `waiting_on_vendor`, `waiting_on_customer`, `awaiting_human_approval` or `resolved`. |
| `request_payment_approval` | 101 (invoice 501), 102 (lease 1 rent) | Files a payment for human approval. The amount comes from the database, not the agent. |
| `request_price_override_approval` | 103 | Files a discounted unit price for human approval. It refuses anything below unit cost. |
| `ship_customer_order` | 101 | Ships a customer order, refusing if the linked invoice is unpaid or stock is short. |
| `decide_approval_request` | 101, 102, 103 | **Human only.** The owner approves or rejects a request. |
| `execute_approved_payment` | 101, 102 | **Human only.** Pays an approved request and updates every affected table in one transaction. |

### 5.4 `approval_requests` (added by the MCP server)

| Field | Meaning |
|---|---|
| `id` | Request number the agents quote, e.g. "request #2" |
| `kind` | `invoice_payment`, `rent_payment` or `price_override` |
| `ticket_id`, `ref_id` | The ticket, and the `invoices.id` or `leases.id` being paid |
| `amount` | Payment amount from the database, or the proposed unit price |
| `account` | `cash_accounts.name` to pay from |
| `details` | JSON of the figures the request was based on: balance and balance after, days overdue, margin, discount % |
| `reason`, `requested_by` | Why, and which agent filed it |
| `status` | `pending` → `approved` / `rejected` → `executed` (payments only) |
| `decided_by`, `decision_note`, `decided_at` | The human who decided |
| `created_at` | When it was filed |

---

## 6. The five agents

Code is in `backend/`:

| File | What it holds |
|---|---|
| `agents.py` | The agents, delegation and loop auditing |
| `desk.py` | The runner and command line |
| `models.py` | Shared data types |
| `mcp_client.py` | The MCP connection and per-agent tool allowlists |
| `audit.py` | The audit trail |
| `config.py` | Model and limits |
| `prompts/` | The instruction files |

**Model:** every agent uses **gpt-6-luna** through Portkey (`PORTKEY_API_KEY`), via the OpenAI Responses API. The model name is fixed in `config.py`, not left to an environment override.

**Instructions:** each agent's instructions are its own prompt file, plus the shared `prompts/shop_rules.md`, plus a short "this run" note giving its name, where it sits in the delegation chain, and whether it can still delegate.

| Agent | Prompt | Responsibilities | MCP tools | Can delegate to |
|---|---|---|---|---|
| **Boss** | `boss.md` | Reads the open tickets, assigns each to one lead specialist, checks the combined cash picture, writes the `DeskReport` for the owner. Doesn't work tickets or change data. | `get_desk_date`, `list_open_tickets`, `get_ticket`, `get_cash_position`, `list_approval_requests` | Any specialist, via `assign_ticket` |
| **Inventory** | `inventory.md` | Stock by SKU and size, shortfalls and alternatives, restock timing from vendor `lead_days`, shipping cleared orders. | `get_desk_date`, `get_ticket`, ticket tools 101 and 103, `ship_customer_order`, `update_ticket_status` | Accounting, Customer Service |
| **Accounting** | `accounting.md` | Cash, invoices, overdue priority, payment requests, pricing and discount (price override) requests. The only agent that can file a request. | `get_desk_date`, `get_ticket`, `get_cash_position`, `list_approval_requests`, all three ticket tools, `request_payment_approval`, `request_price_override_approval`, `update_ticket_status` | Inventory, Customer Service, Facilities |
| **Facilities** | `facilities.md` | Lease and landlord: verifies a rent notice's sender, amount and date against the lease before any payment is requested. | `get_desk_date`, `get_ticket`, `verify_rent_notice_against_lease`, `update_ticket_status` | Accounting, to file the rent request |
| **Customer Service** | `customer_service.md` | The requester's side: understands the request and drafts an honest reply (never sent automatically) with real alternatives. | `get_desk_date`, `get_ticket`, ticket tools 101 and 103, `list_approval_requests`, `update_ticket_status` | Inventory, Accounting |

**Routing.** The Boss gives each ticket to one lead, never to all five:
- `customer_order` → Customer Service
- `rent_notice` → Facilities
- `price_override` → Accounting

Leads bring in a colleague with `ask_colleague` only for work that's that colleague's responsibility. For example, Facilities can't file payments, so it asks Accounting.

**Tickets are worked one at a time.** `assign_ticket` is a sequential tool, so the next ticket starts only after the previous lead reports back. Each agent therefore sees what earlier agents filed through the MCP tools; for example, Accounting sees payment requests already waiting before it files another. The Boss also does a final check: anything blocking left without action (such as an overdue invoice with no payment request) is sent to Accounting once.

**`handled_by` comes from the record, not the model.** After the run, `desk.py` rebuilds each ticket's `handled_by` from the actual delegations, and logs any correction to the audit trail.

**Shared data types** (`backend/models.py`):

| Type | What it is |
|---|---|
| `SpecialistReport` | A specialist's output: findings, actions taken, blockers, approvals needed, recommended next steps, draft customer message |
| `DeskReport` / `TicketOutcome` | The Boss's output |
| `ApprovalNeeded` | Something a human must decide |
| `Delegation` | One agent handing work to another |
| `AuditEvent` | One audit trail record |
| `RunUsage` | Token and request usage for a run |
| `DeskRunResult` | Everything a desk run returns |

---

## 7. Safeguards around payments and business decisions

| Rule | Where it's enforced |
|---|---|
| **No agent can approve or execute a payment.** | `decide_approval_request` and `execute_approved_payment` are on no agent's allowlist (`mcp_client.py`, checked at import). Both tools also refuse an agent name as the decider or executor. |
| **Payments need human approval first.** | `execute_approved_payment` only runs on a request a human set to `approved`. `payments.approved_by` is filled with that human's name. |
| **Amounts can't be invented.** | `request_payment_approval` takes the amount from `invoices.amount` or `leases.monthly_rent`. The agent can't pass one. |
| **No double payments.** | Refuses an invoice that's already paid, and refuses a second request while one is pending or approved. Execution re-checks the invoice is still unpaid. |
| **No paying beyond the balance.** | `execute_approved_payment` refuses if the account can't cover the amount. Requests record `sufficient_funds` and `balance_after`. |
| **Proposed payments don't touch cash.** | Agents' requests are only `pending` rows in `approval_requests`. The balance changes only in `POST /api/approvals/{id}/approve`, after a named human approves (verified in P7: $3,400 stayed $3,400 until approval). |
| **Paying moves the ticket on.** | In the same transaction, a paid rent request resolves its `rent_notice` ticket, and a paid restock invoice moves its `customer_order` to `waiting_on_vendor`. This only happens if nothing else on the ticket is still waiting on a human. |
| **Reset is human-only.** | `reset_working_database` needs `confirm=true` and a human's name, and is refused while an agent run is in progress. |
| **Payments are all-or-nothing.** | Inserting the payment, lowering the balance, marking the invoice paid or advancing `next_due`, and closing the request all happen in one SQLite transaction. |
| **Overdue is measured from `desk.date_today`.** | Every tool computes `days_overdue` and `days_until_due` from `desk`. The prompts forbid using the clock. |
| **No shipping on unpaid invoices or short stock.** | `ship_customer_order` refuses if the linked invoice isn't `paid`, or stock is short for the exact SKU and size. |
| **No selling below cost; discounts need a human.** | `request_price_override_approval` refuses prices below `unit_cost` or at/above list price. Only a human can approve. Prompts forbid quoting an unapproved price. |
| **Tickets can't be closed with decisions pending.** | `update_ticket_status` refuses `resolved` while the ticket has a pending or approved request, refuses changes to closed tickets, and requires a note. |
| **Customer messages are drafts.** | No tool sends messages. The `customer_message` field is for a human to review. |
| **Foreign keys checked.** | The database doesn't enforce them, so action tools check that tickets, invoices, leases and accounts exist, and write connections turn on `PRAGMA foreign_keys`. |

---

## 8. Limits on agent loops and tokens

All are set in `backend/config.py` and can be overridden in `.env`:

| Limit | Default | What happens when it's hit |
|---|---|---|
| Delegation depth | 2 (Boss → specialist → colleague) | The delegation is refused, and the agent reports with what it has |
| Delegations per run | 8 | Further delegations are refused |
| No self- or loop-delegation | always | Delegating to yourself or to anyone already up the chain is refused, so A → B → A can't happen |
| Boss per-run limits | 12 model requests, 15 tool calls, 100,000 tokens | PydanticAI `UsageLimits` stops the Boss, and the run ends with an error result |
| Specialist per-run limits | 8 model requests, 10 tool calls, 60,000 tokens | That specialist stops. Its caller gets a `limit_reached` result and carries on |
| Team token budget | 300,000 tokens across every agent in a run | Checked after every model response. The whole run stops |
| Model call timeout | 120 s, with 1 retry | A stuck request can't hang the run |

Every limit hit is written to the audit trail as a `limit_reached` event.

---

## 9. Audit trail (`output/audit_trail.json`)

**Format.** One JSON array of `AuditEvent` records. Each has:
- `event_id`, `run_id`, `seq` and `timestamp`
- `agent` and `kind`
- `ticket_id`
- `delegation_chain`, e.g. `["boss", "facilities", "accounting"]`
- `details`

**Appending.** Each event is appended as it happens. The file is read, the event added, and the file replaced atomically under a file lock. Earlier events are never removed or rewritten.

**Event kinds:**

| Kind | When it's logged |
|---|---|
| `run_start` | A desk run begins: the message, model and all limits |
| `agent_start` | An agent begins a task: its prompt and limits |
| `model_response` | Each loop step: the model's text, which tools it called, and token usage including the team running total |
| `tool_call` / `tool_result` | Every MCP tool and delegation tool call, with its arguments and what it returned. Refusals and errors are marked `ok: false` |
| `delegation` / `delegation_result` | Who handed what to whom, at what depth, and the report or error that came back |
| `decision` | Each agent's final structured report. Its `final_result` tool call has no separate `tool_result` |
| `limit_reached` / `error` | Something was stopped or failed |
| `run_end` | The run finishes: success, number of delegations, and usage by agent |

The file starts as `[]`.

**Running the desk.** From `backend/`, run:

```bash
../.venv/bin/python desk.py
```

Use `--ticket 102` to handle a single ticket.

---

## 10. Verification run (P5)

To check the system without changing the working database or the real audit trail, it was run end to end on scratch copies (`CAMPUS_CUSTOMS_DB` and `AUDIT_PATH` pointed at temporary files) with gpt-6-luna through Portkey.

**Routing and delegation:**
- The Boss assigned 101 → Customer Service, 102 → Facilities and 103 → Accounting.
- Each lead brought in exactly one colleague:
  - Customer Service → Accounting, for the unpaid invoice
  - Facilities → Accounting, to file the rent payment request
  - Accounting → Customer Service, for the club's reply
- 6 delegations in total, none refused.

**What the agents filed and did:**
- **Ticket 101:** payment request for invoice 501 ($840, 3 days overdue). No shipping attempted.
- **Ticket 102:** rent request for lease 1 ($2,400, due 2026-09-02), after Facilities matched the landlord, amount and date.
- **Ticket 103:** price override at $52.00 a hoodie (10.3% off, still $30 above cost). The agents flagged that only 8 of the 20 are in stock.
- All three tickets were set to `awaiting_human_approval`.
- No payment was made, and the balance stayed at $3,400.

**Desk report:** the Boss's cash summary noted that paying both requests would leave $160. It listed the three approvals for the owner, overdue invoice first.

**Audit trail and usage:**
- 113 audit events: 26 model responses and 33 tool calls (26 MCP or delegation calls with results, plus 7 `final_result` reports).
- 0 failed tool calls and 0 limits hit.
- 90,494 tokens in total, under the 300,000 budget.

**Separate check of the server's rules** (scratch copy, called directly through the MCP server):
- shipping 101 is refused while invoice 501 is unpaid
- agent names are refused as approvers
- unapproved payments can't execute
- a price below cost is refused
- duplicates are refused
- an approved payment updates `payments`, `cash_accounts`, `invoices` and `leases` together

---

## 11. Notes

- **Ticket `type` is the routing key.** It decides the lead agent (section 6). Statuses now include `in_progress`, `waiting_on_vendor`, `waiting_on_customer`, `awaiting_human_approval`, `resolved` and `shipped`.
- **`payments.kind` values are now defined** as `invoice` and `rent`, and `ref_id` is the `invoices.id` or `leases.id`.
- **A real run changes the working database.** Running the desk against `data/campus_customs_new.db` files approval requests and updates ticket statuses and notes. The original `data/campus_customs.db` is never touched, so it can be copied over the working copy to start fresh.
- **Paying invoice 501 doesn't restock size S by itself.** `ship_customer_order` will keep refusing ticket 101 until stock arrives. No tool records a delivery yet.

---

## 12. Collaboration review (P5 follow-up)

I checked the audit trail to confirm the agents really delegate and build on each other's work, rather than each running alone.

### What was already working (first run)
- **Handoffs carried facts.** Every delegation task included concrete figures, for example: "Lease monthly_rent is 2400.00, next due date is 2026-09-02… Please file a rent payment approval request".
- **Results came back and were used.** Facilities' and Customer Service's reports cited the request numbers Accounting filed for them. Customer Service's draft reply for ticket 103 was passed unchanged through Accounting into the Boss's report.

### Problems found, and fixes

| # | Problem (evidence in the audit trail) | Fix |
|---|---|---|
| 1 | **The leads ran in parallel.** The Boss called `assign_ticket` three times in one response. All three leads started (audit seq 13, 15, 17) before any finished, so three Accounting runs filed requests without seeing each other's. | `assign_ticket` is now `sequential=True`, and the Boss assigns the most urgent ticket first. The Accounting prompt now adds requests already waiting (`payment_requests_awaiting_human`) to the new amount when checking cash. |
| 2 | **Restock planning skipped Inventory and got the vendor wrong.** On ticket 103, Accounting read the vendor list itself and offered QuickShip CT (a local courier) and Elm City Gifts (mugs) as hoodie restock options, arriving "as early as 2026-09-01". Inventory was never consulted. | Accounting must now ask Inventory whenever an order can't be filled from stock. Inventory must pick a vendor by `specialty`. The tool field was renamed from `restock_vendors` to `vendors_check_specialty`, and its description warns that one vendor is a courier. |
| 3 | **A required escalation was skipped** (second run). Customer Service saw that invoice 501 was unpaid and overdue, set ticket 101 to `waiting_on_vendor`, and never asked Accounting. No payment request was filed, so the order would never unblock. | The Customer Service prompt now *requires* asking Accounting when an unpaid invoice blocks an order and no request exists, because only Accounting can file one. The Boss now checks that nothing blocking was left untouched, and sends any such item to Accounting once. |
| 4 | **The Boss's report misstated who worked a ticket** (second run). It said ticket 101 was handled by Customer Service, Inventory and Accounting, but there were no delegations from Customer Service at all. In the third run it under-reported instead. | `desk.py` now rebuilds `handled_by` from the delegation record, and logs any correction as a `decision` event with the claimed and actual lists. |

### Verification run after the fixes (scratch copies)

**Delegations,** in order:
1. Boss → Facilities (102)
2. Facilities → Accounting (102)
3. Boss → Customer Service (101)
4. Customer Service → Accounting (101)
5. Boss → Accounting (103)
6. Accounting → Inventory (103)

All six completed, and no limits were hit.

**What changed:**
- **Each ticket waited for the previous one.** When Accounting checked cash for ticket 101, it saw the rent request just filed for ticket 102, and reported that the invoice could be covered "alongside the existing obligations".
- **Inventory picked the right vendor.** It chose Bulldog Print Co as the only apparel vendor ("the other listed vendors do not supply apparel stock"), with the earliest arrival on 2026-09-05. Accounting used that in its report.
- **All three requests were filed:** rent $2,400, invoice 501 $840 and a $52 hoodie price. All three tickets reached `awaiting_human_approval`, and no payments were made.
- **`handled_by` was corrected on all three tickets.** The Boss had listed only the lead each time, and the delegation record added the colleague.
- **Usage:** 93,598 tokens over 26 model requests.

**Remaining observation:** the Boss assigned 102 (rent due in 2 days) before 101 (an invoice already 3 days overdue). Both requests were filed in the same run, so nothing was missed, but ordering is still the model's judgment.

---

## 13. FastAPI backend (P7)

**Code:** `backend/main.py`. Start it from `backend/` with `uvicorn main:app --reload --port 8000`, with `Homeworks/5/.venv` active, or run `../.venv/bin/uvicorn main:app --reload --port 8000`. Vite's dev server on port 5173 is allowed through CORS.

**MCP-only.** Every route that reads or changes shop data calls an MCP tool through one long-lived MCP client (`mcp_client.ShopMCP`), started with the app. Agent runs use the agents' own filtered toolsets. A search of `backend/` finds no `sqlite3` or SQL. The only file the backend reads directly is `output/audit_trail.json`, its own log.

**One run at a time.** Agent runs and resets share a lock, because they change the same working database. A second run, or a reset during a run, gets a `409`.

### The six capabilities

| # | Capability | Route(s) | What it does | MCP tools behind it |
|---|---|---|---|---|
| 1 | **Tickets with open/resolved status** | `GET /api/tickets` (and `GET /api/tickets/{id}`) | Returns all tickets with their raw `status`, a simple `state` (`resolved` once resolved or shipped, otherwise `open`), their approval requests, and counts of open and resolved tickets. | `list_tickets`, `get_ticket` |
| 2 | **Run the agent team on a ticket** | `POST /api/tickets/{id}/run` (optional body `{"message": "..."}`) | Runs the Boss on that one ticket. The Boss delegates as in P5, and every step goes to the audit trail. The call waits for the run (about 40–50 s) and returns the `DeskRunResult` (report, delegations, token usage) plus the ticket afterwards. Returns `404` for an unknown ticket, and `409` if the ticket is already closed or a run is in progress. | The agents' tools; `get_ticket` |
| 3 | **Recent agent activity** | `GET /api/activity?limit=&run_id=&ticket_id=` | Reads the audit trail and returns, newest first: `runs` (status and tokens), `messages` (tasks, model text, reports), `delegations` (who asked whom, task, status, reply summary), `tool_calls` (each MCP or delegation call with args, `ok` and result), `mcp_tools_used`, and `human_actions`. | none (audit file) |
| 4 | **Human approval of a proposed payment or purchase** | `POST /api/approvals/{id}/approve` `{"approved_by", "note"}`; also `POST /api/approvals/{id}/reject` `{"rejected_by", "note"}` and `GET /api/approvals?status=` | **The only place money moves.** For an invoice payment (a vendor purchase, such as the 501 reprint) or a rent payment, the route checks the account can cover it, approves it, then executes it in one MCP transaction. That writes `payments` (with `approved_by`), lowers `cash_accounts`, marks the invoice paid or moves the lease's due date, and moves the ticket on. A price override is only approved; no money moves. Agent names are refused, and approving twice returns `409`. Each decision is logged as a `human_action`. | `list_approval_requests`, `get_cash_position`, `decide_approval_request`, `execute_approved_payment` |
| 5 | **Checking balance** | `GET /api/cash` | `checking_balance` from `cash_accounts` and its `as_of` date, plus unpaid invoices, rent due, payment requests waiting on a human, total obligations, and cash left after all of them. | `get_cash_position` |
| 6 | **Reset the working database** | `POST /api/reset` `{"confirm": true, "requested_by"}` | Copies the original `campus_customs.db` over the working copy with SQLite's backup API. That removes payments, requests, status changes and the `approval_requests` table. Needs `confirm` and a human's name, and is refused during a run. The audit trail isn't cleared (it's append-only); the reset is logged in it. | `reset_working_database` |

`GET /api/health` also reports the model, `desk.date_today`, and whether a run is in progress.

**Added in P8 for the dashboard:**
- `POST /api/tickets/{id}/run/stream` runs the team like `/run`, but streams every audit event live as Server-Sent Events: `started`, then one `audit` event per agent step, then `result` (or `error`). The run finishes even if the browser disconnects.
- `GET /api/runs/{run_id}/events` returns one run's raw audit events, so the dashboard can redraw a past run.

**Also added in P8:** a human's decision now moves the ticket on. Approving a price override, or rejecting any request, sets a ticket at `awaiting_human_approval` back to `in_progress` for the agents to follow up, unless other requests on it are still waiting. An approved payment is left for `execute_approved_payment`, which resolves the ticket or moves it to `waiting_on_vendor` once the money has moved.

**CORS:** `http://localhost:5173` and `http://127.0.0.1:5173` are allowed, for the Vite dashboard in `frontend/`. Its design is described in `output/design.md`.

### Verified (P7, on scratch copies of the database and audit trail, through the real uvicorn server)

**Read routes and errors:**
- `/api/tickets` showed 3 open; `/api/cash` showed $3,400, with $3,240 in obligations leaving $160.
- An unknown ticket returned `404`, as did an unknown approval. A reset without `confirm` returned `409`.

**Agent runs through the API:**

| Ticket | Delegation | Request filed | Time | Tokens |
|---|---|---|---|---|
| 102 | Boss → Facilities → Accounting | rent, `pending` | 42 s | 30,059 |
| 103 | Boss → Accounting → Inventory | price override | 50 s | 40,307 |
| 101 | Boss → Customer Service → Accounting | invoice 501, `pending` | 42 s | 37,093 |

**Approvals:**
- **Cash stayed at $3,400 while the rent request was pending.** Approving as `accounting` returned `409`.
- **Approving as "Shop Owner"** paid the rent. Checking went from $3,400 to $1,000, `leases.next_due` became 2026-10-02, and `payments` gained a row with `approved_by` = Shop Owner. Approving again returned `409`.
- **Rejecting the price override** left cash unchanged.

**Locks:** a reset during the ticket 101 run returned `409`, and so did a second run.

**Reset:**
- All three tickets went back to `open`, the requests were cleared, and checking returned to $3,400.
- `sqlite3 .dump` was identical to the original. Only the file header's change counter differs.
- All 148 audit events were kept.

**Ticket states after payment:** approving rent resolved ticket 102, and approving invoice 501 moved ticket 101 to `waiting_on_vendor`. `/api/tickets` then reported 1 resolved and 2 open.

### Audit-trail fix found while testing
When an agent called a tool in the same response as its final report (for example, Accounting's `update_ticket_status` on ticket 102), the tool ran but its result wasn't logged, because the loop ended first. Two changes fixed this:
- Every agent now uses `end_strategy="exhaustive"`, so actions requested alongside a final report always run.
- `run_agent` logs any tool results it finds in the message history after the loop.

After the fix, every non-`final_result` tool call in a run has a matching `tool_result`.

---

## 14. Final system and the P9 desk run

### The system as it stands
```
React dashboard (frontend/, Vite :5173)
   │  REST + Server-Sent Events (live run stream)
   ▼
FastAPI backend (backend/main.py, uvicorn :8000) ── appends every step ──► output/audit_trail.json
   │  agent runs: Boss + 4 specialists on gpt-6-luna via Portkey (backend/agents.py)
   │  human routes: approve / reject / reset
   ▼
campus-customs-ops MCP server (mcp_server/server.py, stdio) ── the only path to ──► data/campus_customs_new.db
```

**Components:**
- **MCP server:** 16 tools: 9 read, 4 agent action, 3 human-only. All business rules are enforced inside the tools, and `approval_requests` holds proposals until a human decides.
- **Agents:** five agents with per-agent tool allowlists (section 6), sequential ticket assignment, and delegation limits (section 8).
- **Backend:** the six capabilities plus live streaming (section 13).
- **Dashboard:** design described in `output/design.md`.

### What happened in P9 (all from the audit trail and working database)

**Reset and starting balance:**
- The working database was reset to the original at 04:08:22 UTC through `POST /api/reset`, logged as a `human_action`.
- It was verified identical to `data/campus_customs.db` with `sqlite3 .dump`.
- Starting checking balance: **$3,400.00**.

**Runs and approvals,** all from the dashboard and one at a time:

| Time (UTC) | Event | Delegation | Result |
|---|---|---|---|
| 04:08 | Run `474bc48e56c1` on 101 | Boss → Customer Service → Accounting | Request #1 filed: invoice 501, $840 |
| 04:13 | **MM approved #1** | | $840.00 paid; checking $3,400 → $2,560; ticket 101 → `waiting_on_vendor` |
| 04:14 | Run `26a228be3acd` on 101 (re-run) | Boss → Customer Service | Confirmed it's waiting on the reprint; nothing new to approve |
| 04:14 | Run `a23dcc2c3944` on 102 | Boss → Facilities → Accounting | Rent notice verified; request #2 filed: $2,400 |
| 04:15 | **MM approved #2** | | $2,400.00 paid; checking $2,560 → $160; lease due date → 2026-10-02; ticket 102 → `resolved` |
| 04:16 | Run `0a956984219f` on 103 | Boss → Accounting, then Accounting → Inventory and Accounting → Customer Service | Price override #3 filed at $52/unit |
| 04:17 | **MM approved #3** | | No money moved; ticket 103 → `in_progress` |

**Overall:**
- 4 runs, 8 hand-offs, 138,370 tokens.
- No tool refusals, limit hits or errors.
- The 193 audit events after the reset were all appended; none were removed.

**Final state:**
- **101:** `waiting_on_vendor`. Not resolved: size S is still 0 in stock.
- **102:** `resolved`.
- **103:** `in_progress`. Not resolved: 12 hoodies short, with no restock funded.

**Cash:** $3,400.00 − $840.00 − $2,400.00 = **$160.00**, which equals `cash_accounts.checking`. **Reconciled.**

**Outputs:**

| File | Contents |
|---|---|
| `output/desk_tickets.html` | Actual sections and the Cash tab filled in; Expected sections from P6 unchanged (checked byte for byte) |
| `output/resolved_tickets.json` | Per ticket: status, outcome, each agent's contribution, human approvals and flags |
| `output/resolved_board.html` | Real dashboard screenshots, saved in `output/screenshots/` |

### Safeguards observed in the real run
- **No money moved without a human.** Both payments sat `pending` until MM approved them on the dashboard. The balance changed only at those moments, and `payments.approved_by` = MM on both rows.
- **Approving a price moved no money.** The balance stayed at $160.00 after #3.
- **Overdue was measured from the desk date.** Invoice 501 was "3 days overdue" from `desk.date_today` (2026-08-31).
- **No order shipped.** Nothing was shipped for 101 while stock was 0; no agent even attempted `ship_customer_order`.
- **The team saw each other's work.** The 102 run saw invoice 501 already paid, because ticket runs are sequential and state is shared through MCP.

### Known gaps and flags
1. **No way to record a restock arriving.** No MCP tool records a delivery. Ticket 101 stays at `waiting_on_vendor` until someone restocks size S and re-runs it.
2. **No purchase-order tool.** Agents can't propose buying stock, so ticket 103's 12-hoodie shortfall (at least $264 at unit cost) can't be put through the approval flow. Cash ($160) wouldn't cover it anyway.
3. **Accounting missed the restock shortfall.** On ticket 103 it saw $160 in checking but didn't flag that it can't fund the restock; the P6 plan expected it to.
4. **The reset was logged under a descriptive name.** It was done by Claude on the user's instruction and recorded as "Claude (on your P9 instruction)". Every money decision was made by the user on the dashboard as "MM".
