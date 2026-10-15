# Campus Customs: Multi-Agent Operations Desk (HW5)

A five-agent operations system for **Campus Customs**, a small campus apparel shop. A Boss agent routes each open ticket (a customer order, a rent notice, a bulk-discount request) to the right specialist: Inventory, Accounting, Facilities or Customer Service. The specialists work the ticket together through MCP tools over the shop's SQLite database. **No money moves until a human approves it** on the dashboard.

| Layer | Tech | Where |
|---|---|---|
| Database tools | FastMCP server (16 tools), the only path to the data | `mcp_server/server.py` |
| Agents | PydanticAI; Boss + 4 specialists on **gpt-6-luna** via Portkey | `backend/agents.py`, `backend/prompts/` |
| API | FastAPI: tickets, run agents (with live stream), activity, approvals, cash, reset | `backend/main.py` |
| Dashboard | React 19 + Vite + TypeScript (React Compiler, motion, lucide-react) | `frontend/` |

The full design, safeguards and run history are documented in `output/harness.md`. The dashboard's design is explained in `output/design.md`.

## Repository layout

```
hw5/
├── AI_prompts.md            prompt log for P1–P11
├── README.md
├── requirements.txt         Python dependencies (MCP server, agents, API)
├── .env.example             environment variable names (no real values)
├── .gitignore
├── .mcp.json                Claude Code project config for the MCP server
├── data/
│   ├── campus_customs.db        original data (never modified)
│   └── campus_customs_new.db    working copy (all reads/writes)
├── mcp_server/
│   ├── server.py                FastMCP server: campus-customs-ops
│   ├── README.md
│   └── requirements.txt
├── backend/
│   ├── main.py                  FastAPI app
│   ├── models.py                shared Pydantic types
│   ├── agents.py                the five agents, delegation, loop auditing
│   ├── desk.py                  desk runner (also a CLI)
│   ├── mcp_client.py            MCP connection + per-agent tool allowlists
│   ├── audit.py                 append-only audit trail
│   ├── config.py                model, Portkey, loop/token limits
│   └── prompts/                 boss.md, inventory.md, accounting.md,
│                                facilities.md, customer_service.md, shop_rules.md
├── frontend/                    React dashboard (npm run dev → localhost:5173)
└── output/
    ├── harness.md               system documentation (tables, tools, agents, safeguards, P9 run)
    ├── mcp_smoke.json           P4: MCP tools tested through Claude Code
    ├── desk_tickets.html        P6 Expected / P9 Actual / Cash / P10 Reflection
    ├── design.md                P8 dashboard design
    ├── resolved_tickets.json    P9: per-ticket outcome, agent contributions, approvals
    ├── resolved_board.html      P9: dashboard screenshots per ticket
    ├── screenshots/             the PNGs used by resolved_board.html
    ├── audit_trail.json         every agent-loop step and human action (append-only)
    └── github_url.txt           the published repository URL
```

## Setup

You need Python 3.12+ and Node.js 20+ (developed on Python 3.14 and Node 24).

```bash
python3 -m venv .venv
```

```bash
.venv/bin/pip install -r requirements.txt
```

```bash
cd frontend && npm install
```

Then copy the environment template and add your Portkey key:

```bash
cp .env.example .env
```

`PORTKEY_API_KEY` is the only required variable. Everything else in `.env.example` is an optional override; the defaults are shown there. `.env` is git-ignored and must never be committed.

## Reset the working database

`data/campus_customs.db` is the original. All work happens on `data/campus_customs_new.db`. To start over, use any of these:

- **Dashboard:** the **Reset working database** button under "Practice mode".
- **API** (with the backend running):

  ```bash
  curl -X POST localhost:8000/api/reset -H 'content-type: application/json' -d '{"confirm": true, "requested_by": "Your Name"}'
  ```

- **No servers running:**

  ```bash
  cp data/campus_customs.db data/campus_customs_new.db
  ```

The API and dashboard reset uses the MCP tool `reset_working_database` (SQLite backup API) and logs the reset in `output/audit_trail.json`. The audit trail itself is append-only and is never cleared.

## Run it

**1. MCP server.** The backend starts it automatically over stdio, so you don't need to run it yourself to use the dashboard. To run it on its own, from the project root:

```bash
.venv/bin/python mcp_server/server.py
```

Add `--http` to serve it over HTTP at `http://127.0.0.1:8001/mcp` instead. Claude Code picks it up from `.mcp.json`: open the project folder in Claude Code and approve `campus-customs-ops`.

**2. Backend** (FastAPI on port 8000), from `backend/`:

```bash
../.venv/bin/uvicorn main:app --reload --port 8000
```

Or with the virtual environment activated, `uvicorn main:app --reload --port 8000`. API docs are at http://localhost:8000/docs.

**3. Frontend** (Vite on port 5173), from `frontend/`:

```bash
npm run dev
```

Open http://localhost:5173. The dashboard calls the backend at `http://localhost:8000`; the backend allows CORS from `http://localhost:5173`.

**Without the dashboard,** run the agents from the command line, from `backend/`:

```bash
../.venv/bin/python desk.py --ticket 102
```

## Using the dashboard

1. **Pick a ticket and run it.** Select a ticket and press **Run the agent team**. The team graph and activity feed update live as agents work and hand off to each other.
2. **Review what the agents propose.** Payments and price overrides appear under **Awaiting your approval**. Enter your own name; agent names are refused.
3. **Approve or reject.** **Approve & pay** is the only action that moves money. The checking balance updates when you approve.

## Results (P9)

The desk was run on 2026-10-15. Starting checking balance: **$3,400.00**.

| Ticket | Outcome | Human decisions |
|---|---|---|
| 101 · Bulldog tee in size S | `waiting_on_vendor`. **Not resolved:** the reprint is paid, but size S is still out of stock | #1 invoice 501, $840.00, approved |
| 102 · Rent due | `resolved` | #2 rent, $2,400.00, approved |
| 103 · Bulk hoodie discount | `in_progress`. **Not resolved:** price approved, but 12 hoodies short | #3 price override $52/unit, approved (no money moved) |

Ending balance: **$160.00**, reconciled against `cash_accounts`. Details are in `output/resolved_tickets.json` and the Cash and Reflection tabs of `output/desk_tickets.html`.
