# Campus Customs Operations Desk: dashboard design

The dashboard (`frontend/`, React + Vite + TypeScript) is where a person runs the Campus Customs desk. They pick a ticket, watch the five agents work it, decide what only a human can decide, and see what it does to the shop's cash.

Every design choice below serves one of three jobs:
1. **Make it obvious what each ticket needs.**
2. **Make the agents' work readable as it happens.**
3. **Make money impossible to move by accident, and obvious when it does move.**

---

## 1. Look and feel: "Yale-y" without being a costume

| Choice | What it is | Why |
|---|---|---|
| **Yale Blue masthead** | `#00356B` header band with a lighter `#286DC0` rule beneath it, and a shield crest with "CC" | Yale Blue is the most recognizable signal of the school's look. The shield nods to a college crest without copying Yale's arms. |
| **Serif display type** | Headings, names, the balance and amounts use a book serif. The stack starts with Yale's own *YaleNew* and falls back to Iowan Old Style, Palatino and Georgia. | Yale's identity is built on a serif. It gives titles and figures a printed, institutional feel, while body text stays in a clean sans for readability. |
| **Warm paper background** | `#F6F4EF` page with white cards and soft warm-grey rules | Feels like letterhead or a ledger rather than a generic SaaS grey, and keeps white panels distinct. |
| **Restraint** | One accent color (Yale Blue) for structure. Every other color is reserved for meaning: agent identity, status, or money. | If color always means something, people learn to read it fast. |
| **Small-caps section labels** | Uppercase, tracked labels in Yale Blue for each panel ("Tickets", "Checking account") | Mimics the labeling on university print materials, and makes it easy to scan which panel is which. |

The page honors `prefers-reduced-motion`: all pulses, count-ups and slide-ins switch off.

---

## 2. Layout

```
┌────────────────────────────── Masthead: crest · desk date · model · connection ──────────────────────────────┐
├──────────────┬───────────────────────────────────────────────────────────┬─────────────────────────────────┤
│ TICKETS      │ TICKET DETAIL                                             │ CHECKING ACCOUNT                │
│  #101 card   │  #102 · Rent notice · "Rent due" · Open · Needs approval  │  $3,400.00 (big)                │
│  #102 card ◀ │  "Email: shop rent due in 2 days."                        │  owed vs. left bar              │
│  #103 card   │  facts · [▶ Run the agent team]                            │  ledger: invoice 501, rent      │
│              ├───────────────────────────────────────────────────────────┤  If everything is paid: $160    │
│ STATUS KEY   │ THE AGENT TEAM (org chart, live hand-off edges)            ├─────────────────────────────────┤
│              ├───────────────────────────────────────────────────────────┤ AWAITING YOUR APPROVAL          │
│              │ WHAT EACH AGENT CONTRIBUTED (after the run)                │  Approving as [Shop Owner]      │
│              ├───────────────────────────────────────────────────────────┤  Rent payment #1 · $2,400       │
│              │ LIVE ACTIVITY (feed with hand-off cards)                   │  Checking $3,400 → $1,000       │
│              │                                                            │  [✓ Approve & pay] [Reject]     │
│              │                                                            ├─────────────────────────────────┤
│              │                                                            │ PRACTICE MODE: reset            │
└──────────────┴───────────────────────────────────────────────────────────┴─────────────────────────────────┘
```

**Why three columns:**
- **Left: what needs doing.** The ticket queue is always visible and sticky. Each card shows its open/resolved state at a glance.
- **Center: the work.** The selected ticket, the team, what each agent contributed, and the step-by-step activity, read top to bottom in the order you need them.
- **Right: the money.** Cash and approvals sit together on purpose. Next to every Approve button you can see the balance it will draw from, and what's already owed.

**The center column's order is deliberate.** First what the ticket is, then who's working, then (once finished) the summary, then the detailed log. The summary sits above the long feed so the answer comes before the evidence.

**Responsive layout:** under 1240 px, cash and approvals move below as a row of cards. Under 820 px, everything stacks in a single column.

---

## 3. Agent identities

Each agent has one color, one emblem and one short role. They appear the same way everywhere: the roster, feed, hand-off cards, contribution cards, approval cards and ticket log. So once you know "brick red = Facilities", the whole page reads faster.

| Agent | Color | Emblem | Role line | Why |
|---|---|---|---|---|
| **Boss** | Yale Blue `#00356B` | Shield with a check (Lucide `ShieldCheck`) | Routes every ticket | The desk lead wears the school color and a crest-like shield: the authority that assigns work. |
| **Inventory** | Ivy green `#3D6B35` | Crate (`Package`) | Stock & shipping | Ivy for the campus. A crate reads instantly as "goods on shelves". |
| **Accounting** | Brass `#8A6A1F` | Open ledger (`BookOpen`) | Cash & pricing | Brass/gold says money without using alarm colors. The ledger matches its job. |
| **Facilities** | Old Campus brick `#9B3B2B` | Columned building (`Landmark`) | Lease & landlord | Brick and a collegiate building evoke Yale's campus, fitting the agent in charge of premises. |
| **Customer Service** | Slate violet `#5B4A86` | Speech bubble (`MessageCircle`) | The requester's voice | The one agent that faces outsiders gets the speech emblem and a hue clearly apart from the other four. |

**Telling them apart.** The five hues come from a collegiate palette (navy, ivy, brass, brick, slate violet) and differ in both hue and lightness. Each always comes with its emblem and name, so color is never the only cue, which matters for color-blind users. White emblems sit on solid colored circles with strong contrast. Text in an agent's color is used only on white or very light tints.

---

## 4. Showing live agent activity

The dashboard calls `POST /api/tickets/{id}/run/stream`. The backend streams every audit-trail event as it's written (Server-Sent Events), so the page updates during the 40–50 seconds a run takes rather than at the end.

| What you see | Built from | Why |
|---|---|---|
| **Team graph:** an org chart with the Boss on top and the four specialists below. Each node shows *Standing by* (faded), *Working* (tinted, lifted, pulsing ring), *Waiting on colleague* (amber) or *Done* (green). | Agent starts and final reports, tracked as a stack | Answers "which agent is working right now?" without reading the log. |
| **Hand-off edges:** every delegation is drawn as an edge in the receiving agent's color. Boss → specialist edges curve down from the Boss. Specialist → specialist edges arc beneath the row, so they never cross a card. While waiting for a reply, an edge animates as marching dashes with a dot running along it. Once the colleague reports back it settles to a solid line. | `delegation` and `delegation_result` events (`delegationEdges()` in `feed.ts`) | The prompt asked to see "when it hands something off to another agent". The graph shows the collaboration's shape at a glance, for example Customer Service → Accounting on ticket 101. Reporting lines that weren't used stay faint and dashed. |
| **Hand-off cards:** both agents' emblems with an arrow between them, a "HAND-OFF" or "REPORTED BACK" label, and the actual task text | `delegation` and `delegation_result` events | Hand-offs are the most important moments in a multi-agent run, so they get the strongest treatment in the feed: a boxed card, not a plain line. Showing the task text proves the agents pass real facts, not just names. |
| **Indentation** | Depth in the delegation chain | Boss → Facilities → Accounting work is nested visually, so you can see who's working on whose behalf. |
| **Tool lines:** plain English ("checked the rent notice against the lease"), the real MCP tool name in monospace, then ✓, *refused*, or a spinner while waiting | `tool_call` and `tool_result` events | Plain English for the person, plus the exact tool for the grader or developer. A refusal from an MCP guard rail, like trying to ship on an unpaid invoice, shows in red, so safeguards are visible when they fire. |
| **"Thinking" lines** in italics | Model text between tool calls | The agent's reasoning, set apart from actions. |
| **Filter tabs:** Everything, Hand-offs, MCP tools, Thinking, each with a live count. The selected tab's pill slides between options. | Feed item kinds | A run has 15–20 steps. Filters let you see only the hand-offs, or only the MCP tool calls, without losing the full log. |
| **Live badge** (red dot), elapsed timer on the button ("Agents working · 0:23"), a sweeping progress line on the ticket, and auto-scroll | While the stream is open | Makes clear the feed is happening now, not a replay, and shows how long the run has taken. |

After a run, or when you select a ticket that was worked earlier, the feed is rebuilt from `/api/runs/{run_id}/events` and labeled "Last run". Runs from before the latest database reset aren't shown, because they describe data that no longer exists.

---

## 5. "What each agent contributed"

Once the run ends, a summary appears above the feed:
- **An outcome banner** (Yale tint) with the ticket's new status, the Boss's one-paragraph summary, and who the Boss assigned it to.
- **One card per specialist**, topped with the agent's color:
  - whether it led the ticket or was "Brought in by" a colleague, and its number of tool calls
  - its own summary
  - **Did:** what it changed
  - **Handed off:** to whom, and what it asked for
  - **Needs your decision:** request numbers and amounts
  - any **draft reply (not sent)**
  - the MCP tools it used, as small chips

**Why:** the prompt asked to show what each agent contributed, so contributions are grouped per agent rather than per step. "Brought in by" makes the collaboration explicit, for example that Accounting worked ticket 102 because Facilities asked. The draft-reply label repeats the rule that nothing is sent to customers automatically.

---

## 6. Status indicators

Tickets carry **two indicators**, because there are two questions to answer:

| Indicator | Values | Look | Answers |
|---|---|---|---|
| **State pill** | Open · Resolved | Amber dot + "Open"; green check + "Resolved". The ticket card's left edge matches (amber or green). | "Is this done?" This is the open/resolved status the backend reports. |
| **Stage chip** | New · In progress · Waiting on vendor · Waiting on customer · **Needs your approval** · Resolved · Shipped | Grey (new), blue (in progress), amber (waiting on someone else), **solid Yale Blue with white text** (needs you), green (done) | "What's it waiting on?" |

**A lifecycle stepper on every ticket card:** Received → Agents → Your call → Done. The current step is a filled dot with a halo: Yale Blue normally, amber when waiting on a vendor or customer, green when done. It answers "how far along is this?", which neither pill shows.

**Why "Needs your approval" is the only solid chip:** it's the one stage where the person at the desk is the bottleneck, so it should stand out from across the room. Waiting on a vendor or customer is amber, because it's out of the user's hands. A **Status key** under the ticket list explains the colors. Ticket cards also show "1 awaiting you" and "Agents working" (with a spinner), so the queue alone tells you where attention is needed.

**Rules about color:**
- Green only ever means done or approved/paid.
- Amber means waiting.
- Red means overdue, refused or tight cash.
- Yale Blue means structure, or your action.

---

## 7. Cash display

The checking account panel sits at the top of the right column, with a Yale Blue top border:

1. **The balance, large, in the serif face, using tabular numerals.** It's the most important number on the page. Below it: "Balance as of Aug 31 · desk date Aug 31". The shop runs on `desk.date_today`, not the computer's clock, and the dashboard says so.
2. **An owed-vs-left bar.** A striped brass segment for obligations sits over a pale green track for what's left. You can see at a glance how much of the balance is already spoken for.
3. **The ledger** of what's owed and coming due:
   - each unpaid invoice with its vendor, and **"3 days overdue" in red**
   - rent with its landlord, and **"due Sep 2 (in 2 days)" in amber**
4. **"If everything is paid"** shows the cash left. It turns red with "Cash is tight. Every approval counts." when under $500. With $3,400 against $3,240 owed, the shop has just $160 to spare, and the panel makes that impossible to miss.

**After you approve a payment,** the balance counts down from the old figure to the new one, for example $3,400.00 → $1,000.00, with a 0.9 s ease-out tween using a motion value. Only the number's text node updates, so React doesn't re-render each frame, and it always lands on the exact figure. A green box flashes with the request ("Rent payment #1"), the before → after amounts, and the deduction in red (−$2,400.00). A toast confirms "Paid $2,400.00. Checking is now $1,000.00." The ledger, bar and ticket status all update from the backend, so the page always shows what the database says, not a guess.

**Why animate it:** a payment is the most consequential action on the page. Seeing the number move, rather than just change, confirms that this click moved real money.

---

## 8. Approving payments and purchases

Each pending request is a card in the right column, next to the cash it affects:
- the request type and number, and the amount in large serif type ("/unit" for a price override)
- who proposed it, with the agent's tag, and for which ticket
- the agent's reasoning
- **the impact before you click:**
  - for a payment: "Checking $3,400.00 → **$1,000.00** · paid from checking the moment you approve"
  - for a price override: "$58.00 → **$52.00** per unit · 10.3% off · $30.00 margin · no money moves"
- **one clear green button** that says exactly what it does: **"✓ Approve & pay $2,400.00"** or **"✓ Approve price"**, next to a quiet **Reject**

**Safeguards in the interface,** on top of the backend's:
- **You approve under your own name.** "Approving as" must be filled in. It's remembered in the browser, but starts empty, so the first approval is always a deliberate act.
- **Agent names are blocked.** The buttons stay disabled for agent names ("accounting", "boss" and so on), with the hint "Agents can't approve". The backend refuses them too.
- **The button names the amount,** so there's no ambiguity about what one click does.
- **Payment requests never touch the balance on their own.** Only this button moves money, and the backend checks the balance covers it before approving.
- **Requests on other tickets** are listed below as compact rows. Clicking one jumps to that ticket.

---

## 9. Other details

- **One run at a time.** While agents work on one ticket, the other tickets' Run buttons are disabled with an explanation, matching the backend's lock.
- **Ticket log.** A collapsible log under the ticket shows the dated notes agents and people added, each tagged with the agent's identity.
- **Practice mode.** "Reset working database" sits apart at the bottom of the right column, as a ghost button with a confirmation dialog. It's a teaching tool, not part of daily work, so it shouldn't compete with Approve.
- **Connection pill** in the masthead: "Backend connected", "Backend offline", or "Connecting…". If uvicorn isn't running, every error explains how to fix it.
- **Accessibility:**
  - the balance and feed are `aria-live`
  - focus rings are visible
  - the selected ticket uses `aria-current`
  - status is never color alone: every pill has a word and an icon

---

## 10. How it connects

- **Running it:**
  - Start the backend from `backend/` with `uvicorn main:app --reload --port 8000`.
  - Start the dashboard from `frontend/` with `npm install` (first time only), then `npm run dev`, and open http://localhost:5173.
- **API address:** the frontend calls `http://localhost:8000` directly; set `VITE_API_URL` to change it. The backend's CORS allows `http://localhost:5173` (and `127.0.0.1:5173`).
- **MCP-only:** the frontend only talks to the FastAPI routes. All shop data still goes through the MCP server.

---

## 11. Modern React and the visual refresh

A follow-up asked to "use modern React to pretty up the UI". This is what changed, and why.

### Modern React patterns

| Pattern | Where | Why |
|---|---|---|
| **React 19 + React Compiler 1.0** (`babel-plugin-react-compiler`, set up in `vite.config.ts`) | Every component | The compiler memoizes components and derived values automatically. `App.tsx` computes the feed, agent states, edges and contributions inline, with no `useMemo` or `useCallback`, and still avoids needless re-renders while a run streams in. |
| **Actions:** `<form action={fn}>` + `useFormStatus` | Approval cards (`Approvals.tsx`) | Each request card is a form whose action approves or rejects, depending on which submit button was pressed. `useFormStatus` gives the buttons their pending spinner without hand-written loading state. |
| **`useOptimistic`** | Approval cards | As soon as you click, the card shows "Paying $840.00…" (or "Rejecting…"), before the server answers. When the refresh arrives, the card slides out. |
| **`useDeferredValue`** | Activity feed | While events stream in, React renders the newest feed when it has a moment. Filter tabs and clicks stay responsive during a busy run. |
| **A custom hook for all desk state:** `useDesk()` | `hooks/useDesk.ts` | Tickets, cash, approvals, live runs, the stream, toasts and actions live in one hook. Components only render, so the UI is easier to change without touching the data flow. Also `useApprover()` (name remembered in `localStorage`) and `useElapsed()` (run timer). |
| **`ResizeObserver` in a layout effect** | `TeamGraph.tsx` | The graph measures its own width, so the SVG edges line up with the cards at any size. Below 560 px it switches to a simple list. |

### Motion and icons

- **motion** (`motion/react`, the successor to Framer Motion):
  - shared-layout animations (`layoutId`) for the ticket selection highlight and the filter-tab pill
  - `AnimatePresence` for feed items, approval cards, ledger rows and toasts entering and leaving
  - staggered contribution cards
  - `pathLength` drawing for hand-off edges
  - the balance count-down

  `<MotionConfig reducedMotion="user">` plus the CSS reduced-motion rule turn all of this off for people who ask their system for less motion.
- **lucide-react** icons replace the hand-drawn glyphs, so every icon on the page shares one stroke style:
  - agent emblems
  - ticket types: shopping bag, landmark, price tag
  - masthead stats, ledger rows, buttons and toasts

### Visual refinements

- **Masthead:** a deeper Yale Blue gradient with a light-blue rule. A **stat strip** under it shows open, waiting on you, resolved and checking. "Waiting on you" turns white when non-zero, so it pops.
- **Cards:** softer, layered shadows, 14 px corners, a slight lift on hover. Ticket cards have a type icon, a colored edge for their state, and the lifecycle stepper.
- **Ticket header:** a Yale Blue gradient tile with the ticket-type icon, and a larger serif title.
- **Buttons:** gradient fills with an inner highlight. "Run the agent team" becomes a live timer while working. Approve buttons show a spinner while pending.
- **Feed:** a timeline rail in each agent's color, monospace tool chips with a wrench icon, and hand-off cards blending the two agents' colors. Report-backs use a dashed outline and a green label.
- **Toasts:** a stack in the bottom-right with icon, title, detail and dismiss. They slide in and fade out instead of replacing each other.

**Verified** in headless Chrome against scratch data, with no console errors or warnings:
- **Live run (ticket 101):** the graph showed Customer Service working and the Boss waiting, with the hand-off edge animating. The button counted up the elapsed time.
- **Feed filters:** the Hand-offs filter showed exactly the 4 hand-off and report-back cards.
- **Approval:** "Paying $840.00…" appeared at once, and the balance landed exactly on $2,560.00. Then approving rent took it to $160.00 and ticket 102 went to Done.
- **Reset:** everything returned to $3,400.00 with 3 open tickets.
