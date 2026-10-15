# AI Prompts — Homework 5: Campus Customs Multi-Agent Operations System

This file records the prompts given to the AI coding assistant for each problem, along with any follow-up prompts and a short note on what needed to be clarified or improved.

---

## P1 — Vibe coder prompts

### Prompt

> Today we'll be working in @homeworks/5 P1 —Vibe coder prompts. We will be building a multi-agent operations system for a shop called Campus Customs. The starting database is data/campus_customs.db.
> We'll be using FastMCP for database tools, PydanticAI for the agents, FastAPI for the backend, and React, Vite, and TypeScript for the frontend. All the agents need to use gpt-6-luna through my PORTKEY_API_KEY which you can copy from my .env.example
> To start, create AI_prompts.md with sections for P1 through P11, I will give you a prompt and each problem's title. Record the actual prompts I give you, along with any follow-up prompts and a short explanation of what I needed to clarify or improve. Add this initial prompt under P1, and fill out future sections as we go.

### Follow-up prompts

_None yet._

### What needed clarification / improvement

- This prompt set up the project context: the tech stack (FastMCP, PydanticAI, FastAPI, React + Vite + TypeScript), the model (gpt-6-luna through Portkey), and the starting database.
- It also set up this log so each problem's prompts and fixes are recorded as we go.

---

## P2 — Understand the database

### Prompt

> now onto P2 - Understand the database.  Before building the agents, I want to understand the Campus Customs database and how the information is connected. Make a copy of data/campus_customs.db called data/campus_customs_new.db so we're not changing the original, continue using the new db for .
> Find the three open tickets and see how they link to  all nine tables: desk, tickets, inventory, pricing, vendors, leases, cash_accounts, payments, and invoices.
>
> Start an output/harness.md file documenting the tables, their  fields, and why the agents might need them. I want this to reflect what's actually in the database, not assumptions about what a shop database should contain.

### Follow-up prompts

_None yet._

### What needed clarification / improvement

- The sentence "continue using the new db for ." was cut off. The assistant took it to mean using `data/campus_customs_new.db` for all work from here on, and leaving the original untouched.
- I asked for the documentation to reflect what's actually in the database rather than general assumptions about shops. So `output/harness.md` is built from direct queries, and anything inferred is marked **(inferred)**.

---

## P3 — Build the MCP server

### Prompt

> Moving to P3: Build the MCP server.
>
> Now that we understand the database, I want to create an MCP server that the agents can use to retrieve information about Campus Customs.
> Build the server using FastMCP inside mcp_server/ and connect it to data/campus_customs_new.db. Based on what we found about tickets 101, 102, and 103, create three tools that would help an agent gather the information needed to resolve those tickets. Make the tools specific to the actual ticket requirements, give them descriptive names, and have them return real database information rather than hardcoded values.
> Update output/harness.md to document each tool, the database table or tables it reads, the ticket it is meant to help with, and why the information is important for that ticket. Also create mcp_server/README.md explaining what the server does, which database it uses, and the tools available.
> For now I only want the server built and documented. We'll connect and test it in the next problem.

### Follow-up prompts

_None yet._

### What needed clarification / improvement

- I asked for tools tied to what tickets 101, 102 and 103 actually need, rather than generic "get table" tools. So each tool gathers everything one ticket type needs in a single call. For example, ticket 101's tool follows the ticket's `invoice_id` through to the vendor's lead time.
- I said the tools must return real database values, not hardcoded ones, so every number comes from a live query against `data/campus_customs_new.db`.
- I limited this step to building and documenting the server. The assistant only syntax-checked the code, and left installing FastMCP and running the server for P4.

---

## P4 — Connect the MCP server to Claude Code

### Prompt

> ok let's do P4: Connect the MCP server to Claude Code. I want to connect the MCP server from P3 to this Claude Code project and make sure the tools actually work. Set up a project-level .mcp.json configuration with the correct server startup command and paths.
> Once it's connected, test each of the three MCP tools directly through Claude Code. For each test, use a question related to the Campus Customs tickets and save the prompt I used, the tool that was called, and the actual response in output/mcp_smoke.json.
> Make sure the results agree with the working database. If the MCP server needs to be restarted or a tool doesn't connect, explain the problem and help me fix it. Don't generate sample results and pass them off as real tests.

### Follow-up prompts

> Where should the project-level .mcp.json go? → **Homeworks/5 (Recommended)**
>
> (My answer to the assistant's question. The session had been opened in the `AI Foundations` folder, but Claude Code reads `.mcp.json` from the folder a session is opened in.)

Test prompts, run in a new Claude Code session opened in `Homeworks/5`:

> Can we fill Tauhid Zaman's order for a Bulldog tee in size S (ticket 101), and if not, what's holding it up?

> Is the Elm City Properties rent notice (ticket 102) legitimate, how much do we owe and when, and can we afford it?

> The Yale AI Club wants 20 navy hoodies in size M at a bulk discount (ticket 103). How much stock do we have, and what's the largest discount we can give without losing money?

### What needed clarification / improvement

- **Where the config goes.** The assistant pointed out that the session had been opened in the parent `AI Foundations` folder, so a `.mcp.json` in `Homeworks/5` wouldn't load there. I chose to keep it in `Homeworks/5` with the homework and run the tests from a new Claude Code session opened in that folder.
- **Setup.** FastMCP wasn't installed, so the assistant created `Homeworks/5/.venv` and installed `fastmcp` (4.1.0). `.mcp.json` runs the server with that virtual environment's Python, using absolute paths.
- **Approval.** `claude mcp list` showed the server registered but "Pending approval". Claude Code won't start a project's MCP server until the user approves it, so I had to approve it myself when opening the new session.
- **Pre-check.** Before connecting, the assistant started the server with FastMCP's own client to confirm all three tools registered. That check is not one of the Claude Code tests and isn't recorded in `mcp_smoke.json`.
- **Testing.** In the new session the server connected as soon as it was approved, and all three tools showed up as `mcp__campus-customs-ops__*`. Each was called once through Claude Code with no errors and no restart needed. Every response was checked with read-only `sqlite3 -readonly` queries against `data/campus_customs_new.db` (desk date, ticket, inventory, pricing, invoice/vendor, lease, payments, cash), and all three matched. For example: tee S qty 0, invoice 501 $840 is 3 days overdue, rent $2,400 is due in 2 days and would leave $1,000 in checking, and hoodie M qty 8 with a break-even discount of $36 per unit. The exact responses and checks are in `output/mcp_smoke.json`, and both databases were unchanged afterward (identical checksums).

---

## P5 — Create the five-agent system

### Prompt

> okay P5: Create the five-agent system.
>
> Now I want to build the actual Campus Customs agent team using PydanticAI. I need five agents: Boss, Inventory, Accounting, Facilities, and Customer Service.
> The Boss should coordinate the work and decide which specialized agent is best suited to each ticket. The other agents should have clearly defined responsibilities and be able to delegate work to each other when needed, rather than the Boss automatically sending every ticket to all five.
> Create a detailed instruction file for each agent in backend/prompts/, define the shared data types in backend/models.py, and organize the agent code in backend/. All five agents must use gpt-6-luna through PORTKEY_API_KEY.
> Give each agent operating rules that reflect a real shop. For example, overdue items should be determined using desk.date_today, orders shouldn't be shipped if their invoices haven't been paid, and agents shouldn't be able to approve or execute payments without human authorization.
> Expand the MCP server with any additional tools needed to handle tickets 101, 102, and 103. All shop-related database information must go through MCP tools. I don't want a separate direct database access layer in the agents or backend that bypasses MCP.
> Set up output/audit_trail.json to capture every agent-loop step, including the agent involved, delegation, tool usage, and decisions. New records should be appended without deleting previous events.
> Finally, update output/harness.md with the five agents, their responsibilities, every MCP tool and its database tables, the safeguards around payments and other business decisions, and limits on agent loops and token usage. Update mcp_server/README.md to reflect the expanded tool set.

### Follow-up prompts

> Review the agent interactions to make sure the agents can actually delegate tasks and are collaborative, not just running independently.

### What needed clarification / improvement

- **Which Portkey key.** P1 said to copy `PORTKEY_API_KEY` from my `.env.example`, but `Homeworks/5` had none. The `.env.example` files elsewhere held placeholders or older keys. The assistant used the key from my root `AI Foundations/.env`, which my most recent lecture projects also use. It copied it into `Homeworks/5/.env` without displaying it, and added a placeholder `.env.example`.
- **"Human authorization" made real.** Asking for agents that "can't approve or execute payments" needed a mechanism, not just a prompt rule. The MCP server got an `approval_requests` table and two human-only tools, `decide_approval_request` and `execute_approved_payment`, which no agent's tool list includes. Agents can only file requests, and amounts are taken from the database.
- **Rules enforced in tools, not just prompts.** Rules like "don't ship on unpaid invoices" and "never below cost" are written into the agent prompts, but they're also enforced inside the MCP tools. So a model that ignores its instructions still can't break them.
- **"No direct database access."** The backend starts the MCP server over stdio and has no SQLite code. A search of `backend/` confirmed it.
- **Testing without changing data.** The end-to-end check ran against scratch copies of the database and audit file. The working database and `output/audit_trail.json` (still `[]`) stay clean for real runs.
- **Collaboration review (follow-up).** I asked for a check that the agents really collaborate. Delegation itself worked: handoffs carried figures, and results were used by the agent that asked. But tracing the audit trail turned up four problems:
  - the three leads ran in parallel, so no agent could see what another had filed
  - Accounting chose a courier and a mug vendor as hoodie restock options instead of asking Inventory
  - on a re-run, Customer Service saw the overdue invoice but never asked Accounting to request payment
  - the Boss's `handled_by` named agents that never worked the ticket

  Fixes:
  - ticket assignment is now sequential
  - restock questions must go to Inventory, which picks vendors by specialty
  - Customer Service must escalate unpaid invoices, and the Boss checks for anything left blocked
  - `handled_by` is rebuilt from the delegation record

  A third scratch run confirmed all of these. The details are in `output/harness.md` section 12.

---

## P6 — Plan how the agents should handle each ticket

### Prompt

> Now P6 - Plan how the agents should handle each ticket. Before running any tickets, I want to map out how I expect the agent team to handle each of the three open problems.
>
> Use the actual information from the three open tickets and the agent roles we designed to create a standalone output/desk_tickets.html page. Give each ticket its own tab and add two more tabs called Cash and Reflection, which you should leave empty for now.
>
> For each ticket, help me draft an Expected workflow that identifies which agent the Boss should contact first and why, which additional agents might need to be involved, the order of delegation between them, and the MCP tools they'll likely need. I want the workflow to be specific to the ticket.
>
> Only fill the Expected sections at this stage. Leave the Actual sections empty because we haven't run the system yet.

### Follow-up prompts

_None yet._

### What needed clarification / improvement

- **Real data, checked first.** I asked for the plan to use the tickets' actual data, so the assistant re-queried the working database before writing. It confirmed nothing had changed since the original: no desk run has touched it, and the P5 test runs used scratch copies. Every figure on the page comes from that query.
- **"Specific to the ticket."** Each Expected section names:
  - the lead agent and why it fits that ticket better than the alternatives
  - which agents are needed, and which aren't and why
  - the delegation order, as a diagram and a step table, with the MCP tool calls at each step
  - the expected end state, with what should happen and what must not

  The plan follows the routing and fixes from P5's collaboration review. Examples: Customer Service must escalate the overdue invoice to Accounting, Accounting must ask Inventory about restocking, and the Boss handles the most urgent ticket first.
- **Expected cash interplay.** Because tickets now run one after another, the plan predicts Accounting will see earlier requests. On 102 it should see the $840 invoice request; on 103 it should find only $160 left, less than the $264 needed to restock 12 hoodies.
- **Left empty on purpose.** The Actual sections have empty headings to fill in after the run (lead contacted, delegation order, tools called, outcome, differences from expected). The Cash and Reflection tabs are blank.
- **Preview.** The in-app preview server couldn't read `.claude/launch.json` (a macOS file-permission block). So the assistant checked the page's structure and script with a parser instead.

---

## P7 — Build the FastAPI backend

### Prompt

> P7: Build fastAPI backend.
>
> I need a backend that connects the agent team to the dashboard we'll build next. Use FastAPI in backend/main.py and create the API routes needed to manage the Campus Customs workflow.
>
> I want the backend to let me retrieve all three tickets with their current open or resolved status, run the agent team on a selected ticket, and see recent agent activity including messages, delegations, and MCP tools used. It should also have a separate route for a human to approve a proposed payment or purchase, a route to retrieve the checking balance from cash_accounts, and a route to reset the working database.
>
> Make sure proposed payments don't change the cash balance until a human explicitly approves them. All shop data access should follow the MCP-only architecture from P5, so don't add a direct SQL shortcut in the backend.
>
> The backend should work when started from the backend folder using uvicorn main:app --reload --port 8000. Update output/harness.md with all six API capabilities, the routes used, and what each does.

### Follow-up prompts

_None yet._

### What needed clarification / improvement

- **Reset and the ticket list stay MCP-only.** "No direct SQL shortcut" meant the backend couldn't copy the database file or query tickets itself. So two tools were added to the MCP server: `list_tickets`, for all tickets with an open/resolved state, and the human-only `reset_working_database`, which uses SQLite's backup API. A search of `backend/` finds no `sqlite3` or SQL.
- **"Approve a proposed payment or purchase."** Purchases were taken to mean vendor invoices, like invoice 501's reprint. Approving a payment is the only route where money moves: it approves and then executes in one MCP transaction. The route checks the balance first, so a request is never left approved but unpaid. A price override is only approved. A reject route and an approvals list were added for the dashboard.
- **Cash unchanged until a human approves.** This was verified through the running server: after the agents proposed rent on ticket 102, the balance stayed at $3,400. Approving under an agent's name returned `409`. Only "Shop Owner" approving moved it to $1,000.
- **Open/resolved needed a way to resolve.** Paying rent left ticket 102 at `awaiting_human_approval`, so nothing would ever show as resolved. Executing a payment now moves the linked ticket on in the same transaction: rent resolves its notice, and a paid restock invoice moves the order to `waiting_on_vendor`.
- **Audit gap found while testing.** A tool called in the same response as an agent's final report ran, but its result wasn't logged. Agents now use `end_strategy="exhaustive"`, and leftover results are logged from the message history.
- **One run at a time.** Runs and resets share a lock, because they change the same database. Overlapping requests get `409`.
- **Testing kept the real files clean.** All testing used scratch copies of the database and audit file, through the real `uvicorn main:app --reload --port 8000` server. The working database and `output/audit_trail.json` (still `[]`) are untouched.

---

## P8 — Build the React dashboard

### Prompt

> P8 — Build the React dashboard. I want to create a dashboard that makes it easy to manage Campus Customs and see what the AI agents are doing. Build the frontend in frontend/ using React, Vite, and TypeScript, and connect it to the FastAPI backend running on localhost:8000.
> The dashboard should display tickets 101, 102, and 103, show which ones are open or resolved, and let me select a ticket and run the agent team. I also want to see live activity from each agent, including which agent is working, what it's doing, and when it hands something off to another agent.
> Once a ticket is completed, show a summary of what each agent contributed. Include a clear button that lets me approve a proposed payment or purchase, and display the current checking balance. After I approve a payment, the balance should update to reflect the change.
> For the design, I'd like something polished and Yale-y. Give the agents distinct visual identities, use clear status indicators, and make the ticket information and financial information easy to follow.
> Make sure the frontend works with npm run dev, configure the backend to allow CORS from http://localhost:5173, and write output/design.md explaining the design choices, layout, agent identities, status indicators, cash display, and why those decisions make sense.

### Follow-up prompts

> Use modern react to pretty up the UI

### What needed clarification / improvement

- **"Live activity" needed a streaming backend.** The P7 run route only answered after the whole 40–50 s run. The assistant added `POST /api/tickets/{id}/run/stream`, which pushes each audit event to the browser as it's written (Server-Sent Events). It also added `GET /api/runs/{run_id}/events`, so a past run can be redrawn when you select its ticket. The audit trail notifies listeners as it writes, so the stream and `output/audit_trail.json` always match.
- **"Yale-y" was turned into concrete rules,** explained in `output/design.md`:
  - a Yale Blue masthead with a shield crest
  - serif display type on a warm paper background
  - one collegiate color and emblem per agent: Boss in navy with a shield, Inventory in ivy with a crate, Accounting in brass with a ledger, Facilities in brick with a gothic arch, Customer Service in slate violet with a speech bubble
  - every other color reserved for meaning
- **Approve needs a human name.** "Approve a proposed payment" became one green button that names the amount ("Approve & pay $2,400.00"). It's disabled until you type your own name; agent names are blocked. Each request shows its impact before you click. After a payment the balance counts down, and a before → after box flashes.
- **Testing in a real browser.** The Chrome extension wasn't connected, and the in-app preview couldn't read `.claude/launch.json` because of macOS file permissions. So the assistant drove the dashboard headlessly with Playwright and the installed Chrome, against scratch copies of the database and audit trail. Results:
  - **Ticket 102:** the live roster showed Facilities working while the Boss waited, and the hand-offs Boss → Facilities → Accounting appeared live. Approving "Approve & pay $2,400.00" moved checking from $3,400 to $1,000 and resolved the ticket.
  - **Ticket 103:** Accounting brought in Inventory. Approving the $52/unit price left cash unchanged.
  - **Reset:** everything returned to New and $3,400.
  - **No console errors**, and `npm run build` type-checks and compiles.
- **Fixes found while testing:**
  - The agent roster was cramped, so the cards became centered emblem cards with shorter role lines.
  - Hand-off text in contribution cards was clipped.
  - After a price override was approved, ticket 103 still said "Needs your approval". The MCP tool now moves a decided ticket back to `in_progress`; an approved payment's ticket is moved on when the payment executes. This was verified for all four decision cases.
- **A third browser used the test server.** During testing, the server log showed a browser other than the test scripts clicking Run on ticket 103. It was likely the user exploring at localhost:5173. That server pointed at scratch data, so the working database and audit trail are untouched. The test servers were stopped afterwards.
- **Follow-up: "Use modern react to pretty up the UI."** This left the specifics open. The assistant took "modern React" to mean React 19 and current tooling:
  - React Compiler 1.0 for automatic memoization
  - Actions (`<form action>` + `useFormStatus`) and `useOptimistic` for approvals
  - `useDeferredValue` for the streaming feed
  - one custom `useDesk` hook for all state

  It took "pretty up" to mean adding motion animation and lucide-react icons while keeping the Yale design. Visible changes:
  - an animated org-chart team graph that draws each hand-off as a colored edge
  - a lifecycle stepper on ticket cards
  - filter tabs in the feed
  - a stat strip in the masthead
  - a run timer
  - stacked toasts
  - an exact count-down of the balance after payments

  Browser testing found and fixed two issues: the spring-animated balance hadn't settled after 2 s ($2,560.02), so it was replaced with a fixed 0.9 s tween; and the gap between the Boss and the specialists was too small to see the edges. Section 11 of `output/design.md` explains each choice.

---

## P9 — Run and resolve all tickets

### Prompt

> P9 - run and resolve all tickets. Start by resetting data/campus_customs_new.db to the original state and recording the initial checking balance. Then run tickets 101, 102, and 103 through the agent dashboard, one at a time. If an agent proposes a payment or purchase, pause for me to review and explicitly approve it before any money is moved.
>
> As the tickets are processed, record which agents participated, the order of delegations, the MCP tools used, and the actual outcome. Use those results to fill the Actual section of each ticket in output/desk_tickets.html, without changing the Expected sections from P6.
> Complete the Cash tab with the starting checking balance, every actual cash change associated with each ticket, the reason and amount for each transaction, and the ending balance. Reconcile that ending balance against cash_accounts in the working database.
> Create output/resolved_tickets.json with each ticket's ID, final status, outcome, each agent's contribution, and any human approvals. Also create output/resolved_board.html with a genuine screenshot of the React dashboard for each completed ticket.
> Keep appending real events to output/audit_trail.json and finish output/harness.md so it accurately documents the final system. If a ticket fails or something doesn't reconcile, flag the issue rather than marking it as resolved or inventing results.

### Follow-up prompts

> I approve request #1: pay invoice 501 for $840.00. Record the approver as:

> I'll run it from the site, just record the outputs

> I'm done on the dashboard. Record the outputs for P9.

> Wait. I'll approve or reject price override #3 on the dashboard first, then tell you.

> I've decided on price override #3. Record the P9 outputs now.

### What needed clarification / improvement

- **Who approves.** The assistant reset the database and ran ticket 101 through the dashboard, then paused when Accounting proposed paying invoice 501. My first approval came with a blank approver name, and the assistant asked for one rather than inventing it. I then chose to approve and run the rest myself on the dashboard as "MM", and asked the assistant only to record the outputs.
- **Recording only after the run had settled.** When I said "done", the audit trail showed a run on 103 still in progress, and then a price override still pending. The assistant waited for the run to finish, asked whether to wait for my decision on #3, and only recorded after I'd decided. Every figure comes from the audit trail and the database read after that.
- **Not marking unfinished tickets as resolved.** Only 102 is resolved. 101 (size S still out of stock, reprint paid) and 103 (price approved, 12 hoodies short and no restock funded) are flagged as not resolved in every output.
- **Expected stayed untouched.** The P6 Expected sections were checked byte for byte against a copy taken before P9.
- **Cash reconciles.** $3,400 − $840 − $2,400 = $160, which equals `cash_accounts.checking`.
- **Repair to this file.** A P8 edit had accidentally cut the empty P9–P11 placeholders off the end of this log. They were restored before P9 was recorded.

---

## P10 — Reflect on the agent system

### Prompt

> P10 — Reflect on the agent system.
>
> Using the Expected and Actual sections of output/desk_tickets.html, the audit trail, and the cash results, help me organize the evidence for my reflection. For each ticket, show what I originally expected, what actually happened, which agents and MCP tools were involved, and whether the result was successful. Highlight any differences between the expected and actual workflows.
> I also want to evaluate whether the multi-agent setup was necessary for every step. Help me identify tasks that might have been easier with one agent using tools, and explain what evidence would support that argument.
> Next, identify three additional operational problems that the current system has the tools to handle, as well as three problems it cannot handle yet. For the latter, specify what tools, capabilities, or additional agents would be needed.
> Put this into the Reflection tab of output/desk_tickets.html. Use actual evidence from my ticket runs and cash results, but don't invent my opinions or make final judgments for me. Clearly mark any sections where I need to add my own assessment before submission.

### Follow-up prompts

> Here's my assessment, expand on it.  101 and 103 are not technically successes because they have not been resolved. the cash flag matters most to me because it let me approve knowing the limitations. It was a prompt problem. I also think the multi-agent setup was unnecessary for every step. Likely, the boss would be the one using this app, meaning they would know who to delegate each request to. A boss giving a task to another boss to delegate (delegating delegation) might be a little overkill. to improve the app, I would add another option of recommended next steps. for example, in p9, there was a draft email that was never sent about timelines for restock etc, it only has the option to approve. I would let it recommend other actions to the user. Overall, it was surprisingly good, I think with better prompting it could be better.

### What needed clarification / improvement

- **Evidence, not opinions.** I asked for the reflection to use real evidence and not to decide for me. The Reflection tab records only facts from the P6 plan, the four P9 runs, the audit trail and the cash results, and checks each ticket against measurable criteria. Five dashed "✍ Your assessment needed" boxes mark where my own judgment goes: whether each ticket was a success, which differences matter, whether multi-agent was necessary, what to build first, and my overall reflection.
- **Measured the single-agent question.** The "was multi-agent necessary?" section uses numbers computed from the audit trail: tokens per agent (the Boss used 53,704 of 138,370, or 39%), 6 reads that one agent repeated after another had already made them, 8 hand-offs, and time per run. It gives evidence on both sides, including the P5 case where Accounting alone picked the wrong restock vendor, and lists the comparison run that would settle it.
- **Problems the system can and can't handle are grounded in this run.** The three it can handle cite tool paths already exercised, with caveats (for example, $160 can't cover next month's $2,400 rent). The three it can't handle come from P9's unresolved tickets and the drafts that were never sent, each paired with specific missing tools.
- **Expected stayed unchanged.** The P6 Expected sections were checked byte for byte again.
- **My assessment, expanded.** I gave my own judgments, and the assistant expanded each one into the five boxes, now labeled "✍ My assessment", backing it with evidence from the runs:
  - **Success:** only 102 counts, since 101 and 103 aren't resolved.
  - **Cash flag:** it matters most and was a prompt problem. The data was in the tool results; Accounting's prompt never asked it to compare $160 against the ~$264 restock.
  - **Multi-agent:** unnecessary. The human user is effectively the boss, and the Boss agent spent 39% of tokens routing by a fixed rule.
  - **Improvement:** show recommended next steps as actions. Agents already return a `recommended_next_steps` field, such as "Send the draft customer update", but the dashboard only offers Approve or Reject.
  - **Overall:** surprisingly good, and better prompting would improve it.

---

## P11 — Submission

### Prompt

> P11-submission.
>
> lease go through the entire hw5 folder and check that all the deliverables from P1 through P10 are present and properly organized.
> Make sure the repository includes both database files, the MCP server, the five agents and their prompts, the FastAPI backend, the React frontend, the prompt log, the test results, the resolved ticket evidence, the dashboard screenshots, and the reflection. Check the directory structure against the assignment requirements.
> Prepare a README explaining what the project does, how to install the dependencies, how to reset the working database from the original, and how to start the MCP server, backend, and frontend. Also include requirements.txt, .gitignore, and .env.example with the required environment variable names but no real credentials.
> Check that my actual .env file and API keys are excluded from the repository and its Git history. Then prepare the project for a public GitHub repository, create a matching hw5.zip archive, and save the repository URL in output/github_url.txt once it has actually been published.
> Before publishing, show me anything missing or unsafe and let me review the final submission. Don't report a GitHub URL or a successful upload unless it actually happened.

### Follow-up prompts

> (Expected file layout screenshot: hw5/ with AI_prompts.md, requirements.txt, .env.example, .gitignore, .mcp.json, README.md, data/, mcp_server/server.py + README.md, frontend/, backend/main.py, models.py, prompts/*.md, output/ with harness.md, mcp_smoke.json, desk_tickets.html, design.md, resolved_tickets.json, resolved_board.html, audit_trail.json, github_url.txt)

> First rewrite the commit to use my GitHub noreply email, then publish it as a public repo at Mamometi/hw5.

### What needed clarification / improvement

- **Matching the expected layout.** I shared the required file tree. The MCP server was renamed from `mcp_server/mcp_server.py` to `mcp_server/server.py`, and every reference was updated. Root `README.md`, `requirements.txt` (pinned to the installed versions) and `.gitignore` were added. `output/mcp_smoke.json` still names the old file because it records the P4 test as it ran.
- **Unsafe before publishing.** `.mcp.json` held absolute paths containing my Mac username, so it was switched to relative paths and checked to still start all 16 tools. The runtime log, lock files, `.env`, `.venv` and `node_modules` are git-ignored. A scan confirmed my real Portkey key is in no committed file and nowhere in git history, and `.env` was never committed.
- **My email.** The first commit used my Yale email from git settings. Before publishing I asked for it to be rewritten to my GitHub noreply address, set for this repository only, so the public history contains no `yale.edu` address.
- **Honest publishing.** The first `gh repo create --push` created the repo, but the push failed with "remote end hung up". It was retried with a larger HTTP buffer and confirmed with `git ls-remote`. Only then was `output/github_url.txt` written.
- **Matching zip.** `hw5.zip` is built with `git archive` from the final commit, so it contains exactly what's in the repository.
